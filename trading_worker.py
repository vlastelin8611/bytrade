#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для управления торговыми стратегиями и автоматической торговлей

Основные функции:
- Инициализация и управление торговыми стратегиями
- Подключение к API биржи
- Управление состоянием торговли
- Обработка сигналов от стратегий
"""

import logging
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal, QThread

from .bybit_client import BybitClient
from .db_manager import DatabaseManager
from .config_manager import ConfigManager
from .src.strategies.base_strategy import BaseStrategy

class TradingWorker(QObject):
    """
    Класс для управления торговыми стратегиями и автоматической торговлей
    
    Сигналы:
    - balance_updated: Обновление баланса
    - position_updated: Обновление позиций
    - log_message: Сообщение для логирования
    - strategy_status_changed: Изменение статуса стратегии
    """
    
    # Сигналы для обновления UI
    balance_updated = pyqtSignal(dict)
    position_updated = pyqtSignal(dict)
    log_message = pyqtSignal(str, str)  # (level, message)
    strategy_status_changed = pyqtSignal(str, str)  # (strategy_name, status)
    
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.logger = logging.getLogger("TradingWorker")
        
        # Флаг активности торговли
        self.trading_enabled = False
        
        # API клиент
        self.api_key = None
        self.api_secret = None
        self.client = None
        
        # База данных
        self.db_manager = None
        
        # Словарь активных стратегий
        self.strategies = {}
        
        # Интервал обновления данных (в секундах)
        self.update_interval = 5
        
        # Рабочий поток
        self.worker_thread = None
        
        self.logger.info("TradingWorker инициализирован")
    
    def initialize(self, api_key: str, api_secret: str, testnet: bool = True) -> bool:
        """
        Инициализация торгового воркера с API ключами
        
        Args:
            api_key: API ключ Bybit
            api_secret: API секрет Bybit
            testnet: Использовать тестовую сеть (True) или основную (False)
            
        Returns:
            bool: Успешность инициализации
        """
        try:
            self.api_key = api_key
            self.api_secret = api_secret
            
            # Инициализация API клиента
            self.client = BybitClient(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet
            )
            
            # Проверка соединения
            if not self.client.test_connectivity():
                self.logger.error("Не удалось подключиться к API Bybit")
                self.log_message.emit("error", "Не удалось подключиться к API Bybit")
                return False
            
            # Инициализация базы данных
            db_path = self.config_manager.get_value("database_path", "bytrade.db")
            self.db_manager = DatabaseManager(db_path, testnet=testnet)
            
            self.logger.info(f"TradingWorker успешно инициализирован с API ключами (testnet={testnet})")
            self.log_message.emit("info", f"Торговый воркер инициализирован (testnet={testnet})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации TradingWorker: {e}")
            self.log_message.emit("error", f"Ошибка инициализации торгового воркера: {e}")
            return False
    
    def enable_trading(self, enabled: bool) -> None:
        """
        Включение или отключение автоматической торговли
        
        Args:
            enabled: True для включения, False для отключения
        """
        self.trading_enabled = enabled
        status = "включена" if enabled else "отключена"
        self.logger.info(f"Автоматическая торговля {status}")
        self.log_message.emit("info", f"Автоматическая торговля {status}")
    
    def add_strategy(self, strategy_class, strategy_name: str, config: Dict[str, Any]) -> bool:
        """
        Добавление новой стратегии
        
        Args:
            strategy_class: Класс стратегии (наследник BaseStrategy)
            strategy_name: Имя стратегии
            config: Конфигурация стратегии
            
        Returns:
            bool: Успешность добавления стратегии
        """
        try:
            if not issubclass(strategy_class, BaseStrategy):
                self.logger.error(f"Класс {strategy_class.__name__} не является наследником BaseStrategy")
                return False
            
            if strategy_name in self.strategies:
                self.logger.warning(f"Стратегия с именем {strategy_name} уже существует")
                return False
            
            # Создание экземпляра стратегии
            strategy = strategy_class(
                name=strategy_name,
                config=config,
                api_client=self.client,
                db_manager=self.db_manager,
                config_manager=self.config_manager
            )
            
            # Добавление в словарь стратегий
            self.strategies[strategy_name] = strategy
            
            self.logger.info(f"Стратегия {strategy_name} добавлена")
            self.log_message.emit("info", f"Стратегия {strategy_name} добавлена")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка добавления стратегии {strategy_name}: {e}")
            self.log_message.emit("error", f"Ошибка добавления стратегии {strategy_name}: {e}")
            return False
    
    def remove_strategy(self, strategy_name: str) -> bool:
        """
        Удаление стратегии
        
        Args:
            strategy_name: Имя стратегии для удаления
            
        Returns:
            bool: Успешность удаления стратегии
        """
        try:
            if strategy_name not in self.strategies:
                self.logger.warning(f"Стратегия с именем {strategy_name} не найдена")
                return False
            
            # Остановка стратегии, если она запущена
            strategy = self.strategies[strategy_name]
            if strategy.state.value == "running":
                strategy.stop()
            
            # Удаление из словаря стратегий
            del self.strategies[strategy_name]
            
            self.logger.info(f"Стратегия {strategy_name} удалена")
            self.log_message.emit("info", f"Стратегия {strategy_name} удалена")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка удаления стратегии {strategy_name}: {e}")
            self.log_message.emit("error", f"Ошибка удаления стратегии {strategy_name}: {e}")
            return False
    
    def start_strategy(self, strategy_name: str) -> bool:
        """
        Запуск стратегии
        
        Args:
            strategy_name: Имя стратегии для запуска
            
        Returns:
            bool: Успешность запуска стратегии
        """
        try:
            if strategy_name not in self.strategies:
                self.logger.warning(f"Стратегия с именем {strategy_name} не найдена")
                return False
            
            # Проверка, включена ли торговля
            if not self.trading_enabled:
                self.logger.warning("Невозможно запустить стратегию: автоматическая торговля отключена")
                self.log_message.emit("warning", "Невозможно запустить стратегию: автоматическая торговля отключена")
                return False
            
            # Запуск стратегии
            strategy = self.strategies[strategy_name]
            result = strategy.start()
            
            if result:
                self.logger.info(f"Стратегия {strategy_name} запущена")
                self.log_message.emit("info", f"Стратегия {strategy_name} запущена")
                self.strategy_status_changed.emit(strategy_name, "running")
            else:
                self.logger.error(f"Не удалось запустить стратегию {strategy_name}")
                self.log_message.emit("error", f"Не удалось запустить стратегию {strategy_name}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска стратегии {strategy_name}: {e}")
            self.log_message.emit("error", f"Ошибка запуска стратегии {strategy_name}: {e}")
            return False
    
    def stop_strategy(self, strategy_name: str) -> bool:
        """
        Остановка стратегии
        
        Args:
            strategy_name: Имя стратегии для остановки
            
        Returns:
            bool: Успешность остановки стратегии
        """
        try:
            if strategy_name not in self.strategies:
                self.logger.warning(f"Стратегия с именем {strategy_name} не найдена")
                return False
            
            # Остановка стратегии
            strategy = self.strategies[strategy_name]
            result = strategy.stop()
            
            if result:
                self.logger.info(f"Стратегия {strategy_name} остановлена")
                self.log_message.emit("info", f"Стратегия {strategy_name} остановлена")
                self.strategy_status_changed.emit(strategy_name, "stopped")
            else:
                self.logger.error(f"Не удалось остановить стратегию {strategy_name}")
                self.log_message.emit("error", f"Не удалось остановить стратегию {strategy_name}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка остановки стратегии {strategy_name}: {e}")
            self.log_message.emit("error", f"Ошибка остановки стратегии {strategy_name}: {e}")
            return False
    
    def pause_strategy(self, strategy_name: str) -> bool:
        """
        Приостановка стратегии
        
        Args:
            strategy_name: Имя стратегии для приостановки
            
        Returns:
            bool: Успешность приостановки стратегии
        """
        try:
            if strategy_name not in self.strategies:
                self.logger.warning(f"Стратегия с именем {strategy_name} не найдена")
                return False
            
            # Приостановка стратегии
            strategy = self.strategies[strategy_name]
            if hasattr(strategy, 'pause') and callable(getattr(strategy, 'pause')):
                result = strategy.pause()
                
                if result:
                    self.logger.info(f"Стратегия {strategy_name} приостановлена")
                    self.log_message.emit("info", f"Стратегия {strategy_name} приостановлена")
                    self.strategy_status_changed.emit(strategy_name, "paused")
                else:
                    self.logger.error(f"Не удалось приостановить стратегию {strategy_name}")
                    self.log_message.emit("error", f"Не удалось приостановить стратегию {strategy_name}")
                
                return result
            else:
                self.logger.warning(f"Стратегия {strategy_name} не поддерживает приостановку")
                return False
            
        except Exception as e:
            self.logger.error(f"Ошибка приостановки стратегии {strategy_name}: {e}")
            self.log_message.emit("error", f"Ошибка приостановки стратегии {strategy_name}: {e}")
            return False
    
    def resume_strategy(self, strategy_name: str) -> bool:
        """
        Возобновление стратегии
        
        Args:
            strategy_name: Имя стратегии для возобновления
            
        Returns:
            bool: Успешность возобновления стратегии
        """
        try:
            if strategy_name not in self.strategies:
                self.logger.warning(f"Стратегия с именем {strategy_name} не найдена")
                return False
            
            # Возобновление стратегии
            strategy = self.strategies[strategy_name]
            if hasattr(strategy, 'resume') and callable(getattr(strategy, 'resume')):
                result = strategy.resume()
                
                if result:
                    self.logger.info(f"Стратегия {strategy_name} возобновлена")
                    self.log_message.emit("info", f"Стратегия {strategy_name} возобновлена")
                    self.strategy_status_changed.emit(strategy_name, "running")
                else:
                    self.logger.error(f"Не удалось возобновить стратегию {strategy_name}")
                    self.log_message.emit("error", f"Не удалось возобновить стратегию {strategy_name}")
                
                return result
            else:
                self.logger.warning(f"Стратегия {strategy_name} не поддерживает возобновление")
                return False
            
        except Exception as e:
            self.logger.error(f"Ошибка возобновления стратегии {strategy_name}: {e}")
            self.log_message.emit("error", f"Ошибка возобновления стратегии {strategy_name}: {e}")
            return False
    
    def get_strategy_status(self, strategy_name: str) -> Optional[str]:
        """
        Получение статуса стратегии
        
        Args:
            strategy_name: Имя стратегии
            
        Returns:
            Optional[str]: Статус стратегии или None, если стратегия не найдена
        """
        if strategy_name not in self.strategies:
            return None
        
        return self.strategies[strategy_name].state.value
    
    def get_all_strategies_status(self) -> Dict[str, str]:
        """
        Получение статусов всех стратегий
        
        Returns:
            Dict[str, str]: Словарь {имя_стратегии: статус}
        """
        return {name: strategy.state.value for name, strategy in self.strategies.items()}
    
    def update_strategy_config(self, strategy_name: str, config: Dict[str, Any]) -> bool:
        """
        Обновление конфигурации стратегии
        
        Args:
            strategy_name: Имя стратегии
            config: Новая конфигурация
            
        Returns:
            bool: Успешность обновления конфигурации
        """
        try:
            if strategy_name not in self.strategies:
                self.logger.warning(f"Стратегия с именем {strategy_name} не найдена")
                return False
            
            strategy = self.strategies[strategy_name]
            
            # Проверка, поддерживает ли стратегия обновление конфигурации
            if hasattr(strategy, 'update_config') and callable(getattr(strategy, 'update_config')):
                result = strategy.update_config(config)
                
                if result:
                    self.logger.info(f"Конфигурация стратегии {strategy_name} обновлена")
                    self.log_message.emit("info", f"Конфигурация стратегии {strategy_name} обновлена")
                else:
                    self.logger.error(f"Не удалось обновить конфигурацию стратегии {strategy_name}")
                    self.log_message.emit("error", f"Не удалось обновить конфигурацию стратегии {strategy_name}")
                
                return result
            else:
                # Если метод не поддерживается, обновляем конфигурацию напрямую
                # Это может быть небезопасно, но обеспечивает обратную совместимость
                strategy.config.update(config)
                self.logger.info(f"Конфигурация стратегии {strategy_name} обновлена напрямую")
                self.log_message.emit("info", f"Конфигурация стратегии {strategy_name} обновлена напрямую")
                return True
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления конфигурации стратегии {strategy_name}: {e}")
            self.log_message.emit("error", f"Ошибка обновления конфигурации стратегии {strategy_name}: {e}")
            return False
    
    def start_trading_worker(self) -> bool:
        """
        Запуск рабочего потока для обновления данных
        
        Returns:
            bool: Успешность запуска рабочего потока
        """
        try:
            # Проверка, что рабочий поток не запущен
            if self.worker_thread is not None and self.worker_thread.isRunning():
                self.logger.warning("Рабочий поток уже запущен")
                return False
            
            # Создание и запуск рабочего потока
            self.worker_thread = QThread()
            self.moveToThread(self.worker_thread)
            self.worker_thread.started.connect(self._worker_loop)
            self.worker_thread.start()
            
            self.logger.info("Рабочий поток запущен")
            self.log_message.emit("info", "Рабочий поток запущен")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска рабочего потока: {e}")
            self.log_message.emit("error", f"Ошибка запуска рабочего потока: {e}")
            return False
    
    def stop_trading_worker(self) -> bool:
        """
        Остановка рабочего потока
        
        Returns:
            bool: Успешность остановки рабочего потока
        """
        try:
            # Проверка, что рабочий поток запущен
            if self.worker_thread is None or not self.worker_thread.isRunning():
                self.logger.warning("Рабочий поток не запущен")
                return False
            
            # Остановка рабочего потока
            self.worker_thread.quit()
            self.worker_thread.wait()
            self.worker_thread = None
            
            self.logger.info("Рабочий поток остановлен")
            self.log_message.emit("info", "Рабочий поток остановлен")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка остановки рабочего потока: {e}")
            self.log_message.emit("error", f"Ошибка остановки рабочего потока: {e}")
            return False
    
    def _worker_loop(self) -> None:
        """
        Основной цикл рабочего потока
        """
        self.logger.info("Запущен основной цикл рабочего потока")
        
        while True:
            try:
                # Проверка, включена ли торговля
                if self.trading_enabled:
                    # Обновление баланса
                    self._update_balance()
                    
                    # Обновление позиций
                    self._update_positions()
                    
                    # Обновление стратегий
                    self._update_strategies()
                
                # Пауза между обновлениями
                time.sleep(self.update_interval)
                
            except Exception as e:
                self.logger.error(f"Ошибка в рабочем цикле: {e}")
                self.log_message.emit("error", f"Ошибка в рабочем цикле: {e}")
                time.sleep(5)  # Пауза перед повторной попыткой
    
    def _update_balance(self) -> None:
        """
        Обновление информации о балансе
        """
        try:
            if self.client is None:
                return
            
            # Получение баланса через API
            balance_info = self.client.get_wallet_balance(accountType="UNIFIED")
            
            if balance_info and 'result' in balance_info:
                # Обработка и отправка сигнала с обновленным балансом
                self.balance_updated.emit(balance_info['result'])
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления баланса: {e}")
    
    def _update_positions(self) -> None:
        """
        Обновление информации о позициях
        """
        try:
            if self.client is None:
                return
            
            # Получение позиций через API
            positions = self.client.get_positions(category="linear")
            
            if positions and 'result' in positions:
                # Обработка и отправка сигнала с обновленными позициями
                self.position_updated.emit(positions['result'])
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления позиций: {e}")
    
    def _update_strategies(self) -> None:
        """
        Обновление всех активных стратегий
        """
        for name, strategy in self.strategies.items():
            try:
                # Обновление только запущенных стратегий
                if strategy.state.value == "running":
                    # Проверка наличия метода update
                    if hasattr(strategy, 'update') and callable(getattr(strategy, 'update')):
                        strategy.update()
                    
            except Exception as e:
                self.logger.error(f"Ошибка обновления стратегии {name}: {e}")
                self.log_message.emit("error", f"Ошибка обновления стратегии {name}: {e}")
    
    def cleanup(self) -> None:
        """
        Очистка ресурсов при завершении работы
        """
        try:
            # Остановка всех стратегий
            for name, strategy in list(self.strategies.items()):
                if strategy.state.value == "running":
                    self.stop_strategy(name)
            
            # Остановка рабочего потока
            if self.worker_thread is not None and self.worker_thread.isRunning():
                self.stop_trading_worker()
            
            # Закрытие соединения с базой данных
            if self.db_manager is not None:
                self.db_manager.close()
            
            self.logger.info("TradingWorker успешно завершил работу")
            
        except Exception as e:
            self.logger.error(f"Ошибка при завершении работы TradingWorker: {e}")