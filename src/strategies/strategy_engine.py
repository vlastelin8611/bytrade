#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Движок выполнения торговых стратегий

Отвечает за:
- Управление множественными стратегиями
- Координацию выполнения
- Мониторинг производительности
- Управление рисками на уровне портфеля
"""

import logging
import threading
import time
from typing import Dict, List, Any, Optional, Type
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import asyncio

from .base_strategy import BaseStrategy, StrategyState

class StrategyEngine:
    """
    Движок для управления торговыми стратегиями
    """
    
    def __init__(self, api_client, db_manager, config_manager):
        self.api_client = api_client
        self.db = db_manager
        self.config = config_manager
        
        # Активные стратегии
        self.strategies: Dict[str, BaseStrategy] = {}
        self.strategy_threads: Dict[str, threading.Thread] = {}
        
        # Состояние движка
        self.is_running = False
        self.update_interval = 5  # секунд
        
        # Пул потоков для выполнения стратегий
        self.executor = ThreadPoolExecutor(max_workers=10)
        
        # Кэш рыночных данных
        self.market_data_cache = {}
        self.cache_update_time = {}
        self.cache_ttl = 30  # секунд
        
        # Статистика движка
        self.start_time = None
        self.total_updates = 0
        self.errors_count = 0
        
        # Логгер
        self.logger = logging.getLogger(__name__)
        
        # Блокировка для потокобезопасности
        self.lock = threading.RLock()
        
        self.logger.info("Движок стратегий инициализирован")
    
    def register_strategy(self, strategy_id: str, strategy: BaseStrategy) -> bool:
        """
        Регистрация новой стратегии
        
        Args:
            strategy_id: Уникальный идентификатор стратегии
            strategy: Экземпляр стратегии
            
        Returns:
            True если регистрация успешна
        """
        try:
            with self.lock:
                if strategy_id in self.strategies:
                    self.logger.warning(f"Стратегия {strategy_id} уже зарегистрирована")
                    return False
                
                self.strategies[strategy_id] = strategy
                self.logger.info(f"Стратегия {strategy_id} зарегистрирована")
                return True
                
        except Exception as e:
            self.logger.error(f"Ошибка регистрации стратегии {strategy_id}: {e}")
            return False
    
    def unregister_strategy(self, strategy_id: str) -> bool:
        """
        Отмена регистрации стратегии
        
        Args:
            strategy_id: Идентификатор стратегии
            
        Returns:
            True если отмена успешна
        """
        try:
            with self.lock:
                if strategy_id not in self.strategies:
                    self.logger.warning(f"Стратегия {strategy_id} не найдена")
                    return False
                
                # Остановка стратегии если она запущена
                strategy = self.strategies[strategy_id]
                if strategy.state == StrategyState.RUNNING:
                    strategy.stop()
                
                # Остановка потока если он существует
                if strategy_id in self.strategy_threads:
                    thread = self.strategy_threads[strategy_id]
                    if thread.is_alive():
                        # Ждем завершения потока
                        thread.join(timeout=5)
                    del self.strategy_threads[strategy_id]
                
                del self.strategies[strategy_id]
                self.logger.info(f"Стратегия {strategy_id} удалена")
                return True
                
        except Exception as e:
            self.logger.error(f"Ошибка удаления стратегии {strategy_id}: {e}")
            return False
    
    def start_strategy(self, strategy_id: str) -> bool:
        """
        Запуск конкретной стратегии
        
        Args:
            strategy_id: Идентификатор стратегии
            
        Returns:
            True если запуск успешен
        """
        try:
            with self.lock:
                if strategy_id not in self.strategies:
                    self.logger.error(f"Стратегия {strategy_id} не найдена")
                    return False
                
                strategy = self.strategies[strategy_id]
                
                # Проверка лимитов одновременных стратегий
                max_concurrent = self.config.get('strategies.max_concurrent', 3)
                running_count = sum(1 for s in self.strategies.values() 
                                  if s.state == StrategyState.RUNNING)
                
                if running_count >= max_concurrent:
                    self.logger.warning(f"Достигнут лимит одновременных стратегий: {max_concurrent}")
                    return False
                
                # Запуск стратегии
                if not strategy.start():
                    return False
                
                # Создание потока для стратегии
                thread = threading.Thread(
                    target=self._strategy_worker,
                    args=(strategy_id,),
                    name=f"Strategy-{strategy_id}",
                    daemon=True
                )
                
                self.strategy_threads[strategy_id] = thread
                thread.start()
                
                self.logger.info(f"Стратегия {strategy_id} запущена")
                return True
                
        except Exception as e:
            self.logger.error(f"Ошибка запуска стратегии {strategy_id}: {e}")
            return False
    
    def stop_strategy(self, strategy_id: str) -> bool:
        """
        Остановка конкретной стратегии
        
        Args:
            strategy_id: Идентификатор стратегии
            
        Returns:
            True если остановка успешна
        """
        try:
            with self.lock:
                if strategy_id not in self.strategies:
                    self.logger.error(f"Стратегия {strategy_id} не найдена")
                    return False
                
                strategy = self.strategies[strategy_id]
                
                # Остановка стратегии
                if not strategy.stop():
                    return False
                
                # Остановка потока
                if strategy_id in self.strategy_threads:
                    thread = self.strategy_threads[strategy_id]
                    if thread.is_alive():
                        thread.join(timeout=10)
                    del self.strategy_threads[strategy_id]
                
                self.logger.info(f"Стратегия {strategy_id} остановлена")
                return True
                
        except Exception as e:
            self.logger.error(f"Ошибка остановки стратегии {strategy_id}: {e}")
            return False
    
    def pause_strategy(self, strategy_id: str) -> bool:
        """
        Приостановка стратегии
        
        Args:
            strategy_id: Идентификатор стратегии
            
        Returns:
            True если приостановка успешна
        """
        try:
            if strategy_id not in self.strategies:
                return False
            
            return self.strategies[strategy_id].pause()
            
        except Exception as e:
            self.logger.error(f"Ошибка приостановки стратегии {strategy_id}: {e}")
            return False
    
    def resume_strategy(self, strategy_id: str) -> bool:
        """
        Возобновление стратегии
        
        Args:
            strategy_id: Идентификатор стратегии
            
        Returns:
            True если возобновление успешно
        """
        try:
            if strategy_id not in self.strategies:
                return False
            
            return self.strategies[strategy_id].resume()
            
        except Exception as e:
            self.logger.error(f"Ошибка возобновления стратегии {strategy_id}: {e}")
            return False
    
    def start_engine(self) -> bool:
        """
        Запуск движка стратегий
        
        Returns:
            True если запуск успешен
        """
        try:
            if self.is_running:
                self.logger.warning("Движок уже запущен")
                return False
            
            self.is_running = True
            self.start_time = datetime.utcnow()
            
            # Запуск основного цикла движка
            engine_thread = threading.Thread(
                target=self._engine_worker,
                name="StrategyEngine",
                daemon=True
            )
            engine_thread.start()
            
            self.logger.info("Движок стратегий запущен")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска движка: {e}")
            return False
    
    def stop_engine(self) -> bool:
        """
        Остановка движка стратегий
        
        Returns:
            True если остановка успешна
        """
        try:
            if not self.is_running:
                self.logger.warning("Движок уже остановлен")
                return False
            
            self.is_running = False
            
            # Остановка всех стратегий
            strategy_ids = list(self.strategies.keys())
            for strategy_id in strategy_ids:
                self.stop_strategy(strategy_id)
            
            # Закрытие пула потоков
            self.executor.shutdown(wait=True)
            
            self.logger.info("Движок стратегий остановлен")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка остановки движка: {e}")
            return False
    
    def emergency_stop(self) -> bool:
        """
        Экстренная остановка всех стратегий
        
        Returns:
            True если остановка успешна
        """
        try:
            self.logger.warning("ЭКСТРЕННАЯ ОСТАНОВКА всех стратегий")
            
            # Немедленная остановка всех стратегий
            for strategy_id, strategy in self.strategies.items():
                try:
                    strategy.stop()
                    self.logger.info(f"Стратегия {strategy_id} экстренно остановлена")
                except Exception as e:
                    self.logger.error(f"Ошибка экстренной остановки {strategy_id}: {e}")
            
            # Остановка движка
            self.is_running = False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка экстренной остановки: {e}")
            return False
    
    def get_strategies_status(self) -> Dict[str, Any]:
        """
        Получение статуса всех стратегий
        
        Returns:
            Словарь со статусом каждой стратегии
        """
        try:
            with self.lock:
                status = {}
                
                for strategy_id, strategy in self.strategies.items():
                    status[strategy_id] = strategy.get_status()
                
                return status
                
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса стратегий: {e}")
            return {}
    
    def get_engine_status(self) -> Dict[str, Any]:
        """
        Получение статуса движка
        
        Returns:
            Словарь с информацией о движке
        """
        uptime = None
        if self.start_time:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        running_strategies = sum(1 for s in self.strategies.values() 
                               if s.state == StrategyState.RUNNING)
        
        return {
            'is_running': self.is_running,
            'start_time': self.start_time,
            'uptime_seconds': uptime,
            'total_strategies': len(self.strategies),
            'running_strategies': running_strategies,
            'total_updates': self.total_updates,
            'errors_count': self.errors_count,
            'update_interval': self.update_interval,
            'cache_size': len(self.market_data_cache)
        }
    
    def _strategy_worker(self, strategy_id: str):
        """
        Рабочий поток для конкретной стратегии
        
        Args:
            strategy_id: Идентификатор стратегии
        """
        strategy = self.strategies.get(strategy_id)
        if not strategy:
            return
        
        self.logger.info(f"Запущен рабочий поток для стратегии {strategy_id}")
        
        while (strategy.state in [StrategyState.RUNNING, StrategyState.PAUSED] 
               and self.is_running):
            try:
                if strategy.state == StrategyState.RUNNING:
                    # Получение рыночных данных
                    market_data = self._get_market_data(strategy.symbol)
                    
                    if market_data:
                        # Обновление стратегии
                        result = strategy.update(market_data)
                        
                        if result.get('status') == 'error':
                            self.logger.error(f"Ошибка в стратегии {strategy_id}: {result.get('error')}")
                            self.errors_count += 1
                        
                        self.total_updates += 1
                
                # Пауза между обновлениями
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Ошибка в рабочем потоке стратегии {strategy_id}: {e}")
                self.errors_count += 1
                time.sleep(self.update_interval)
        
        self.logger.info(f"Рабочий поток стратегии {strategy_id} завершен")
    
    def _engine_worker(self):
        """
        Основной рабочий поток движка
        """
        self.logger.info("Запущен основной поток движка")
        
        while self.is_running:
            try:
                # Обновление кэша рыночных данных
                self._update_market_data_cache()
                
                # Мониторинг стратегий
                self._monitor_strategies()
                
                # Сохранение метрик производительности
                self._save_performance_metrics()
                
                # Пауза
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Ошибка в основном потоке движка: {e}")
                self.errors_count += 1
                time.sleep(self.update_interval)
        
        self.logger.info("Основной поток движка завершен")
    
    def _get_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Получение рыночных данных с кэшированием
        
        Args:
            symbol: Торговый символ
            
        Returns:
            Рыночные данные или None
        """
        try:
            current_time = datetime.utcnow()
            
            # Проверка кэша
            if (symbol in self.market_data_cache and 
                symbol in self.cache_update_time):
                
                cache_age = (current_time - self.cache_update_time[symbol]).total_seconds()
                if cache_age < self.cache_ttl:
                    return self.market_data_cache[symbol]
            
            # Получение свежих данных
            ticker_data = self.api_client.get_tickers(symbol=symbol)
            kline_data = self.api_client.get_kline(symbol=symbol, interval='1m', limit=100)
            
            if ticker_data.get('retCode') == 0 and kline_data.get('retCode') == 0:
                market_data = {
                    'symbol': symbol,
                    'timestamp': current_time,
                    'ticker': ticker_data.get('result', {}),
                    'klines': kline_data.get('result', {}),
                    'price': float(ticker_data.get('result', {}).get('list', [{}])[0].get('lastPrice', 0))
                }
                
                # Обновление кэша
                self.market_data_cache[symbol] = market_data
                self.cache_update_time[symbol] = current_time
                
                return market_data
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка получения рыночных данных для {symbol}: {e}")
            return None
    
    def _update_market_data_cache(self):
        """
        Обновление кэша рыночных данных для всех активных символов
        """
        try:
            # Получение списка уникальных символов из активных стратегий
            symbols = set()
            for strategy in self.strategies.values():
                if strategy.state == StrategyState.RUNNING:
                    symbols.add(strategy.symbol)
            
            # Обновление данных для каждого символа
            for symbol in symbols:
                self._get_market_data(symbol)
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления кэша рыночных данных: {e}")
    
    def _monitor_strategies(self):
        """
        Мониторинг состояния стратегий
        """
        try:
            for strategy_id, strategy in self.strategies.items():
                # Проверка на зависшие стратегии
                if strategy.last_update:
                    time_since_update = (datetime.utcnow() - strategy.last_update).total_seconds()
                    if time_since_update > 300:  # 5 минут
                        self.logger.warning(f"Стратегия {strategy_id} не обновлялась {time_since_update} секунд")
                
                # Проверка состояния ошибки
                if strategy.state == StrategyState.ERROR:
                    self.logger.error(f"Стратегия {strategy_id} в состоянии ошибки")
                    # Можно добавить логику автоматического перезапуска
                    
        except Exception as e:
            self.logger.error(f"Ошибка мониторинга стратегий: {e}")
    
    def _save_performance_metrics(self):
        """
        Сохранение метрик производительности в базу данных
        """
        try:
            current_time = datetime.utcnow()
            
            for strategy_id, strategy in self.strategies.items():
                if strategy.state == StrategyState.RUNNING:
                    status = strategy.get_status()
                    
                    # Сохранение метрик каждые 15 минут
                    if (not hasattr(strategy, '_last_metrics_save') or 
                        (current_time - strategy._last_metrics_save).total_seconds() > 900):
                        
                        self.db.save_performance_metrics(
                            strategy_name=strategy.name,
                            symbol=strategy.symbol,
                            period_start=strategy.start_time or current_time,
                            period_end=current_time,
                            total_trades=status['total_trades'],
                            winning_trades=status['winning_trades'],
                            losing_trades=status['losing_trades'],
                            total_profit_loss=status['total_pnl'],
                            win_rate=status['win_rate'],
                            additional_metrics={
                                'consecutive_losses': status['consecutive_losses'],
                                'daily_pnl': status['daily_pnl'],
                                'uptime_seconds': status['uptime_seconds']
                            }
                        )
                        
                        strategy._last_metrics_save = current_time
                        
        except Exception as e:
            self.logger.error(f"Ошибка сохранения метрик производительности: {e}")