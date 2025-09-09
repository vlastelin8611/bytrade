#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главное окно торгового бота для Bybit
Простое приложение с автоматическим подключением к API
"""

import sys
import os
import asyncio
import logging
import traceback
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
import threading
import time

# Добавляем путь к модулям
sys.path.append(str(Path(__file__).parent / 'src'))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QPushButton, QLabel, QTextEdit, QTableWidget, 
    QTableWidgetItem, QHeaderView, QSplitter, QGroupBox,
    QProgressBar, QStatusBar, QMessageBox, QTabWidget,
    QScrollArea, QFrame, QGridLayout, QSpacerItem, QSizePolicy,
    QLineEdit
)
from PySide6.QtCore import QTimer, QThread, Signal, Qt, QMutex, QMetaObject, Q_ARG
from PySide6.QtGui import QTextCursor
from PySide6.QtGui import QFont, QPalette, QColor, QPixmap, QIcon

# Импорт наших модулей
try:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
    from api.bybit_client import BybitClient
    from strategies.adaptive_ml import AdaptiveMLStrategy
    from database.db_manager import DatabaseManager
except ImportError as e:
    print(f"Ошибка импорта модулей: {e}")
    print("Убедитесь, что все файлы находятся в правильных директориях")
    sys.exit(1)


class TradingWorker(QThread):
    """Рабочий поток для торговых операций"""
    
    balance_updated = Signal(dict)
    positions_updated = Signal(list)
    trade_executed = Signal(dict)
    log_message = Signal(str)
    error_occurred = Signal(str)
    status_updated = Signal(str)
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.running = False
        self.trading_enabled = False
        self._mutex = QMutex()
        
        # Инициализация компонентов
        self.bybit_client = None
        self.ml_strategy = None
        self.db_manager = None
        self.config_manager = None
        
        # Статистика торговли
        self.daily_volume = 0.0
        self.daily_pnl = 0.0
        self.last_reset_date = datetime.now().date()
        
        # Настройка логирования с сохранением в отдельную папку
        log_dir = Path(__file__).parent / 'logs'
        log_dir.mkdir(exist_ok=True)  # Создаем папку, если не существует
        
        log_file = log_dir / f'trading_bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Логи сохраняются в файл: {log_file}")
    
    def run(self):
        """Основной цикл торгового потока"""
        session_id = f"session_{int(time.time())}"
        
        try:
            self.running = True
            self.status_updated.emit("Инициализация...")
            self.log_message.emit("Запуск торгового потока...")
            
            # Инициализация менеджера БД
            self.db_manager = DatabaseManager()
            # self.db_manager.log_entry({
            #     'level': 'INFO',
            #     'logger_name': 'TRADING_WORKER',
            #     'message': 'Trading worker started',
            #     'session_id': session_id
            # }) # Временно закомментировано - блокирует выполнение
            
            # Инициализация менеджера конфигурации
            try:
                # Пробуем импортировать из bytrade директории
                sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bytrade', 'src'))
                from core.config_manager import ConfigManager
                self.config_manager = ConfigManager()
                self.log_message.emit("✅ ConfigManager инициализирован")
            except ImportError as e:
                self.log_message.emit(f"⚠️ Ошибка импорта ConfigManager: {e}")
                self.log_message.emit("⚠️ Продолжаем без ConfigManager")
                self.config_manager = None
            
            # Инициализация клиента API
            start_time = time.time()
            self.bybit_client = BybitClient(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            init_time = (time.time() - start_time) * 1000
            
            # self.db_manager.log_entry({
            #     'level': 'INFO',
            #     'logger_name': 'API_CLIENT',
            #     'message': f'Client initialized (testnet: {self.testnet})',
            #     'session_id': session_id
            # }) # Временно закомментировано - блокирует выполнение
            
            # Инициализация ML стратегии
            try:
                self.log_message.emit("🤖 Инициализация ML стратегии...")
                self.log_message.emit("📋 Создание конфигурации ML...")
                start_time = time.time()
                ml_config = {
                    'feature_window': 50,
                    'confidence_threshold': 0.65,
                    'use_technical_indicators': True,
                    'use_market_regime': True
                }
                self.log_message.emit("✅ Конфигурация ML создана")
                self.log_message.emit("🔧 Создание объекта ML стратегии...")
                self.ml_strategy = AdaptiveMLStrategy(
                    name="adaptive_ml",
                    config=ml_config,
                    api_client=self.bybit_client,
                    db_manager=self.db_manager,
                    config_manager=self.config_manager
                )
                self.log_message.emit("✅ Объект ML стратегии создан")
                ml_init_time = (time.time() - start_time) * 1000
                
                # Временно закомментировано из-за блокировки
                # self.db_manager.log_entry({
                #     'level': 'INFO',
                #     'logger_name': 'ML_STRATEGY',
                #     'message': 'ML strategy initialized',
                #     'session_id': session_id
                # })
                self.log_message.emit("✅ ML стратегия инициализирована")
                print("DEBUG: ML стратегия инициализирована, продолжаем...")
                self.log_message.emit("🔄 Продолжаем после инициализации ML...")
            except Exception as e:
                error_msg = f"Ошибка инициализации ML стратегии: {e}"
                self.log_message.emit(error_msg)
                self.error_occurred.emit(error_msg)
                raise
            
            print("DEBUG: Устанавливаем статус...")
            self.log_message.emit("🔄 Устанавливаем статус 'Подключено'...")
            print("DEBUG: Вызываем status_updated.emit...")
            self.status_updated.emit("Подключено")
            print("DEBUG: Статус установлен")
            self.log_message.emit("✅ Статус установлен")
            self.log_message.emit("Подключение к Bybit API установлено")
            print(f"DEBUG: self.running = {self.running}")
            print("DEBUG: Вызываем log_message.emit для запуска цикла...")
            self.log_message.emit("🔄 Запуск основного торгового цикла...")
            print("DEBUG: Вызываем log_message.emit для проверки готовности...")
            self.log_message.emit("🔍 Проверка готовности к торговому циклу...")
            print("DEBUG: Дошли до основного цикла")
            
            # Основной торговый цикл
            cycle_count = 0
            print(f"DEBUG: Перед входом в цикл, self.running = {self.running}")
            print("DEBUG: Заменяем log_message.emit на print для избежания блокировки...")
            print(f"✅ Входим в торговый цикл, running={self.running}")
            print("🔄 Начинаем основной цикл while...")
            while self.running:
                print(f"🔄 Начало итерации цикла #{cycle_count + 1}")
                try:
                    print(f"🔄 Цикл #{cycle_count + 1} начат")
                    cycle_start = time.time()
                    cycle_count += 1
                    
                    # Сброс дневной статистики
                    print("🔄 Вызов _reset_daily_stats_if_needed()...")
                    self._reset_daily_stats_if_needed()
                    print("✅ _reset_daily_stats_if_needed() завершен")
                    
                    # Обновление баланса
                    print("🔄 Обновление баланса...")
                    balance_info = self._update_balance(session_id)
                    print(f"✅ Баланс обновлен: {balance_info is not None}")
                    
                    # Обновление позиций
                    print("🔄 Обновление позиций...")
                    positions = self._update_positions(session_id)
                    print(f"✅ Позиции обновлены: {len(positions) if positions else 0} позиций")
                    
                    # Торговая логика (если включена)
                    if self.trading_enabled:
                        print(f"🔄 Выполнение торгового цикла #{cycle_count}...")
                        self._execute_trading_cycle(session_id, positions)
                    else:
                        print(f"⏸️ Торговля отключена (цикл #{cycle_count})")
                        # Логируем состояние торговли каждые 10 циклов
                        if cycle_count % 10 == 1:
                            print("💡 Для включения торговли используйте кнопку 'Включить торговлю' в интерфейсе")
                    
                    # Логирование цикла
                    cycle_time = (time.time() - cycle_start) * 1000
                    # Временно закомментировано из-за блокировки
                    # self.db_manager.log_entry({
                    #     'level': 'DEBUG',
                    #     'logger_name': 'TRADING_CYCLE',
                    #     'message': f'Trading cycle {cycle_count} completed (enabled: {self.trading_enabled})',
                    #     'session_id': session_id
                    # })
                    
                    # Пауза между циклами
                    self.msleep(5000)  # 5 секунд
                    
                except Exception as e:
                    error_msg = f"Ошибка в торговом цикле: {e}"
                    self.logger.error(error_msg)
                    self.error_occurred.emit(error_msg)
                    
                    # Логирование ошибки
                    # Временно закомментировано из-за блокировки
                    # self.db_manager.log_entry({
                    #     'level': 'ERROR',
                    #     'logger_name': 'TRADING_WORKER',
                    #     'message': f'{type(e).__name__}: {str(e)}',
                    #     'exception': traceback.format_exc()
                    # })
                    
                    self.msleep(10000)  # 10 секунд при ошибке
                    
        except Exception as e:
            error_msg = f"Критическая ошибка торгового потока: {e}"
            self.logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            
            if self.db_manager:
                # Временно закомментировано из-за блокировки
                # self.db_manager.log_entry({
                #     'level': 'CRITICAL',
                #     'logger_name': 'TRADING_WORKER',
                #     'message': f'Critical error: {type(e).__name__}: {str(e)}',
                #     'exception': traceback.format_exc()
                # })
                pass
        finally:
            self.running = False
            self.status_updated.emit("Отключено")
            self.log_message.emit("Торговый поток остановлен")
            
            if self.db_manager:
                # Временно закомментировано из-за блокировки
                # self.db_manager.log_entry({
                #     'level': 'INFO',
                #     'logger_name': 'TRADING_WORKER',
                #     'message': 'Trading worker stopped',
                #     'session_id': session_id
                # })
                pass
    
    def _reset_daily_stats_if_needed(self):
        """Сброс дневной статистики при смене дня"""
        current_date = datetime.now().date()
        if current_date != self.last_reset_date:
            self.daily_volume = 0.0
            self.daily_pnl = 0.0
            self.last_reset_date = current_date
            
            # self.db_manager.log_entry({
            #     'level': 'INFO',
            #     'logger_name': 'TRADING_STATS',
            #     'message': f'Daily stats reset for date: {current_date}',
            #     'session_id': getattr(self, 'current_session_id', None)
            # }) # Временно закомментировано - блокирует выполнение
    
    def _update_balance(self, session_id: str) -> Optional[dict]:
        """Обновление информации о балансе"""
        try:
            start_time = time.time()
            # Получаем реальные данные через API
            balance_response = self.bybit_client.get_wallet_balance()
            exec_time = (time.time() - start_time) * 1000
            
            if balance_response and balance_response.get('list'):
                # Извлекаем данные из правильной структуры ответа API
                balance_data = balance_response['list'][0]
                
                # Создаем упрощенную структуру для совместимости
                balance_info = {
                    'totalWalletBalance': balance_data.get('totalWalletBalance', '0'),
                    'totalAvailableBalance': balance_data.get('totalAvailableBalance', '0'),
                    'totalEquity': balance_data.get('totalEquity', '0'),
                    'totalPerpUPL': balance_data.get('totalPerpUPL', '0'),
                    'coins': balance_data.get('coin', [])
                }
                
                # Обработка данных о монетах для правильного отображения
                for coin in balance_info['coins']:
                    # Сохраняем оригинальные значения без преобразования в USD
                    # и без усечения до меньших значений
                    coin_name = coin.get('coin')
                    wallet_balance = coin.get('walletBalance', '0')
                    available_balance = coin.get('availableToWithdraw', '0')
                    
                    self.logger.info(f"Баланс монеты {coin_name}: {wallet_balance} (доступно: {available_balance})")
                
                self.balance_updated.emit(balance_info)
                
                # Логирование снимка счета
                account_data = {
                    'total_balance': float(balance_info.get('totalWalletBalance', 0)),
                    'available_balance': float(balance_info.get('totalAvailableBalance', 0)),
                    'unrealized_pnl': float(balance_info.get('totalPerpUPL', 0)),
                    'daily_pnl': self.daily_pnl,
                    'daily_volume': self.daily_volume,
                    'execution_time_ms': exec_time
                }
                
                # Временно закомментировано - блокирует выполнение
                # self.db_manager.log_account_snapshot(account_data)
                
                return balance_info
            else:
                self.logger.warning("Получен пустой ответ при запросе баланса")
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления баланса: {e}")
            return None
    
    def _update_positions(self, session_id: str) -> List[dict]:
        """Обновление информации о позициях"""
        try:
            start_time = time.time()
            all_positions = []
            
            # Получаем позиции по поддерживаемым категориям (spot не поддерживается для позиций)
            categories = ["linear", "inverse"]
            
            for category in categories:
                try:
                    # Получаем реальные данные через API с указанием settleCoin=USDT для linear категории
                    settle_coin = "USDT" if category == "linear" else None
                    positions_list = self.bybit_client.get_positions(category=category, settle_coin=settle_coin)
                    
                    # Проверяем, что получили список позиций
                    if positions_list and isinstance(positions_list, list):
                        # Добавляем категорию к каждой позиции для идентификации
                        for pos in positions_list:
                            pos['category'] = category
                        all_positions.extend(positions_list)
                    self.logger.info(f"Получено {len(positions_list) if positions_list else 0} позиций для категории {category}")
                except Exception as e:
                    self.logger.warning(f"Ошибка получения позиций {category}: {e}")
                    continue
            
            # Фильтруем только активные позиции (с размером > 0)
            active_positions = []
            for pos in all_positions:
                size = float(pos.get('size', 0))
                if size > 0:
                    active_positions.append(pos)
            
            exec_time = (time.time() - start_time) * 1000
            self.logger.info(f"Найдено {len(active_positions)} активных позиций из {len(all_positions)} всего")
            
            # Всегда отправляем список позиций, даже если он пустой
            self.positions_updated.emit(active_positions)
            
            # Сохраняем позиции в базу данных
            if self.db_manager:
                try:
                    self.db_manager.save_positions(active_positions)
                    self.log_message.emit(f"Сохранено {len(active_positions)} позиций в базу данных")
                except Exception as db_err:
                    self.logger.error(f"Ошибка сохранения позиций в БД: {db_err}")
            
            # self.db_manager.log_entry({
            #     'level': 'DEBUG',
            #     'logger_name': 'API_POSITIONS',
            #     'message': f'Positions updated: {len(active_positions)} active positions from {len(all_positions)} total',
            #     'session_id': session_id
            # }) # Временно закомментировано - блокирует выполнение
            
            return active_positions
        except Exception as e:
            self.logger.error(f"Ошибка обновления позиций: {e}")
            self.positions_updated.emit([])  # Отправляем пустой список в случае ошибки
            
            # Сохраняем пустой список позиций в базу данных
            if self.db_manager:
                try:
                    self.db_manager.save_positions([])
                    self.log_message.emit("Нет активных позиций, обновлена БД")
                except Exception as db_err:
                    self.logger.error(f"Ошибка обновления пустых позиций в БД: {db_err}")
            
            # self.db_manager.log_entry({
            #     'level': 'DEBUG',
            return []
                #     'logger_name': 'API_POSITIONS',
                #     'message': 'No active positions found',
                #     'session_id': session_id
                # }) # Временно закомментировано - блокирует выполнение
            
            return active_positions
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления позиций: {e}")
            return []
    
    def _execute_trading_cycle(self, session_id: str, positions: List[dict]):
        """Выполнение одного цикла торговли"""
        try:
            cycle_start = time.time()
            
            # Получение списка доступных символов для торговли
            symbols_to_analyze = self._get_trading_symbols(positions)
            
            for symbol in symbols_to_analyze:
                try:
                    # Анализ символа
                    analysis_result = self._analyze_symbol(symbol, session_id)
                    
                    if analysis_result and analysis_result.get('signal') in ['BUY', 'SELL']:
                        # Проверка лимитов (не более 20% баланса в день)
                        if self._check_daily_limits(analysis_result):
                            trade_result = self._execute_trade(symbol, analysis_result, session_id)
                            
                            if trade_result:
                                self.trade_executed.emit(trade_result)
                                
                                # Обновление дневной статистики
                                self.daily_volume += float(trade_result.get('size', 0))
                                
                                # Обучение стратегии на результатах
                                self.ml_strategy.update_performance(symbol, trade_result)
                
                except Exception as e:
                    self.logger.error(f"Ошибка анализа символа {symbol}: {e}")
                    continue
            
            cycle_time = (time.time() - cycle_start) * 1000
            # self.db_manager.log_entry({
            #     'level': 'DEBUG',
            #     'logger_name': 'TRADING_CYCLE',
            #     'message': f'Trading cycle completed: analyzed {len(symbols_to_analyze)} symbols',
            #     'session_id': session_id
            # }) # Временно закомментировано - блокирует выполнение
                
        except Exception as e:
            self.logger.error(f"Ошибка выполнения торгового цикла: {e}")
    
    def _get_all_available_symbols(self) -> List[str]:
        """Получение всех доступных торговых символов через API"""
        try:
            if not self.bybit_client:
                return []
            
            # Получаем все доступные spot инструменты
            instruments = self.bybit_client.get_instruments_info(category="spot")
            
            if not instruments:
                self.logger.warning("Не удалось получить список инструментов, используем резервный список")
                from config import FALLBACK_TRADING_SYMBOLS
                return FALLBACK_TRADING_SYMBOLS
            
            # Фильтруем только USDT пары и активные инструменты
            usdt_symbols = []
            for instrument in instruments:
                symbol = instrument.get('symbol', '')
                status = instrument.get('status', '')
                
                # Проверяем что это USDT пара и инструмент активен
                if (symbol.endswith('USDT') and 
                    status == 'Trading' and 
                    len(symbol) <= 12):  # Исключаем слишком длинные символы
                    usdt_symbols.append(symbol)
            
            self.logger.info(f"Найдено {len(usdt_symbols)} доступных USDT торговых пар")
            return sorted(usdt_symbols)  # Сортируем для консистентности
            
        except Exception as e:
            self.logger.error(f"Ошибка получения списка торговых символов: {e}")
            # Возвращаем резервный список в случае ошибки
            from config import FALLBACK_TRADING_SYMBOLS
            return FALLBACK_TRADING_SYMBOLS
    
    def _get_trading_symbols(self, positions: List[dict]) -> List[str]:
        """Получение списка символов для анализа"""
        # Получаем все доступные торговые символы
        all_available_symbols = self._get_all_available_symbols()
        
        # Добавляем символы из активных позиций (если они есть)
        position_symbols = [pos.get('symbol') for pos in positions if pos.get('symbol')]
        
        # Объединяем все символы, приоритет отдаем символам с позициями
        priority_symbols = list(set(position_symbols))  # Символы с позициями идут первыми
        other_symbols = [s for s in all_available_symbols if s not in priority_symbols]
        
        # Объединяем: сначала символы с позициями, потом остальные
        final_symbols = priority_symbols + other_symbols
        
        self.logger.info(f"Будет анализироваться {len(final_symbols)} торговых символов")
        return final_symbols  # Возвращаем все доступные символы без ограничений
    
    def _analyze_symbol(self, symbol: str, session_id: str) -> Optional[dict]:
        """Анализ конкретного символа"""
        try:
            start_time = time.time()
            
            # Получение исторических данных
            klines = self.bybit_client.get_kline(
                symbol=symbol,
                interval='1h',
                limit=200
            )
            
            if not klines:
                return None
            
            # ML анализ
            analysis = self.ml_strategy.analyze_market(symbol, klines)
            
            exec_time = (time.time() - start_time) * 1000
            
            # Логирование анализа
            if analysis:
                analysis_data = {
                    'symbol': symbol,
                    'timeframe': '1h',
                    'current_price': klines[-1].get('close') if klines else 0,
                    'features': analysis.get('features', []),
                    'indicators': analysis.get('indicators', {}),
                    'regime': analysis.get('regime', {}),
                    'prediction': analysis.get('prediction', {}),
                    'signal': analysis.get('signal'),
                    'confidence': analysis.get('confidence'),
                    'execution_time_ms': exec_time
                }
                
                self.db_manager.log_analysis(analysis_data)
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа символа {symbol}: {e}")
            return None
    
    def _check_daily_limits(self, analysis: dict) -> bool:
        """Проверка дневных лимитов торговли"""
        try:
            # Получение текущего баланса
            balance_response = self.bybit_client.get_wallet_balance()
            if not balance_response or not balance_response.get('list'):
                return False
            
            balance_data = balance_response['list'][0]
            available_balance = float(balance_data.get('totalAvailableBalance', 0))
            
            # Проверка лимита 20% от баланса в день
            daily_limit = available_balance * 0.2
            
            if self.daily_volume >= daily_limit:
                # self.db_manager.log_entry({
                #     'level': 'WARNING',
                #     'logger_name': 'TRADING_LIMITS',
                #     'message': f'Daily trading limit reached: volume {self.daily_volume:.2f}, limit {daily_limit:.2f}',
                #     'session_id': getattr(self, 'current_session_id', None)
                # }) # Временно закомментировано - блокирует выполнение
                return False
            
            # Проверка минимальной уверенности
            confidence = analysis.get('confidence', 0)
            if confidence < 0.65:  # Повышенный порог уверенности
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки лимитов: {e}")
            return False
    
    def _execute_trade(self, symbol: str, analysis: dict, session_id: str) -> Optional[dict]:
        """Выполнение торговой операции"""
        try:
            start_time = time.time()
            
            signal = analysis.get('signal')
            confidence = analysis.get('confidence', 0)
            
            # Расчет размера позиции
            balance = self.bybit_client.get_wallet_balance()
            if not balance:
                return None
            
            available_balance = float(balance.get('availableBalance', 0))
            
            # Размер позиции зависит от уверенности (1-3% от баланса)
            position_percentage = 0.01 + (confidence - 0.65) * 0.02  # 1-3%
            position_size = available_balance * position_percentage
            
            # Проверка минимального размера
            if position_size < 10:
                return None
            
            # Размещение ордера
            side = 'Buy' if signal == 'BUY' else 'Sell'
            
            order_result = self.bybit_client.place_order(
                symbol=symbol,
                side=side,
                order_type='Market',
                qty=str(position_size)
            )
            
            exec_time = (time.time() - start_time) * 1000
            
            if order_result:
                trade_info = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'side': side,
                    'order_type': 'Market',
                    'size': position_size,
                    'analysis': analysis,
                    'order_result': order_result,
                    'execution_time_ms': exec_time,
                    'status': 'Executed'
                }
                
                # Логирование торговой операции
                # Временно закомментировано - блокирует выполнение
                # self.db_manager.log_trade(trade_info)
                
                self.log_message.emit(
                    f"✅ Торговля: {symbol} {side} ${position_size:.2f} (уверенность: {confidence:.2%})"
                )
                
                return trade_info
            else:
                pass
                # self.db_manager.log_entry({
                #     'level': 'WARNING',
                #     'logger_name': 'TRADING_ORDER',
                #     'message': f'Order failed: {symbol} {side}',
                #     'session_id': session_id
                # }) # Временно закомментировано - блокирует выполнение
            
        except Exception as e:
            error_msg = f"Ошибка выполнения торговой операции {symbol}: {e}"
            self.logger.error(error_msg)
            
            # self.db_manager.log_entry({
            #     'level': 'ERROR',
            #     'logger_name': 'TRADING_EXECUTION',
            #     'message': error_msg,
            #     'exception': e,
            #     'session_id': getattr(self, 'current_session_id', None)
            # }) # Временно закомментировано - блокирует выполнение
            
            return None
    
    def enable_trading(self, enabled: bool):
        """Включение/выключение торговли"""
        self._mutex.lock()
        try:
            self.trading_enabled = enabled
            status = "включена" if enabled else "выключена"
            self.log_message.emit(f"🔄 Торговля {status}")
            
            if self.db_manager:
                pass
                # self.db_manager.log_entry({
                #     'level': 'INFO',
                #     'logger_name': 'TRADING_CONTROL',
                #     'message': f'Trading toggled: {status}',
                #     'session_id': getattr(self, 'current_session_id', None)
                # }) # Временно закомментировано - блокирует выполнение
        finally:
            self._mutex.unlock()
    
    def stop(self):
        """Остановка торгового потока"""
        self._mutex.lock()
        try:
            self.running = False
            self.trading_enabled = False
            
            if self.db_manager:
                pass
                # self.db_manager.log_entry({
                #     'level': 'INFO',
                #     'logger_name': 'TRADING_WORKER',
                #     'message': 'Trading worker stop requested',
                #     'session_id': getattr(self, 'current_session_id', None)
                # }) # Временно закомментировано - блокирует выполнение
        finally:
            self._mutex.unlock()


class TradingBotMainWindow(QMainWindow):
    """Главное окно торгового бота"""
    
    def __init__(self):
        super().__init__()
        
        print("🔄 Начало инициализации главного окна...")
        
        # Настройка логирования
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        print("✅ Логирование настроено")
        
        # Импорт конфигурации
        print("🔄 Загрузка конфигурации...")
        try:
            import config
            credentials = config.get_api_credentials()
            self.api_key = credentials['api_key']
            self.api_secret = credentials['api_secret']
            self.testnet = credentials['testnet']
            print("✅ API ключи загружены")
            
            # Проверка конфигурации
            config_errors = config.validate_config()
            if config_errors:
                error_msg = "\n".join(config_errors)
                QMessageBox.critical(
                    None, "Ошибка конфигурации", 
                    f"Найдены ошибки в конфигурации:\n\n{error_msg}\n\nПожалуйста, отредактируйте файл config.py"
                )
                sys.exit(1)
            print("✅ Конфигурация валидна")
                
        except ImportError:
            QMessageBox.critical(
                None, "Ошибка", 
                "Файл config.py не найден!\nПожалуйста, создайте файл конфигурации."
            )
            sys.exit(1)
        
        # Инициализация компонентов
        self.trading_worker = None
        self.db_manager = None
        
        # Данные приложения
        self.current_balance = {}
        self.current_positions = []
        self.trade_history = []
        print("✅ Переменные инициализированы")
        
        # Настройка UI
        print("🔄 Инициализация UI...")
        self.init_ui()
        print("✅ UI создан")
        
        print("🔄 Применение стилей...")
        self.setup_styles()
        print("✅ Стили применены")
        
        # Загрузка API ключей в поля ввода
        print("🔄 Загрузка API ключей в поля ввода...")
        self.load_api_keys()
        print("✅ API ключи загружены в поля ввода")
        
        # Настройка таймеров для автоматического обновления
        print("🔄 Настройка таймеров автоматического обновления...")
        self.setup_timers()
        print("✅ Таймеры настроены")
        
        # Запуск торгового потока
        print("🔄 Запуск торгового потока...")
        self.start_trading_worker()
        print("✅ Главное окно полностью инициализировано")
    
    def setup_timers(self):
        """Настройка таймеров для автоматического обновления данных"""
        # Таймер для обновления позиций (каждые 30 секунд)
        self.positions_timer = QTimer(self)
        self.positions_timer.timeout.connect(self.refresh_positions)
        self.positions_timer.start(30000)  # 30 секунд
        self.logger.info("Таймер обновления позиций запущен (интервал: 30 секунд)")
        
        # Таймер для проверки статуса подключения (каждые 60 секунд)
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self.check_api_connection)
        self.connection_timer.start(60000)  # 60 секунд
        self.logger.info("Таймер проверки подключения запущен (интервал: 60 секунд)")
        
        # Таймер для полного обновления данных (каждые 120 секунд)
        self.data_timer = QTimer(self)
        self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(120000)  # 120 секунд
        self.logger.info("Таймер полного обновления данных запущен (интервал: 120 секунд)")
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        self.setWindowTitle("Торговый Бот Bybit - Автоматическая Торговля")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Заголовок приложения
        self.create_header(main_layout)
        
        # Основной контент в виде вкладок
        self.create_main_content(main_layout)
        
        # Строка состояния
        self.create_status_bar()
    
    def create_header(self, parent_layout):
        """Создание заголовка приложения"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.StyledPanel)
        header_frame.setMaximumHeight(80)
        
        header_layout = QHBoxLayout(header_frame)
        
        # Логотип и название
        title_label = QLabel("🤖 Торговый Бот Bybit")
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        # Статус подключения
        self.connection_status = QLabel("🔴 Отключено")
        self.connection_status.setStyleSheet(
            "QLabel { color: #e74c3c; font-weight: bold; font-size: 14px; }"
        )
        
        # Кнопка управления торговлей
        self.trading_toggle_btn = QPushButton("▶️ Включить торговлю")
        self.trading_toggle_btn.setMinimumSize(180, 40)
        self.trading_toggle_btn.clicked.connect(self.toggle_trading)
        self.trading_toggle_btn.setEnabled(False)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.connection_status)
        header_layout.addWidget(self.trading_toggle_btn)
        
        parent_layout.addWidget(header_frame)
    
    def create_main_content(self, parent_layout):
        """Создание основного контента"""
        # Создание вкладок
        self.tab_widget = QTabWidget()
        
        # Вкладка "Обзор"
        self.create_overview_tab()
        
        # Вкладка "Позиции"
        self.create_positions_tab()
        
        # Вкладка "История торговли"
        self.create_history_tab()
        
        # Вкладка "Настройки"
        self.create_settings_tab()
        
        # Вкладка "Логи"
        self.create_logs_tab()
        
        parent_layout.addWidget(self.tab_widget)
    
    def create_overview_tab(self):
        """Создание вкладки обзора"""
        overview_widget = QWidget()
        layout = QVBoxLayout(overview_widget)
        
        # Верхняя панель с балансом
        balance_frame = QGroupBox("💰 Баланс счета")
        balance_layout = QGridLayout(balance_frame)
        
        # Метки для отображения баланса
        self.total_balance_label = QLabel("$0.00")
        self.available_balance_label = QLabel("$0.00")
        self.unrealized_pnl_label = QLabel("$0.00")
        self.daily_pnl_label = QLabel("$0.00")
        
        # Стили для меток баланса
        balance_style = "QLabel { font-size: 16px; font-weight: bold; padding: 5px; }"
        self.total_balance_label.setStyleSheet(balance_style + "color: #2c3e50;")
        self.available_balance_label.setStyleSheet(balance_style + "color: #27ae60;")
        self.unrealized_pnl_label.setStyleSheet(balance_style)
        self.daily_pnl_label.setStyleSheet(balance_style)
        
        balance_layout.addWidget(QLabel("Общий баланс:"), 0, 0)
        balance_layout.addWidget(self.total_balance_label, 0, 1)
        balance_layout.addWidget(QLabel("Доступно:"), 0, 2)
        balance_layout.addWidget(self.available_balance_label, 0, 3)
        balance_layout.addWidget(QLabel("Нереализованный P&L:"), 1, 0)
        balance_layout.addWidget(self.unrealized_pnl_label, 1, 1)
        balance_layout.addWidget(QLabel("Дневной P&L:"), 1, 2)
        balance_layout.addWidget(self.daily_pnl_label, 1, 3)
        
        layout.addWidget(balance_frame)
        
        # Панель статистики торговли
        stats_frame = QGroupBox("📊 Статистика торговли")
        stats_layout = QGridLayout(stats_frame)
        
        self.trades_count_label = QLabel("0")
        self.win_rate_label = QLabel("0%")
        self.daily_volume_label = QLabel("$0.00")
        self.daily_limit_label = QLabel("$0.00")
        
        stats_style = "QLabel { font-size: 14px; font-weight: bold; color: #34495e; }"
        self.trades_count_label.setStyleSheet(stats_style)
        self.win_rate_label.setStyleSheet(stats_style)
        self.daily_volume_label.setStyleSheet(stats_style)
        self.daily_limit_label.setStyleSheet(stats_style)
        
        stats_layout.addWidget(QLabel("Сделок сегодня:"), 0, 0)
        stats_layout.addWidget(self.trades_count_label, 0, 1)
        stats_layout.addWidget(QLabel("Процент прибыльных:"), 0, 2)
        stats_layout.addWidget(self.win_rate_label, 0, 3)
        stats_layout.addWidget(QLabel("Дневной объем:"), 1, 0)
        stats_layout.addWidget(self.daily_volume_label, 1, 1)
        stats_layout.addWidget(QLabel("Дневной лимит:"), 1, 2)
        stats_layout.addWidget(self.daily_limit_label, 1, 3)
        
        layout.addWidget(stats_frame)
        
        # Панель управления
        control_frame = QGroupBox("⚙️ Управление")
        control_layout = QVBoxLayout(control_frame)
        
        # Первая строка - основные кнопки
        main_buttons_layout = QHBoxLayout()
        
        self.emergency_stop_btn = QPushButton("🛑 Экстренная остановка")
        self.emergency_stop_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; padding: 10px; }"
        )
        self.emergency_stop_btn.clicked.connect(self.emergency_stop)
        
        self.refresh_btn = QPushButton("🔄 Обновить данные")
        self.refresh_btn.clicked.connect(self.refresh_data)
        
        main_buttons_layout.addWidget(self.emergency_stop_btn)
        main_buttons_layout.addWidget(self.refresh_btn)
        main_buttons_layout.addStretch()
        
        # Добавляем только основные кнопки управления
        control_layout.addLayout(main_buttons_layout)
        
        layout.addWidget(control_frame)
        
        # Панель активов
        assets_frame = QGroupBox("💎 Активы")
        assets_layout = QVBoxLayout(assets_frame)
        
        # Таблица активов
        self.assets_table = QTableWidget()
        self.assets_table.setColumnCount(4)
        self.assets_table.setHorizontalHeaderLabels([
            "Актив", "Баланс", "USD Стоимость", "Доступно к выводу"
        ])
        
        # Настройка таблицы активов
        assets_header = self.assets_table.horizontalHeader()
        assets_header.setStretchLastSection(True)
        for i in range(3):
            assets_header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.assets_table.setAlternatingRowColors(True)
        self.assets_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.assets_table.setMaximumHeight(200)
        
        # Устанавливаем стиль для таблицы активов, чтобы текст был видимым
        self.assets_table.setStyleSheet(
            "QTableWidget { alternate-background-color: #f0f0f0; background-color: white; }"
            "QTableWidget::item { color: #2c3e50; }"
        )
        
        assets_layout.addWidget(self.assets_table)
        
        # Кнопка обновления активов
        refresh_assets_layout = QHBoxLayout()
        self.refresh_assets_btn = QPushButton("🔄 Обновить активы")
        self.refresh_assets_btn.setStyleSheet(
            "QPushButton { background-color: #3498db; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #2980b9; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.refresh_assets_btn.clicked.connect(self.refresh_data)
        refresh_assets_layout.addStretch()
        refresh_assets_layout.addWidget(self.refresh_assets_btn)
        assets_layout.addLayout(refresh_assets_layout)
        
        layout.addWidget(assets_frame)
        
        # Добавляем растягивающийся элемент
        layout.addStretch()
        
        self.tab_widget.addTab(overview_widget, "📈 Обзор")
    
    def create_positions_tab(self):
        """Создание вкладки позиций"""
        positions_widget = QWidget()
        layout = QVBoxLayout(positions_widget)
        
        # Заголовок
        header_label = QLabel("📋 Активные позиции")
        header_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; margin: 10px; }")
        layout.addWidget(header_label)
        
        # Таблица позиций
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(10)
        self.positions_table.setHorizontalHeaderLabels([
            "Символ", "Категория", "Сторона", "Размер", "Цена входа", "Текущая цена", 
            "Δ 1ч (%)", "Δ 24ч (%)", "Δ 30д (%)", "P&L"
        ])
        
        # Настройка таблицы
        header = self.positions_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(9):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        # Устанавливаем стиль для таблицы позиций, чтобы текст был видимым
        self.positions_table.setStyleSheet(
            "QTableWidget { alternate-background-color: #f0f0f0; background-color: white; }"
            "QTableWidget::item { color: #2c3e50; }"
        )
        
        layout.addWidget(self.positions_table)
        
        # Кнопка обновления позиций
        refresh_layout = QHBoxLayout()
        self.refresh_positions_btn = QPushButton("🔄 Обновить позиции")
        self.refresh_positions_btn.setStyleSheet(
            "QPushButton { background-color: #3498db; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #2980b9; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.refresh_positions_btn.clicked.connect(self.refresh_positions)
        refresh_layout.addStretch()
        refresh_layout.addWidget(self.refresh_positions_btn)
        layout.addLayout(refresh_layout)
        
        # Панель кнопок для торговли
        buttons_layout = QHBoxLayout()
        
        # Кнопка покупки самой дешевой позиции
        self.buy_cheapest_btn = QPushButton("🔽 Купить самую дешевую")
        self.buy_cheapest_btn.setStyleSheet(
            "QPushButton { background-color: #27ae60; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #2ecc71; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.buy_cheapest_btn.clicked.connect(self.buy_cheapest_position)
        buttons_layout.addWidget(self.buy_cheapest_btn)
        
        # Кнопка продажи самой дешевой позиции
        self.sell_cheapest_btn = QPushButton("🔼 Продать самую дешевую")
        self.sell_cheapest_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; padding: 8px; }"
            "QPushButton:hover { background-color: #c0392b; }"
            "QPushButton:disabled { background-color: #95a5a6; }"
        )
        self.sell_cheapest_btn.clicked.connect(self.sell_cheapest_position)
        buttons_layout.addWidget(self.sell_cheapest_btn)
        
        layout.addLayout(buttons_layout)
        
        self.tab_widget.addTab(positions_widget, "📊 Позиции")
    
    def create_history_tab(self):
        """Создание вкладки истории торговли"""
        history_widget = QWidget()
        layout = QVBoxLayout(history_widget)
        
        # Заголовок
        header_label = QLabel("📜 История торговли")
        header_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; margin: 10px; }")
        layout.addWidget(header_label)
        
        # Таблица истории
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)
        self.history_table.setHorizontalHeaderLabels([
            "Время", "Символ", "Сторона", "Размер", "Цена", "P&L", "Уверенность"
        ])
        
        # Настройка таблицы
        header = self.history_table.horizontalHeader()
        header.setStretchLastSection(True)
        for i in range(6):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        
        layout.addWidget(self.history_table)
        
        self.tab_widget.addTab(history_widget, "📋 История")
    
    def create_settings_tab(self):
        """Создание вкладки настроек"""
        from PySide6.QtWidgets import QLineEdit
        
        settings_widget = QWidget()
        layout = QVBoxLayout(settings_widget)
        
        # Группа настроек API
        api_group = QGroupBox("🔑 Настройки API Bybit")
        api_layout = QGridLayout(api_group)
        
        # Поля для ввода API ключей
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("Введите API Key")
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        self.api_secret_input = QLineEdit()
        self.api_secret_input.setPlaceholderText("Введите API Secret")
        self.api_secret_input.setEchoMode(QLineEdit.Password)
        
        # Кнопка для проверки API ключей
        test_api_btn = QPushButton("Проверить ключи")
        test_api_btn.clicked.connect(self.test_api_keys)
        
        # Кнопка для сохранения API ключей
        save_api_btn = QPushButton("Сохранить ключи")
        save_api_btn.clicked.connect(self.save_api_keys)
        
        # Кнопка для очистки API ключей
        clear_api_btn = QPushButton("Очистить ключи")
        clear_api_btn.clicked.connect(self.clear_api_keys)
        clear_api_btn.setStyleSheet(
            "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; }"
            "QPushButton:hover { background-color: #c0392b; }"
        )
        
        # Индикатор статуса API
        self.api_status_label = QLabel("⚠️ API ключи не проверены")
        self.api_status_label.setStyleSheet("QLabel { color: #f39c12; font-weight: bold; }")
        
        # Добавление элементов в layout
        api_layout.addWidget(QLabel("API Key:"), 0, 0)
        api_layout.addWidget(self.api_key_input, 0, 1)
        api_layout.addWidget(QLabel("API Secret:"), 1, 0)
        api_layout.addWidget(self.api_secret_input, 1, 1)
        api_layout.addWidget(self.api_status_label, 2, 0, 1, 2)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(test_api_btn)
        buttons_layout.addWidget(save_api_btn)
        buttons_layout.addWidget(clear_api_btn)
        api_layout.addLayout(buttons_layout, 3, 0, 1, 2)
        
        # Добавление группы в основной layout
        layout.addWidget(api_group)
        layout.addStretch()
        
        self.tab_widget.addTab(settings_widget, "⚙️ Настройки")
    
    def create_logs_tab(self):
        """Создание вкладки логов"""
        logs_widget = QWidget()
        layout = QVBoxLayout(logs_widget)
        
        # Заголовок
        header_label = QLabel("📝 Логи системы")
        header_label.setStyleSheet("QLabel { font-size: 16px; font-weight: bold; margin: 10px; }")
        layout.addWidget(header_label)
        
        # Текстовое поле для логов
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        # Примечание: ограничение количества строк будет реализовано через логику добавления сообщений
        
        # Стиль для логов
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12px;
                border: 1px solid #34495e;
            }
        """)
        
        layout.addWidget(self.logs_text)
        
        # Кнопки управления логами
        logs_control_layout = QHBoxLayout()
        
        clear_logs_btn = QPushButton("🗑️ Очистить логи")
        clear_logs_btn.clicked.connect(self.clear_logs)
        
        export_logs_btn = QPushButton("💾 Экспорт логов")
        export_logs_btn.clicked.connect(self.export_logs)
        
        logs_control_layout.addWidget(clear_logs_btn)
        logs_control_layout.addWidget(export_logs_btn)
        logs_control_layout.addStretch()
        
        layout.addLayout(logs_control_layout)
        
        self.tab_widget.addTab(logs_widget, "📝 Логи")
    
    def create_status_bar(self):
        """Создание строки состояния"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Индикатор состояния
        self.status_label = QLabel("Готов к работе")
        self.status_bar.addWidget(self.status_label)
        
        # Индикатор времени последнего обновления
        self.last_update_label = QLabel("Последнее обновление: никогда")
        self.status_bar.addPermanentWidget(self.last_update_label)
        
        # Инициализируем таймер для автоматического обновления данных
        self.data_timer = QTimer()
        self.data_timer.timeout.connect(self.refresh_data)
        self.data_timer.start(30000)  # Обновление каждые 30 секунд
        
    def load_api_keys(self):
        """Загрузка сохраненных API ключей в поля ввода"""
        try:
            # Если API ключи были загружены в __init__, отображаем их в полях ввода
            if hasattr(self, 'api_key') and self.api_key:
                self.api_key_input.setText(self.api_key)
                
            if hasattr(self, 'api_secret') and self.api_secret:
                self.api_secret_input.setText(self.api_secret)
                
            # Если оба ключа загружены, обновляем статус
            if (hasattr(self, 'api_key') and self.api_key and 
                hasattr(self, 'api_secret') and self.api_secret):
                self.api_status_label.setText("✅ API ключи загружены")
                self.api_status_label.setStyleSheet("QLabel { color: #27ae60; font-weight: bold; }")
                self.logger.info("API ключи успешно загружены из конфигурации")
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке API ключей: {e}")
            self.api_status_label.setText("❌ Ошибка загрузки API ключей")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            
    def clear_api_keys(self):
        """Очистка полей ввода API ключей и обновление файла конфигурации"""
        try:
            # Запрос подтверждения у пользователя
            reply = QMessageBox.question(
                self, "Подтверждение", 
                "Вы уверены, что хотите очистить API ключи?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Очистка полей ввода
                self.api_key_input.clear()
                self.api_secret_input.clear()
                
                # Очистка переменных
                self.api_key = ""
                self.api_secret = ""
                
                # Обновление файла конфигурации
                try:
                    # Путь к файлу конфигурации
                    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")
                    
                    # Чтение текущего содержимого файла
                    with open(config_path, "r", encoding="utf-8") as file:
                        content = file.read()
                    
                    # Регулярные выражения для замены значений API ключей
                    api_key_pattern = r"API_KEY\s*=\s*['\"].*['\"]" 
                    api_secret_pattern = r"API_SECRET\s*=\s*['\"].*['\"]" 
                    
                    # Замена значений на пустые строки
                    content = re.sub(api_key_pattern, "API_KEY = ''" , content)
                    content = re.sub(api_secret_pattern, "API_SECRET = ''" , content)
                    
                    # Запись обновленного содержимого обратно в файл
                    with open(config_path, "w", encoding="utf-8") as file:
                        file.write(content)
                    
                    # Очистка файла keys, если он существует
                    keys_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys")
                    if os.path.exists(keys_path):
                        try:
                            # Удаляем файл keys
                            os.remove(keys_path)
                            self.logger.info("Файл keys успешно удален")
                        except Exception as e:
                            self.logger.error(f"Ошибка при удалении файла keys: {e}")
                        
                    self.logger.info("API ключи успешно очищены в файле конфигурации")
                except Exception as e:
                    self.logger.error(f"Ошибка при обновлении файла конфигурации: {e}")
                    raise
                
                # Обновление статуса
                self.api_status_label.setText("⚠️ API ключи очищены")
                self.api_status_label.setStyleSheet("QLabel { color: #f39c12; font-weight: bold; }")
                
                # Отключение от биржи
                self.update_connection_status(False)
                
                # Логирование
                self.logger.info("API ключи очищены пользователем")
                self.add_log_message("🗑️ API ключи очищены")
                
                # Показать сообщение об успехе
                QMessageBox.information(
                    self, "Успех", 
                    "API ключи успешно очищены из полей ввода, файла конфигурации и файла keys."
                )
        except Exception as e:
            self.logger.error(f"Ошибка при очистке API ключей: {e}")
            self.handle_error("Ошибка при очистке API ключей", str(e))
    
    def setup_styles(self):
        """Настройка стилей приложения"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #ecf0f1;
                color: #2c3e50;
            }
            
            QTabWidget::pane {
                border: 1px solid #bdc3c7;
                background-color: white;
                color: #2c3e50;
            }
            
            QTabBar::tab {
                background-color: #bdc3c7;
                color: #2c3e50;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            
            QTabBar::tab:selected {
                background-color: white;
                color: #2c3e50;
                border-bottom: 2px solid #3498db;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 2px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #2c3e50;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #2c3e50;
            }
            
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            
            QPushButton:hover {
                background-color: #2980b9;
            }
            
            QPushButton:pressed {
                background-color: #21618c;
            }
            
            QPushButton:disabled {
                background-color: #95a5a6;
                color: #7f8c8d;
            }
            
            QTableWidget {
                gridline-color: #bdc3c7;
                background-color: white;
                color: #2c3e50;
                alternate-background-color: #f8f9fa;
            }
            
            QHeaderView::section {
                background-color: #34495e;
                color: white;
                padding: 8px;
            }
            
            QLabel {
                color: #2c3e50;
            }
            
            QLineEdit {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
            }
            
            QTextEdit {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            
            QComboBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
            }
            
            QSpinBox, QDoubleSpinBox {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 6px;
            }
            
            QCheckBox {
                color: #2c3e50;
            }
            
            QRadioButton {
                color: #2c3e50;
            }
            
            QListWidget {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
            
            QTreeWidget {
                background-color: white;
                color: #2c3e50;
                border: 1px solid #bdc3c7;
                border-radius: 4px;
            }
                border: none;
                font-weight: bold;
            }
        """)
    
    def start_trading_worker(self):
        """Запуск торгового потока"""
        try:
            print("🔄 Создание торгового потока...")
            self.trading_worker = TradingWorker(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.testnet
            )
            print("✅ Торговый поток создан")
            
            # Подключение сигналов
            print("🔗 Подключение сигналов...")
            self.trading_worker.balance_updated.connect(self.update_balance)
            self.trading_worker.positions_updated.connect(self.update_positions)
            self.trading_worker.trade_executed.connect(self.add_trade_to_history)
            self.trading_worker.log_message.connect(self.add_log_message)
            self.trading_worker.error_occurred.connect(self.handle_error)
            self.trading_worker.status_updated.connect(self.update_connection_status)
            print("✅ Сигналы подключены")
            
            # Запуск потока
            print("🚀 Запуск торгового потока...")
            self.trading_worker.start()
            print("✅ Торговый поток запущен")
            
            self.add_log_message("🚀 Торговый поток запущен")
            
        except Exception as e:
            error_msg = f"Ошибка запуска торгового потока: {e}"
            print(f"❌ {error_msg}")
            print(f"Traceback: {traceback.format_exc()}")
            self.handle_error(error_msg)
    
    def update_balance(self, balance_info: dict):
        """Обновление информации о балансе"""
        try:
            self.current_balance = balance_info
            
            total_balance = float(balance_info.get('totalWalletBalance', 0))
            available_balance = float(balance_info.get('totalAvailableBalance', 0))
            unrealized_pnl = float(balance_info.get('totalPerpUPL', 0))
            
            self.total_balance_label.setText(f"${total_balance:.2f}")
            self.available_balance_label.setText(f"${available_balance:.2f}")
            self.unrealized_pnl_label.setText(f"${unrealized_pnl:.2f}")
            
            # Цвет для нереализованного P&L
            if unrealized_pnl > 0:
                self.unrealized_pnl_label.setStyleSheet(
                    "QLabel { font-size: 16px; font-weight: bold; padding: 5px; color: #27ae60; }"
                )
            elif unrealized_pnl < 0:
                self.unrealized_pnl_label.setStyleSheet(
                    "QLabel { font-size: 16px; font-weight: bold; padding: 5px; color: #e74c3c; }"
                )
            else:
                self.unrealized_pnl_label.setStyleSheet(
                    "QLabel { font-size: 16px; font-weight: bold; padding: 5px; color: #34495e; }"
                )
            
            # Обновление дневного лимита
            daily_limit = available_balance * 0.2
            self.daily_limit_label.setText(f"${daily_limit:.2f}")
            
            # Обновление времени последнего обновления
            self.last_update_label.setText(
                f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}"
            )
            
            # Отображение списка активов
            if 'coins' in balance_info:
                self.update_assets_display(balance_info['coins'])
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления баланса: {e}")
    
    def update_assets_display(self, coins: list):
        """Обновление отображения активов"""
        try:
            if not coins:
                self.assets_table.setRowCount(0)
                return
            
            # Сортируем активы по USD стоимости (от большей к меньшей)
            sorted_coins = sorted(coins, key=lambda x: float(x.get('usdValue', 0)), reverse=True)
            
            # Фильтруем активы с ненулевым балансом
            active_coins = [coin for coin in sorted_coins if float(coin.get('walletBalance', 0)) > 0]
            
            # Очищаем таблицу перед обновлением
            self.assets_table.clearContents()
            self.assets_table.setRowCount(len(active_coins))
            
            for i, coin in enumerate(active_coins):
                coin_name = coin.get('coin', '')
                wallet_balance = coin.get('walletBalance', '0')
                usd_value = coin.get('usdValue', '0')
                available_to_withdraw = coin.get('availableToWithdraw', '0')
                
                # Преобразуем в float для форматирования вывода
                wallet_balance_float = float(wallet_balance)
                usd_value_float = float(usd_value)
                available_float = float(available_to_withdraw)
                
                # Создаем элементы таблицы с улучшенным форматированием
                coin_item = QTableWidgetItem(coin_name)
                coin_item.setTextAlignment(Qt.AlignCenter)
                
                # Адаптивное форматирование в зависимости от типа актива и значения
                if coin_name in ['BTC', 'ETH']:
                    # Для BTC и ETH показываем больше знаков после запятой
                    precision = 8
                elif wallet_balance_float < 0.01:
                    # Для очень маленьких значений показываем больше знаков
                    precision = 8
                else:
                    # Для остальных активов используем стандартное форматирование
                    precision = 4
                
                balance_item = QTableWidgetItem(f"{wallet_balance_float:.{precision}f}")
                balance_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # USD значение всегда с 2 знаками после запятой
                usd_item = QTableWidgetItem(f"${usd_value_float:.2f}")
                usd_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                available_item = QTableWidgetItem(f"{available_float:.{precision}f}")
                available_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Добавляем элементы в таблицу
                self.assets_table.setItem(i, 0, coin_item)
                self.assets_table.setItem(i, 1, balance_item)
                self.assets_table.setItem(i, 2, usd_item)
                self.assets_table.setItem(i, 3, available_item)
            
            # Принудительно обновляем всю таблицу
            self.assets_table.resizeColumnsToContents()
            self.assets_table.viewport().update()
            self.add_log_message(f"✅ Обновлено активов: {len(active_coins)}")
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления активов: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
    
    def update_positions(self, positions: List[dict]):
        """Обновление таблицы позиций"""
        try:
            self.current_positions = positions
            
            # Очищаем таблицу перед обновлением
            self.positions_table.clearContents()
            self.positions_table.setRowCount(len(positions))
            
            # Получаем историю цен для всех символов
            price_history = {}
            try:
                all_price_history = self.db_manager.get_price_history()
                for ph in all_price_history:
                    price_history[ph[1]] = ph  # Индекс 1 - это symbol
            except Exception as e:
                self.add_log_message(f"⚠️ Ошибка получения истории цен: {e}")
            
            # Сортируем позиции по P&L (от наибольшего к наименьшему)
            positions.sort(key=lambda x: float(x.get('unrealisedPnl', 0)), reverse=True)
            
            for row, position in enumerate(positions):
                symbol = position.get('symbol', '')
                category = position.get('category', 'Unknown').upper()
                side = position.get('side', '')
                size = float(position.get('size', 0))
                entry_price = float(position.get('avgPrice', 0))
                unrealized_pnl = float(position.get('unrealisedPnl', 0))
                
                # Создаем элементы с выравниванием
                symbol_item = QTableWidgetItem(symbol)
                symbol_item.setTextAlignment(Qt.AlignCenter)
                
                category_item = QTableWidgetItem(category)
                category_item.setTextAlignment(Qt.AlignCenter)
                
                # Устанавливаем цвет для стороны позиции (Buy/Sell)
                side_item = QTableWidgetItem(side)
                side_item.setTextAlignment(Qt.AlignCenter)
                if side.upper() == "BUY":
                    side_item.setFont(QFont("Arial", 9, QFont.Bold))
                elif side.upper() == "SELL":
                    side_item.setFont(QFont("Arial", 9, QFont.Bold))
                
                # Размер позиции с адаптивным форматированием
                size_format = "{:.8f}" if size < 0.0001 else "{:.4f}"
                size_item = QTableWidgetItem(size_format.format(size))
                size_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Цена входа
                entry_price_item = QTableWidgetItem(f"${entry_price:.6f}")
                entry_price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                
                # Добавляем элементы в таблицу
                self.positions_table.setItem(row, 0, symbol_item)
                self.positions_table.setItem(row, 1, category_item)
                self.positions_table.setItem(row, 2, side_item)
                self.positions_table.setItem(row, 3, size_item)
                self.positions_table.setItem(row, 4, entry_price_item)
                
                # Добавляем текущую цену и динамику цен
                current_price = 0
                change_1h = 0
                change_24h = 0
                change_30d = 0
                
                if symbol in price_history:
                    ph = price_history[symbol]
                    current_price = ph[2]  # Индекс 2 - текущая цена
                    change_1h = ph[8]      # Индекс 8 - изменение за 1ч
                    change_24h = ph[9]     # Индекс 9 - изменение за 24ч
                    change_30d = ph[11]    # Индекс 11 - изменение за 30д
                
                # Текущая цена
                current_price_item = QTableWidgetItem(f"${current_price:.6f}")
                current_price_item.setForeground(QColor("#2c3e50"))
                current_price_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.positions_table.setItem(row, 5, current_price_item)
                
                # Изменение цены за 1ч
                change_1h_text = f"+{change_1h:.2f}%" if change_1h > 0 else f"{change_1h:.2f}%"
                change_1h_item = QTableWidgetItem(change_1h_text)
                change_1h_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if change_1h > 0 or change_1h < 0:
                    change_1h_item.setFont(QFont("Arial", 9, QFont.Bold))
                self.positions_table.setItem(row, 6, change_1h_item)
                
                # Изменение цены за 24ч
                change_24h_text = f"+{change_24h:.2f}%" if change_24h > 0 else f"{change_24h:.2f}%"
                change_24h_item = QTableWidgetItem(change_24h_text)
                change_24h_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if change_24h > 0 or change_24h < 0:
                    change_24h_item.setFont(QFont("Arial", 9, QFont.Bold))
                self.positions_table.setItem(row, 7, change_24h_item)
                
                # Изменение цены за 30д
                change_30d_text = f"+{change_30d:.2f}%" if change_30d > 0 else f"{change_30d:.2f}%"
                change_30d_item = QTableWidgetItem(change_30d_text)
                change_30d_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if change_30d > 0 or change_30d < 0:
                    change_30d_item.setFont(QFont("Arial", 9, QFont.Bold))
                self.positions_table.setItem(row, 8, change_30d_item)
                
                # P&L с цветом и знаком
                pnl_text = f"+${unrealized_pnl:.2f}" if unrealized_pnl > 0 else f"${unrealized_pnl:.2f}"
                pnl_item = QTableWidgetItem(pnl_text)
                pnl_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if unrealized_pnl > 0 or unrealized_pnl < 0:
                    pnl_item.setFont(QFont("Arial", 9, QFont.Bold))
                
                self.positions_table.setItem(row, 9, pnl_item)
            
            self.add_log_message(f"📊 Обновлено позиций: {len(positions)}")
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления позиций: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
    
    def add_trade_to_history(self, trade_info: dict):
        """Добавление торговой операции в историю"""
        try:
            self.trade_history.append(trade_info)
            
            # Обновление таблицы истории
            row_count = self.history_table.rowCount()
            self.history_table.insertRow(0)  # Вставляем в начало
            
            timestamp = trade_info.get('timestamp', '')
            if timestamp:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_str = dt.strftime('%H:%M:%S')
            else:
                time_str = datetime.now().strftime('%H:%M:%S')
            
            symbol = trade_info.get('symbol', '')
            side = trade_info.get('side', '')
            size = float(trade_info.get('size', 0))
            price = trade_info.get('price', 'Market')
            pnl = trade_info.get('pnl', 'N/A')
            
            analysis = trade_info.get('analysis', {})
            confidence = analysis.get('confidence', 0) if analysis else 0
            
            self.history_table.setItem(0, 0, QTableWidgetItem(time_str))
            self.history_table.setItem(0, 1, QTableWidgetItem(symbol))
            
            # Сторона с цветом
            side_item = QTableWidgetItem(side)
            if side == 'Buy':
                side_item.setForeground(QColor("#27ae60"))
            else:
                side_item.setForeground(QColor("#e74c3c"))
            self.history_table.setItem(0, 2, side_item)
            
            self.history_table.setItem(0, 3, QTableWidgetItem(f"{size:.4f}"))
            self.history_table.setItem(0, 4, QTableWidgetItem(str(price)))
            self.history_table.setItem(0, 5, QTableWidgetItem(str(pnl)))
            self.history_table.setItem(0, 6, QTableWidgetItem(f"{confidence:.1%}"))
            
            # Ограничиваем количество строк в истории
            if self.history_table.rowCount() > 100:
                self.history_table.removeRow(100)
            
            # Обновление статистики
            self.update_trading_stats()
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка добавления в историю: {e}")
    
    def update_trading_stats(self):
        """Обновление статистики торговли"""
        try:
            today = datetime.now().date()
            today_trades = [
                trade for trade in self.trade_history
                if datetime.fromisoformat(trade.get('timestamp', '')).date() == today
            ]
            
            trades_count = len(today_trades)
            self.trades_count_label.setText(str(trades_count))
            
            if trades_count > 0:
                # Подсчет прибыльных сделок (упрощенно)
                profitable_trades = sum(1 for trade in today_trades if trade.get('side') == 'Buy')
                win_rate = (profitable_trades / trades_count) * 100
                self.win_rate_label.setText(f"{win_rate:.1f}%")
                
                # Дневной объем
                daily_volume = sum(float(trade.get('size', 0)) for trade in today_trades)
                self.daily_volume_label.setText(f"${daily_volume:.2f}")
            else:
                self.win_rate_label.setText("0%")
                self.daily_volume_label.setText("$0.00")
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления статистики: {e}")
            
    def buy_cheapest_position(self):
        """Покупка самой дешевой позиции"""
        try:
            if not self.current_positions:
                self.add_log_message("⚠️ Нет доступных позиций для покупки")
                return
                
            # Получаем историю цен для всех символов
            price_history = {}
            try:
                all_price_history = self.db_manager.get_price_history()
                for ph in all_price_history:
                    price_history[ph[1]] = ph  # Индекс 1 - это symbol
            except Exception as e:
                self.add_log_message(f"⚠️ Ошибка получения истории цен: {e}")
                return
                
            # Находим самую дешевую позицию
            cheapest_symbol = None
            lowest_price = float('inf')
            
            for position in self.current_positions:
                symbol = position.get('symbol', '')
                if symbol in price_history:
                    current_price = price_history[symbol][2]  # Индекс 2 - текущая цена
                    if current_price < lowest_price:
                        lowest_price = current_price
                        cheapest_symbol = symbol
            
            if not cheapest_symbol:
                self.add_log_message("⚠️ Не удалось найти самую дешевую позицию")
                return
                
            # Запрос подтверждения
            reply = QMessageBox.question(
                self, 
                "Подтверждение покупки", 
                f"Вы уверены, что хотите купить {cheapest_symbol} по цене ${lowest_price:.6f}?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Здесь будет вызов API для покупки
                self.add_log_message(f"🔄 Отправка запроса на покупку {cheapest_symbol}...")
                
                # Имитация успешной покупки (в реальном приложении здесь будет вызов API)
                trade_info = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': cheapest_symbol,
                    'side': 'Buy',
                    'size': 0.01,  # Фиксированный размер для примера
                    'price': lowest_price,
                    'pnl': 'N/A',
                    'analysis': {'confidence': 0.75}
                }
                
                # Добавляем в историю
                self.add_trade_to_history(trade_info)
                self.add_log_message(f"✅ Успешно куплено {cheapest_symbol} по цене ${lowest_price:.6f}")
            else:
                self.add_log_message("❌ Покупка отменена пользователем")
                
        except Exception as e:
            self.add_log_message(f"❌ Ошибка при покупке: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
    
    def sell_cheapest_position(self):
        """Продажа самой дешевой позиции"""
        try:
            if not self.current_positions:
                self.add_log_message("⚠️ Нет доступных позиций для продажи")
                return
                
            # Получаем историю цен для всех символов
            price_history = {}
            try:
                all_price_history = self.db_manager.get_price_history()
                for ph in all_price_history:
                    price_history[ph[1]] = ph  # Индекс 1 - это symbol
            except Exception as e:
                self.add_log_message(f"⚠️ Ошибка получения истории цен: {e}")
                return
                
            # Находим самую дешевую позицию
            cheapest_symbol = None
            lowest_price = float('inf')
            
            for position in self.current_positions:
                symbol = position.get('symbol', '')
                if symbol in price_history:
                    current_price = price_history[symbol][2]  # Индекс 2 - текущая цена
                    if current_price < lowest_price:
                        lowest_price = current_price
                        cheapest_symbol = symbol
            
            if not cheapest_symbol:
                self.add_log_message("⚠️ Не удалось найти самую дешевую позицию")
                return
                
            # Запрос подтверждения
            reply = QMessageBox.question(
                self, 
                "Подтверждение продажи", 
                f"Вы уверены, что хотите продать {cheapest_symbol} по цене ${lowest_price:.6f}?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Здесь будет вызов API для продажи
                self.add_log_message(f"🔄 Отправка запроса на продажу {cheapest_symbol}...")
                
                # Имитация успешной продажи (в реальном приложении здесь будет вызов API)
                trade_info = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': cheapest_symbol,
                    'side': 'Sell',
                    'size': 0.01,  # Фиксированный размер для примера
                    'price': lowest_price,
                    'pnl': '+$0.05',  # Фиксированный PnL для примера
                    'analysis': {'confidence': 0.75}
                }
                
                # Добавляем в историю
                self.add_trade_to_history(trade_info)
                self.add_log_message(f"✅ Успешно продано {cheapest_symbol} по цене ${lowest_price:.6f}")
            else:
                self.add_log_message("❌ Продажа отменена пользователем")
                
        except Exception as e:
            self.add_log_message(f"❌ Ошибка при продаже: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
    
    def add_log_message(self, message: str):
        """Добавление сообщения в лог"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}"
        
        self.logs_text.append(formatted_message)
        
        # Автопрокрутка к последнему сообщению
        cursor = self.logs_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.logs_text.setTextCursor(cursor)
    
    def handle_error(self, error_message: str):
        """Обработка ошибок"""
        self.add_log_message(f"❌ ОШИБКА: {error_message}")
        
        # Показываем критические ошибки в диалоге
        if "Критическая" in error_message:
            QMessageBox.critical(self, "Критическая ошибка", error_message)
    
    def update_connection_status(self, status: str):
        """Обновление статуса подключения"""
        if status == "Подключено":
            self.connection_status.setText("🟢 Подключено")
            self.connection_status.setStyleSheet(
                "QLabel { color: #27ae60; font-weight: bold; font-size: 14px; }"
            )
            self.trading_toggle_btn.setEnabled(True)
        elif status == "Инициализация...":
            self.connection_status.setText("🟡 Подключение...")
            self.connection_status.setStyleSheet(
                "QLabel { color: #f39c12; font-weight: bold; font-size: 14px; }"
            )
        else:
            self.connection_status.setText("🔴 Отключено")
            self.connection_status.setStyleSheet(
                "QLabel { color: #e74c3c; font-weight: bold; font-size: 14px; }"
            )
            self.trading_toggle_btn.setEnabled(False)
        
        self.status_label.setText(f"Статус: {status}")
    
    def toggle_trading(self):
        """Переключение торговли"""
        if self.trading_worker:
            current_state = self.trading_worker.trading_enabled
            new_state = not current_state
            
            self.trading_worker.enable_trading(new_state)
            
            if new_state:
                self.trading_toggle_btn.setText("⏸️ Остановить торговлю")
                self.trading_toggle_btn.setStyleSheet(
                    "QPushButton { background-color: #e74c3c; color: white; font-weight: bold; padding: 10px; }"
                )
                self.add_log_message("🟢 Торговля включена")
            else:
                self.trading_toggle_btn.setText("▶️ Включить торговлю")
                self.trading_toggle_btn.setStyleSheet(
                    "QPushButton { background-color: #27ae60; color: white; font-weight: bold; padding: 10px; }"
                )
                self.add_log_message("🔴 Торговля выключена")
    
    def emergency_stop(self):
        """Экстренная остановка всех операций"""
        reply = QMessageBox.question(
            self, "Экстренная остановка",
            "Вы уверены, что хотите экстренно остановить все торговые операции?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.trading_worker:
                self.trading_worker.stop()
            
            self.add_log_message("🛑 ЭКСТРЕННАЯ ОСТАНОВКА АКТИВИРОВАНА")
            
            # Обновление UI
            self.trading_toggle_btn.setText("▶️ Включить торговлю")
            self.trading_toggle_btn.setStyleSheet(
                "QPushButton { background-color: #27ae60; color: white; font-weight: bold; padding: 10px; }"
            )
            self.update_connection_status("Отключено")
    
    def refresh_data(self):
        """Принудительное обновление всех данных"""
        self.add_log_message("🔄 Принудительное обновление данных...")
        
        # Запускаем обновление данных в отдельном потоке
        threading.Thread(target=self._refresh_data_thread, daemon=True).start()
        
    def refresh_positions(self):
        """Принудительное обновление только позиций"""
        self.add_log_message("🔄 Обновление позиций...")
        
        # Запускаем обновление позиций в отдельном потоке
        threading.Thread(target=self._refresh_positions_thread, daemon=True).start()
    
    def _refresh_positions_thread(self):
        """Выполнение обновления только позиций в отдельном потоке"""
        try:
            # Проверяем, что клиент API инициализирован
            if not hasattr(self, 'bybit_client') or not self.bybit_client:
                self.add_log_message("❌ Невозможно обновить позиции: API клиент не инициализирован")
                return
                
            # Обновляем позиции
            self.add_log_message("🔄 Получение данных о позициях...")
            try:
                # Получаем позиции по поддерживаемым категориям
                all_positions = []
                categories = ["linear", "inverse"]
                
                for category in categories:
                    try:
                        # Получаем реальные данные через API с указанием settleCoin=USDT для linear категории
                        settle_coin = "USDT" if category == "linear" else None
                        positions_list = self.bybit_client.get_positions(category=category, settle_coin=settle_coin)
                        
                        # Проверяем, что получили список позиций
                        if positions_list and isinstance(positions_list, list):
                            # Добавляем категорию к каждой позиции для идентификации
                            for pos in positions_list:
                                pos['category'] = category
                            all_positions.extend(positions_list)
                    except Exception as e:
                        self.add_log_message(f"⚠️ Ошибка получения позиций {category}: {e}")
                        continue
                
                # Фильтруем только активные позиции (с размером > 0)
                active_positions = []
                for pos in all_positions:
                    size = float(pos.get('size', 0))
                    if size > 0:
                        active_positions.append(pos)
                
                # Обновляем таблицу позиций через сигнал
                QMetaObject.invokeMethod(self, "update_positions", 
                                       Qt.QueuedConnection,
                                       Q_ARG(list, active_positions))
                
                self.add_log_message(f"✅ Позиции успешно обновлены: {len(active_positions)}")
                
            except Exception as pos_err:
                self.add_log_message(f"❌ Ошибка обновления позиций: {pos_err}")
                import traceback
                self.add_log_message(f"Детали: {traceback.format_exc()}")
                
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления позиций: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
            self.logger.error(f"Ошибка обновления позиций: {e}")
            self.logger.error(traceback.format_exc())
    
    def _refresh_data_thread(self):
        """Выполнение обновления всех данных в отдельном потоке"""
        try:
            # Проверяем, что клиент API инициализирован
            if not hasattr(self, 'bybit_client') or not self.bybit_client:
                self.add_log_message("❌ Невозможно обновить данные: API клиент не инициализирован")
                return
                
            # Получаем данные о балансе через API
            balance_response = self.bybit_client.get_wallet_balance()
            
            if balance_response and balance_response.get('list'):
                # Извлекаем данные из структуры ответа API
                balance_data = balance_response['list'][0]
                
                # Создаем структуру для обновления UI
                balance_info = {
                    'totalWalletBalance': balance_data.get('totalWalletBalance', '0'),
                    'totalAvailableBalance': balance_data.get('totalAvailableBalance', '0'),
                    'totalEquity': balance_data.get('totalEquity', '0'),
                    'totalPerpUPL': balance_data.get('totalPerpUPL', '0'),
                    'coins': balance_data.get('coin', [])
                }
                
                # Обновляем интерфейс баланса через сигнал
                QMetaObject.invokeMethod(self, "update_balance", 
                                       Qt.QueuedConnection,
                                       Q_ARG(dict, balance_info))
                
                # Обновляем позиции
                self.add_log_message("🔄 Обновление позиций...")
                try:
                    # Получаем позиции по поддерживаемым категориям
                    all_positions = []
                    categories = ["linear", "inverse"]
                    
                    for category in categories:
                        try:
                            # Получаем реальные данные через API с указанием settleCoin=USDT для linear категории
                            settle_coin = "USDT" if category == "linear" else None
                            positions_list = self.bybit_client.get_positions(category=category, settle_coin=settle_coin)
                            
                            # Проверяем, что получили список позиций
                            if positions_list and isinstance(positions_list, list):
                                # Добавляем категорию к каждой позиции для идентификации
                                for pos in positions_list:
                                    pos['category'] = category
                                all_positions.extend(positions_list)
                        except Exception as e:
                            self.add_log_message(f"⚠️ Ошибка получения позиций {category}: {e}")
                            continue
                    
                    # Фильтруем только активные позиции (с размером > 0)
                    active_positions = []
                    for pos in all_positions:
                        size = float(pos.get('size', 0))
                        if size > 0:
                            active_positions.append(pos)
                    
                    # Обновляем таблицу позиций через сигнал
                    QMetaObject.invokeMethod(self, "update_positions", 
                                           Qt.QueuedConnection,
                                           Q_ARG(list, active_positions))
                    
                except Exception as pos_err:
                    self.add_log_message(f"❌ Ошибка обновления позиций: {pos_err}")
                
                self.add_log_message("✅ Данные успешно обновлены")
            else:
                self.add_log_message("⚠️ Получен пустой ответ от API")
                
        except Exception as e:
            self.add_log_message(f"❌ Ошибка обновления данных: {e}")
            import traceback
            self.add_log_message(f"Детали: {traceback.format_exc()}")
            self.logger.error(f"Ошибка обновления данных: {e}")
            self.logger.error(traceback.format_exc())
    
    def test_api_keys(self):
        """Проверка API ключей"""
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        
        if not api_key or not api_secret:
            self.api_status_label.setText("❌ Введите API ключи")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            return
        
        # Изменение статуса на время проверки
        self.api_status_label.setText("⏳ Проверка ключей...")
        self.api_status_label.setStyleSheet("QLabel { color: #3498db; font-weight: bold; }")
        QApplication.processEvents()
        
        try:
            # Создаем временный клиент для проверки ключей
            from config import USE_TESTNET
            client = BybitClient(api_key, api_secret, testnet=USE_TESTNET)
            # Пробуем получить баланс для проверки работоспособности ключей
            balance = client.get_wallet_balance()
            
            if balance:
                self.api_status_label.setText("✅ API ключи работают")
                self.api_status_label.setStyleSheet("QLabel { color: #27ae60; font-weight: bold; }")
                self.add_log_message("API ключи успешно проверены")
            else:
                self.api_status_label.setText("❌ Не удалось получить баланс")
                self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
                self.add_log_message("Ошибка проверки API ключей: не удалось получить баланс")
        except Exception as e:
            self.api_status_label.setText(f"❌ Ошибка: {str(e)[:50]}")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            self.add_log_message(f"Ошибка проверки API ключей: {str(e)}")
    
    def save_api_keys(self):
        """Сохранение API ключей"""
        api_key = self.api_key_input.text().strip()
        api_secret = self.api_secret_input.text().strip()
        
        if not api_key or not api_secret:
            self.api_status_label.setText("❌ Введите API ключи для сохранения")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            return
        
        try:
            # Путь к файлу config.py
            config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.py')
            
            # Чтение текущего содержимого файла
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Замена значений API ключей
            content = re.sub(r'API_KEY\s*=\s*"[^"]*"', f'API_KEY = "{api_key}"', content)
            content = re.sub(r'API_SECRET\s*=\s*"[^"]*"', f'API_SECRET = "{api_secret}"', content)
            
            # Запись обновленного содержимого
            with open(config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Обновляем клиент с новыми ключами
            self.api_key = api_key
            self.api_secret = api_secret
            # Используем значение USE_TESTNET из конфигурации
            from config import USE_TESTNET
            self.bybit_client = BybitClient(api_key, api_secret, testnet=USE_TESTNET)
            
            self.api_status_label.setText("✅ API ключи сохранены")
            self.api_status_label.setStyleSheet("QLabel { color: #27ae60; font-weight: bold; }")
            self.add_log_message("API ключи успешно сохранены")
            
            # Пробуем подключиться с новыми ключами
            self.connect_to_exchange()
        except Exception as e:
            self.api_status_label.setText(f"❌ Ошибка сохранения: {str(e)[:50]}")
            self.api_status_label.setStyleSheet("QLabel { color: #e74c3c; font-weight: bold; }")
            self.add_log_message(f"Ошибка сохранения API ключей: {str(e)}")
    
    def check_api_connection(self):
        """Проверка статуса подключения к API"""
        self.logger.info("Проверка статуса подключения к API...")
        return self.connect_to_exchange()
    
    def connect_to_exchange(self):
        """Подключение к бирже и обновление статуса соединения"""
        try:
            if not self.bybit_client:
                self.add_log_message("❌ Клиент API не инициализирован")
                self.update_connection_status(False)
                return False
            
            # Проверяем соединение, запрашивая баланс
            balance = self.bybit_client.get_wallet_balance()
            
            if balance:
                self.update_connection_status(True)
                self.add_log_message("✅ Успешное подключение к бирже")
                
                # Обновляем баланс
                self.update_balance(balance)
                
                # Разблокируем кнопку торговли
                self.trading_toggle_btn.setEnabled(True)
                
                # Обновляем данные
                self.refresh_data()
                
                return True
            else:
                self.update_connection_status(False)
                self.add_log_message("❌ Не удалось получить баланс")
                return False
                
        except Exception as e:
            self.update_connection_status(False)
            self.add_log_message(f"❌ Ошибка подключения к бирже: {str(e)}")
            return False
    
    def clear_logs(self):
        """Очистка логов"""
        self.logs_text.clear()
        self.add_log_message("🗑️ Логи очищены")
    
    def export_logs(self):
        """Экспорт логов в файл"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"trading_logs_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.logs_text.toPlainText())
            
            self.add_log_message(f"💾 Логи экспортированы в {filename}")
            
        except Exception as e:
            self.add_log_message(f"❌ Ошибка экспорта логов: {e}")
    
    def get_cheapest_asset(self):
        """Получение самого дешевого актива из всех доступных"""
        try:
            if not self.bybit_client:
                return None, None
            
            # Получаем все доступные торговые символы
            symbols = self._get_all_available_symbols()
            
            if not symbols:
                self.logger.warning("Не удалось получить список символов для поиска самого дешевого актива")
                return None, None
            
            cheapest_symbol = None
            cheapest_price = float('inf')
            processed_count = 0
            
            self.logger.info(f"Поиск самого дешевого актива среди {len(symbols)} символов...")
            
            # Ограничиваем количество запросов для производительности (первые 100 символов)
            symbols_to_check = symbols[:100] if len(symbols) > 100 else symbols
            
            for symbol in symbols_to_check:
                try:
                    ticker = self.bybit_client.get_tickers(symbol)
                    if ticker and 'list' in ticker and ticker['list']:
                        price = float(ticker['list'][0].get('lastPrice', 0))
                        if 0 < price < cheapest_price:
                            cheapest_price = price
                            cheapest_symbol = symbol
                        processed_count += 1
                except Exception as e:
                    self.logger.debug(f"Ошибка получения цены для {symbol}: {e}")
                    continue
            
            self.logger.info(f"Обработано {processed_count} символов, найден самый дешевый: {cheapest_symbol} по цене {cheapest_price}")
            return cheapest_symbol, cheapest_price
            
        except Exception as e:
            self.logger.error(f"Ошибка поиска самого дешевого актива: {e}")
            return None, None
    
    def buy_cheapest_asset(self):
        """Покупка самого дешевого актива с подтверждением"""
        try:
            # Получаем самый дешевый актив
            symbol, price = self.get_cheapest_asset()
            
            if not symbol or not price:
                QMessageBox.warning(self, "Ошибка", "Не удалось найти доступные активы для покупки")
                return
            
            # Окно подтверждения
            reply = QMessageBox.question(
                self, "Подтверждение покупки",
                f"Вы хотите купить 1 единицу актива {symbol}?\n\n"
                f"💰 Цена: ${price:.6f}\n"
                f"💵 Общая стоимость: ~${price:.6f}\n\n"
                f"⚠️ Это реальная торговая операция!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Выполняем покупку
                order_result = self.bybit_client.place_order(
                    symbol=symbol,
                    side='Buy',
                    order_type='Market',
                    qty='1'
                )
                
                if order_result:
                    self.add_log_message(f"✅ Покупка выполнена: {symbol} за ${price:.6f}")
                    QMessageBox.information(self, "Успех", f"Покупка {symbol} успешно выполнена!")
                else:
                    self.add_log_message(f"❌ Ошибка покупки {symbol}")
                    QMessageBox.warning(self, "Ошибка", "Не удалось выполнить покупку")
            
        except Exception as e:
            error_msg = f"Ошибка при покупке актива: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
            QMessageBox.critical(self, "Ошибка", error_msg)
    
    def sell_cheapest_asset(self):
        """Продажа самого дешевого актива с подтверждением"""
        try:
            # Получаем самый дешевый актив
            symbol, price = self.get_cheapest_asset()
            
            if not symbol or not price:
                QMessageBox.warning(self, "Ошибка", "Не удалось найти доступные активы для продажи")
                return
            
            # Проверяем наличие позиции для продажи
            positions = self.bybit_client.get_positions()
            has_position = False
            
            if positions:
                for pos in positions:
                    if pos.get('symbol') == symbol and float(pos.get('size', 0)) >= 1:
                        has_position = True
                        break
            
            if not has_position:
                QMessageBox.warning(
                    self, "Недостаточно активов", 
                    f"У вас нет достаточного количества {symbol} для продажи"
                )
                return
            
            # Окно подтверждения
            reply = QMessageBox.question(
                self, "Подтверждение продажи",
                f"Вы хотите продать 1 единицу актива {symbol}?\n\n"
                f"💰 Цена: ${price:.6f}\n"
                f"💵 Общая сумма: ~${price:.6f}\n\n"
                f"⚠️ Это реальная торговая операция!",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Выполняем продажу
                order_result = self.bybit_client.place_order(
                    symbol=symbol,
                    side='Sell',
                    order_type='Market',
                    qty='1'
                )
                
                if order_result:
                    self.add_log_message(f"✅ Продажа выполнена: {symbol} за ${price:.6f}")
                    QMessageBox.information(self, "Успех", f"Продажа {symbol} успешно выполнена!")
                else:
                    self.add_log_message(f"❌ Ошибка продажи {symbol}")
                    QMessageBox.warning(self, "Ошибка", "Не удалось выполнить продажу")
            
        except Exception as e:
            error_msg = f"Ошибка при продаже актива: {e}"
            self.logger.error(error_msg)
            self.add_log_message(f"❌ {error_msg}")
            QMessageBox.critical(self, "Ошибка", error_msg)
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        reply = QMessageBox.question(
            self, "Выход",
            "Вы уверены, что хотите закрыть торгового бота?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Остановка торгового потока
            if self.trading_worker:
                self.trading_worker.stop()
                self.trading_worker.wait(5000)  # Ждем 5 секунд
            
            event.accept()
        else:
            event.ignore()


def main():
    """Главная функция приложения"""
    app = QApplication(sys.argv)
    
    # Настройка приложения
    app.setApplicationName("Торговый Бот Bybit")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Trading Bot")
    
    # Создание и показ главного окна
    window = TradingBotMainWindow()
    window.show()
    
    # Запуск приложения
    sys.exit(app.exec())


if __name__ == "__main__":
    main()