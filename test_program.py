#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Отдельная программа для тестирования торгового бота

Включает:
- Собственную базу данных для тестирования
- Ручное тестирование стратегий
- Симуляцию торговых операций
- Анализ результатов
"""

import sys
import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Добавляем путь к основному проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QGroupBox,
    QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QProgressBar, QMessageBox, QSplitter, QTabWidget, QFormLayout,
    QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QIcon

# Импорт компонентов основного проекта
from src.core.config_manager import ConfigManager
from src.core.logger import setup_logging
from src.database.db_manager import DatabaseManager
from src.strategies import (
    AVAILABLE_STRATEGIES, STRATEGY_METADATA,
    get_strategy_class, get_strategy_metadata
)

# Импорт модуля симуляции
from test_simulation import MarketSimulator, TradeSimulator, PerformanceAnalyzer

class TestDatabaseManager:
    """
    Менеджер тестовой базы данных
    """
    
    def __init__(self, db_path: str = "test_trading_bot.db"):
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)
        self.logger = logging.getLogger(__name__)
        
    def initialize_test_db(self):
        """
        Инициализация тестовой базы данных
        """
        try:
            # Используем стандартную инициализацию DatabaseManager
            self.db_manager.initialize_database()
            self.logger.info("Тестовая база данных инициализирована")
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации тестовой БД: {e}")
            return False
    
    def save_test_trade(self, trade_data: Dict[str, Any]):
        """
        Сохранение тестовой сделки
        """
        try:
            # Используем метод log_trade из DatabaseManager
            formatted_trade = {
                'order_id': f"test_{datetime.now().timestamp()}_{trade_data.get('symbol', '')}",
                'symbol': trade_data.get('symbol', ''),
                'side': trade_data.get('side', '').upper(),
                'order_type': 'MARKET',
                'quantity': trade_data.get('quantity', 0.0),
                'price': trade_data.get('price', 0.0),
                'executed_price': trade_data.get('price', 0.0),
                'executed_quantity': trade_data.get('quantity', 0.0),
                'status': 'FILLED',
                'strategy_name': trade_data.get('strategy_name', ''),
                'profit_loss': trade_data.get('profit_loss', 0.0),
                'commission': trade_data.get('fee', 0.0),
                'environment': 'test',
                'additional_data': {
                    'test_status': trade_data.get('status', 'simulated'),
                    'confidence': trade_data.get('confidence', 0.0)
                }
            }
            
            self.db_manager.log_trade(formatted_trade)
            self.logger.info(f"Тестовая сделка сохранена: {trade_data}")
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения тестовой сделки: {e}")
    
    def save_test_result(self, result_data: Dict[str, Any]):
        """
        Сохранение результата тестирования
        """
        try:
            # Используем метод log_performance из DatabaseManager
            performance_data = {
                'strategy_name': result_data.get('strategy_name', ''),
                'total_trades': result_data.get('total_trades', 0),
                'profitable_trades': result_data.get('profitable_trades', 0),
                'total_profit': result_data.get('total_profit', 0.0),
                'total_loss': abs(result_data.get('max_drawdown', 0.0)),
                'win_rate': result_data.get('win_rate', 0.0),
                'max_drawdown': result_data.get('max_drawdown', 0.0),
                'sharpe_ratio': 0.0,  # Будет рассчитан позже
                'environment': 'test',
                'additional_metrics': {
                    'test_name': result_data.get('test_name', ''),
                    'start_time': str(result_data.get('start_time', '')),
                    'end_time': str(result_data.get('end_time', '')),
                    'notes': result_data.get('notes', '')
                }
            }
            
            self.db_manager.log_performance(performance_data)
            self.logger.info(f"Результат тестирования сохранен: {result_data.get('test_name', 'Unknown')}")
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения результата тестирования: {e}")
    
    def get_test_trades(self, strategy_name: Optional[str] = None) -> list:
        """
        Получение тестовых сделок
        """
        try:
            with self.db_manager.get_session() as session:
                from src.database.db_manager import TradeEntry
                
                query = session.query(TradeEntry).filter(
                    TradeEntry.environment == 'test'
                )
                
                if strategy_name:
                    query = query.filter(TradeEntry.strategy_name == strategy_name)
                
                results = query.order_by(TradeEntry.timestamp.desc()).all()
                
                return [{
                    'id': result.id,
                    'strategy_name': result.strategy_name,
                    'symbol': result.symbol,
                    'side': result.side,
                    'quantity': result.executed_quantity or result.quantity,
                    'price': result.executed_price or result.price,
                    'timestamp': result.timestamp,
                    'profit_loss': result.profit_loss,
                    'status': result.additional_data.get('test_status', 'simulated') if result.additional_data else 'simulated'
                } for result in results]
                
        except Exception as e:
            self.logger.error(f"Ошибка получения тестовых сделок: {e}")
            return []
    
    def get_test_results(self) -> list:
        """
        Получение результатов тестирования
        """
        try:
            with self.db_manager.get_session() as session:
                from src.database.db_manager import PerformanceEntry
                
                results = session.query(PerformanceEntry).filter(
                    PerformanceEntry.environment == 'test'
                ).order_by(PerformanceEntry.timestamp.desc()).all()
                
                return [{
                    'id': result.id,
                    'test_name': result.additional_metrics.get('test_name', f'Test_{result.id}') if result.additional_metrics else f'Test_{result.id}',
                    'strategy_name': result.strategy_name,
                    'start_time': result.additional_metrics.get('start_time', '') if result.additional_metrics else '',
                    'end_time': result.additional_metrics.get('end_time', '') if result.additional_metrics else '',
                    'total_trades': result.total_trades,
                    'profitable_trades': result.profitable_trades,
                    'total_profit': result.total_profit,
                    'max_drawdown': result.max_drawdown,
                    'win_rate': result.win_rate,
                    'notes': result.additional_metrics.get('notes', '') if result.additional_metrics else ''
                } for result in results]
            
        except Exception as e:
            self.logger.error(f"Ошибка получения результатов тестирования: {e}")
            return []

class StrategyTestWorker(QThread):
    """
    Воркер для тестирования стратегий
    """
    
    test_progress = Signal(int)  # прогресс в процентах
    test_result = Signal(dict)   # результат тестирования
    trade_executed = Signal(dict)  # выполненная сделка
    
    def __init__(self, strategy_name: str, test_params: Dict[str, Any]):
        super().__init__()
        self.strategy_name = strategy_name
        self.test_params = test_params
        self.is_running = False
        
        # Инициализация симуляторов с параметрами
        self.market_sim = MarketSimulator("test_config.json")
        self.trade_sim = TradeSimulator(self.market_sim)
        self.analyzer = PerformanceAnalyzer()
        
        # Параметры симуляции
        self.simulation_speed_ms = test_params.get('simulation_speed_ms', 50)
        self.volatility_factor = test_params.get('volatility_factor', 0.02)
        self.selected_symbols = test_params.get('selected_symbols', ['BTCUSDT'])
        
    def run(self):
        """
        Запуск тестирования стратегии
        """
        self.is_running = True
        
        try:
            # Параметры тестирования
            total_steps = self.test_params.get('duration', 100)
            initial_balance = self.test_params.get('initial_balance', 10000.0)
            simulation_speed = self.test_params.get('simulation_speed_ms', 50)
            
            trades = []
            start_time = datetime.now()
            
            # Используем выбранные символы для тестирования
            symbols = self.selected_symbols
            
            # Устанавливаем волатильность для симулятора
            self.market_sim.set_volatility(self.volatility_factor)
            
            for step in range(total_steps):
                if not self.is_running:
                    break
                
                # Обновляем рыночные условия
                self.market_sim.update_market_trend()
                
                # Тестируем стратегию на каждом выбранном символе
                for symbol in symbols:
                    # Генерируем новое движение цены с учетом волатильности
                    self.market_sim.generate_price_movement(symbol, volatility=self.volatility_factor)
                    
                    # Получаем сигнал от стратегии
                    signal = self.trade_sim.simulate_strategy_signal(self.strategy_name, symbol)
                    
                    if signal:
                        # Выполняем сделку
                        trade = self.trade_sim.execute_trade(signal, symbol, self.strategy_name)
                        trades.append(trade)
                        
                        # Отправляем сигнал о выполненной сделке
                        self.trade_executed.emit(trade)
                
                # Имитация времени выполнения с учетом скорости симуляции
                self.msleep(self.simulation_speed_ms)
                
                # Обновляем прогресс
                progress = int((step + 1) / total_steps * 100)
                self.test_progress.emit(progress)
            
            end_time = datetime.now()
            
            # Анализируем результаты с помощью PerformanceAnalyzer
            analysis = self.analyzer.analyze_trades(trades)
            
            # Формируем результат тестирования
            result = {
                'test_name': f"Test_{self.strategy_name}_{start_time.strftime('%Y%m%d_%H%M%S')}",
                'strategy_name': self.strategy_name,
                'start_time': start_time,
                'end_time': end_time,
                'total_trades': analysis['total_trades'],
                'profitable_trades': analysis['profitable_trades'],
                'total_profit': analysis['net_profit'],
                'max_drawdown': analysis['max_drawdown'],
                'win_rate': analysis['win_rate'],
                'notes': f"Тестирование завершено за {(end_time - start_time).total_seconds():.1f} сек. "
                        f"Sharpe: {analysis['sharpe_ratio']}, Profit Factor: {analysis['profit_factor']}"
            }
            
            self.test_result.emit(result)
            
        except Exception as e:
            error_result = {
                'test_name': f"Error_{self.strategy_name}",
                'strategy_name': self.strategy_name,
                'start_time': datetime.now(),
                'end_time': datetime.now(),
                'total_trades': 0,
                'profitable_trades': 0,
                'total_profit': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'notes': f"Ошибка тестирования: {str(e)}"
            }
            self.test_result.emit(error_result)
    
    def stop(self):
        """
        Остановка тестирования
        """
        self.is_running = False

class TestProgramMainWindow(QMainWindow):
    """
    Главное окно программы тестирования
    """
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Bybit Trading Bot - Программа тестирования")
        self.setGeometry(100, 100, 1200, 800)
        
        # Инициализация компонентов
        self.test_db = TestDatabaseManager()
        self.test_worker = None
        self.logger = logging.getLogger(__name__)
        
        # Инициализация интерфейса
        self._init_ui()
        
        # Инициализация тестовой БД
        if not self.test_db.initialize_test_db():
            QMessageBox.critical(self, "Ошибка", "Не удалось инициализировать тестовую базу данных")
    
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Создаем вкладки
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # Вкладка тестирования стратегий
        self.strategy_test_tab = self._create_strategy_test_tab()
        tab_widget.addTab(self.strategy_test_tab, "Тестирование стратегий")
        
        # Вкладка результатов
        self.results_tab = self._create_results_tab()
        tab_widget.addTab(self.results_tab, "Результаты тестов")
        
        # Вкладка сделок
        self.trades_tab = self._create_trades_tab()
        tab_widget.addTab(self.trades_tab, "Тестовые сделки")
    
    def _create_strategy_test_tab(self) -> QWidget:
        """
        Создание вкладки тестирования стратегий
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Группа настроек тестирования
        settings_group = QGroupBox("Настройки тестирования")
        settings_layout = QFormLayout(settings_group)
        
        # Выбор стратегии
        self.strategy_combo = QComboBox()
        for strategy_key in AVAILABLE_STRATEGIES.keys():
            metadata = get_strategy_metadata(strategy_key)
            self.strategy_combo.addItem(f"{metadata['name']} ({strategy_key})", strategy_key)
        settings_layout.addRow("Стратегия:", self.strategy_combo)
        
        # Параметры тестирования
        self.test_duration_spin = QSpinBox()
        self.test_duration_spin.setRange(1, 10000)
        self.test_duration_spin.setValue(100)
        self.test_duration_spin.setSuffix(" шагов")
        settings_layout.addRow("Длительность теста:", self.test_duration_spin)
        
        self.initial_balance_spin = QDoubleSpinBox()
        self.initial_balance_spin.setRange(100, 100000)
        self.initial_balance_spin.setValue(10000)
        self.initial_balance_spin.setSuffix(" USDT")
        settings_layout.addRow("Начальный баланс:", self.initial_balance_spin)
        
        # Дополнительные параметры симуляции
        self.simulation_speed_spin = QSpinBox()
        self.simulation_speed_spin.setRange(10, 1000)
        self.simulation_speed_spin.setValue(50)
        self.simulation_speed_spin.setSuffix(" мс")
        settings_layout.addRow("Скорость симуляции:", self.simulation_speed_spin)
        
        self.volatility_spin = QDoubleSpinBox()
        self.volatility_spin.setRange(0.001, 0.1)
        self.volatility_spin.setValue(0.02)
        self.volatility_spin.setDecimals(3)
        self.volatility_spin.setSingleStep(0.001)
        settings_layout.addRow("Волатильность рынка:", self.volatility_spin)
        
        # Выбор символов для тестирования
        symbols_layout = QHBoxLayout()
        self.btc_checkbox = QCheckBox("BTCUSDT")
        self.btc_checkbox.setChecked(True)
        self.eth_checkbox = QCheckBox("ETHUSDT")
        self.eth_checkbox.setChecked(True)
        self.ada_checkbox = QCheckBox("ADAUSDT")
        self.dot_checkbox = QCheckBox("DOTUSDT")
        self.link_checkbox = QCheckBox("LINKUSDT")
        
        symbols_layout.addWidget(self.btc_checkbox)
        symbols_layout.addWidget(self.eth_checkbox)
        symbols_layout.addWidget(self.ada_checkbox)
        symbols_layout.addWidget(self.dot_checkbox)
        symbols_layout.addWidget(self.link_checkbox)
        symbols_layout.addStretch()
        
        symbols_widget = QWidget()
        symbols_widget.setLayout(symbols_layout)
        settings_layout.addRow("Торговые пары:", symbols_widget)
        
        layout.addWidget(settings_group)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.start_test_button = QPushButton("Запустить тест")
        self.start_test_button.clicked.connect(self._start_test)
        buttons_layout.addWidget(self.start_test_button)
        
        self.stop_test_button = QPushButton("Остановить тест")
        self.stop_test_button.clicked.connect(self._stop_test)
        self.stop_test_button.setEnabled(False)
        buttons_layout.addWidget(self.stop_test_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        # Прогресс тестирования
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Лог тестирования
        log_group = QGroupBox("Лог тестирования")
        log_layout = QVBoxLayout(log_group)
        
        self.test_log = QTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setMaximumHeight(200)
        log_layout.addWidget(self.test_log)
        
        layout.addWidget(log_group)
        
        return widget
    
    def _create_results_tab(self) -> QWidget:
        """
        Создание вкладки результатов
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Кнопка обновления
        refresh_button = QPushButton("Обновить результаты")
        refresh_button.clicked.connect(self._refresh_results)
        layout.addWidget(refresh_button)
        
        # Таблица результатов
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(9)
        self.results_table.setHorizontalHeaderLabels([
            "Название теста", "Стратегия", "Время начала", "Время окончания",
            "Всего сделок", "Прибыльных", "Общая прибыль", "Просадка", "Win Rate %"
        ])
        
        header = self.results_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        
        layout.addWidget(self.results_table)
        
        return widget
    
    def _create_trades_tab(self) -> QWidget:
        """
        Создание вкладки сделок
        """
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Фильтры
        filters_layout = QHBoxLayout()
        
        filters_layout.addWidget(QLabel("Фильтр по стратегии:"))
        self.trades_filter_combo = QComboBox()
        self.trades_filter_combo.addItem("Все стратегии", None)
        for strategy_key in AVAILABLE_STRATEGIES.keys():
            metadata = get_strategy_metadata(strategy_key)
            self.trades_filter_combo.addItem(metadata['name'], strategy_key)
        self.trades_filter_combo.currentTextChanged.connect(self._refresh_trades)
        filters_layout.addWidget(self.trades_filter_combo)
        
        refresh_trades_button = QPushButton("Обновить")
        refresh_trades_button.clicked.connect(self._refresh_trades)
        filters_layout.addWidget(refresh_trades_button)
        
        filters_layout.addStretch()
        layout.addLayout(filters_layout)
        
        # Таблица сделок
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(8)
        self.trades_table.setHorizontalHeaderLabels([
            "ID", "Стратегия", "Символ", "Сторона", "Количество", "Цена", "P&L", "Время"
        ])
        
        header = self.trades_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        
        layout.addWidget(self.trades_table)
        
        return widget
    
    def _start_test(self):
        """
        Запуск тестирования стратегии
        """
        try:
            strategy_key = self.strategy_combo.currentData()
            if not strategy_key:
                QMessageBox.warning(self, "Предупреждение", "Выберите стратегию для тестирования")
                return
            
            # Получаем выбранные символы
            selected_symbols = []
            if self.btc_checkbox.isChecked():
                selected_symbols.append("BTCUSDT")
            if self.eth_checkbox.isChecked():
                selected_symbols.append("ETHUSDT")
            if self.ada_checkbox.isChecked():
                selected_symbols.append("ADAUSDT")
            if self.dot_checkbox.isChecked():
                selected_symbols.append("DOTUSDT")
            if self.link_checkbox.isChecked():
                selected_symbols.append("LINKUSDT")
            
            if not selected_symbols:
                QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы одну торговую пару")
                return
            
            # Параметры тестирования
            test_params = {
                'duration': self.test_duration_spin.value(),
                'initial_balance': self.initial_balance_spin.value(),
                'simulation_speed_ms': self.simulation_speed_spin.value(),
                'volatility_factor': self.volatility_spin.value(),
                'selected_symbols': selected_symbols
            }
            
            # Создаем и запускаем воркер
            self.test_worker = StrategyTestWorker(strategy_key, test_params)
            self.test_worker.test_progress.connect(self._update_progress)
            self.test_worker.test_result.connect(self._on_test_completed)
            self.test_worker.trade_executed.connect(self._on_trade_executed)
            
            self.test_worker.start()
            
            # Обновляем интерфейс
            self.start_test_button.setEnabled(False)
            self.stop_test_button.setEnabled(True)
            self.progress_bar.setValue(0)
            
            self._add_test_log(f"Запущено тестирование стратегии: {strategy_key}")
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска тестирования: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка запуска тестирования: {e}")
    
    def _stop_test(self):
        """
        Остановка тестирования
        """
        if self.test_worker and self.test_worker.isRunning():
            self.test_worker.stop()
            self.test_worker.wait()
            
        self._reset_test_ui()
        self._add_test_log("Тестирование остановлено пользователем")
    
    def _update_progress(self, progress: int):
        """
        Обновление прогресса тестирования
        """
        self.progress_bar.setValue(progress)
    
    def _on_test_completed(self, result: Dict[str, Any]):
        """
        Обработка завершения тестирования
        """
        try:
            # Сохраняем результат в БД
            self.test_db.save_test_result(result)
            
            # Обновляем интерфейс
            self._reset_test_ui()
            
            # Показываем результат
            message = f"""Тестирование завершено!
            
Стратегия: {result['strategy_name']}
Всего сделок: {result['total_trades']}
Прибыльных сделок: {result['profitable_trades']}
Общая прибыль: {result['total_profit']:.2f} USDT
Win Rate: {result['win_rate']:.1f}%
Максимальная просадка: {result['max_drawdown']:.2f} USDT
            """
            
            QMessageBox.information(self, "Тестирование завершено", message)
            self._add_test_log(f"Тестирование завершено. Результат сохранен: {result['test_name']}")
            
            # Обновляем таблицы
            self._refresh_results()
            self._refresh_trades()
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки результата тестирования: {e}")
    
    def _on_trade_executed(self, trade: Dict[str, Any]):
        """
        Обработка выполненной сделки
        """
        try:
            # Сохраняем сделку в БД
            self.test_db.save_test_trade(trade)
            
            # Добавляем в лог
            self._add_test_log(
                f"Сделка: {trade['side']} {trade['quantity']} {trade['symbol']} "
                f"по цене {trade['price']} (P&L: {trade['profit_loss']:.2f})"
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки сделки: {e}")
    
    def _reset_test_ui(self):
        """
        Сброс интерфейса тестирования
        """
        self.start_test_button.setEnabled(True)
        self.stop_test_button.setEnabled(False)
        self.progress_bar.setValue(0)
    
    def _add_test_log(self, message: str):
        """
        Добавление сообщения в лог тестирования
        """
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.test_log.append(f"[{timestamp}] {message}")
    
    def _refresh_results(self):
        """
        Обновление таблицы результатов
        """
        try:
            results = self.test_db.get_test_results()
            
            self.results_table.setRowCount(len(results))
            
            for row, result in enumerate(results):
                self.results_table.setItem(row, 0, QTableWidgetItem(str(result['test_name'])))  # test_name
                self.results_table.setItem(row, 1, QTableWidgetItem(str(result['strategy_name'])))  # strategy_name
                self.results_table.setItem(row, 2, QTableWidgetItem(str(result['start_time'])))  # start_time
                self.results_table.setItem(row, 3, QTableWidgetItem(str(result['end_time'])))  # end_time
                self.results_table.setItem(row, 4, QTableWidgetItem(str(result['total_trades'])))  # total_trades
                self.results_table.setItem(row, 5, QTableWidgetItem(str(result['profitable_trades'])))  # profitable_trades
                self.results_table.setItem(row, 6, QTableWidgetItem(f"{result['total_profit']:.2f}"))  # total_profit
                self.results_table.setItem(row, 7, QTableWidgetItem(f"{result['max_drawdown']:.2f}"))  # max_drawdown
                self.results_table.setItem(row, 8, QTableWidgetItem(f"{result['win_rate']:.1f}%"))  # win_rate
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления результатов: {e}")
    
    def _refresh_trades(self):
        """
        Обновление таблицы сделок
        """
        try:
            strategy_filter = self.trades_filter_combo.currentData()
            trades = self.test_db.get_test_trades(strategy_filter)
            
            self.trades_table.setRowCount(len(trades))
            
            for row, trade in enumerate(trades):
                self.trades_table.setItem(row, 0, QTableWidgetItem(str(trade['id'])))  # id
                self.trades_table.setItem(row, 1, QTableWidgetItem(str(trade['strategy_name'])))  # strategy_name
                self.trades_table.setItem(row, 2, QTableWidgetItem(str(trade['symbol'])))  # symbol
                self.trades_table.setItem(row, 3, QTableWidgetItem(str(trade['side'])))  # side
                self.trades_table.setItem(row, 4, QTableWidgetItem(str(trade['quantity'])))  # quantity
                self.trades_table.setItem(row, 5, QTableWidgetItem(str(trade['price'])))  # price
                
                # Цветовое выделение P&L
                pnl_item = QTableWidgetItem(f"{trade['profit_loss']:.2f}")
                if trade['profit_loss'] > 0:
                    pnl_item.setBackground(Qt.green)
                elif trade['profit_loss'] < 0:
                    pnl_item.setBackground(Qt.red)
                self.trades_table.setItem(row, 6, pnl_item)
                
                self.trades_table.setItem(row, 7, QTableWidgetItem(str(trade['timestamp'])))  # timestamp
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления сделок: {e}")

def main():
    """
    Главная функция для запуска тестовой программы
    """
    # Настройка логирования
    setup_logging()
    
    # Создание приложения
    app = QApplication(sys.argv)
    app.setApplicationName("Bybit Trading Bot - Test Program")
    app.setApplicationVersion("1.0.0")
    
    # Устанавливаем стиль приложения
    app.setStyle('Fusion')
    
    # Создаем и показываем главное окно
    window = TestProgramMainWindow()
    window.show()
    
    # Запускаем приложение
    sys.exit(app.exec())

if __name__ == "__main__":
    main()