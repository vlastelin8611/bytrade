#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главное окно торгового бота Bybit
Простое приложение с одним окном для автоматической торговли
"""

import sys
import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
    QWidget, QLabel, QPushButton, QTextEdit, QTableWidget,
    QTableWidgetItem, QGroupBox, QProgressBar, QMessageBox,
    QSplitter, QFrame, QHeaderView
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, pyqtSignal
from PySide6.QtGui import QFont, QColor, QPalette

from src.api.bybit_client import BybitClient
from src.database.db_manager import DatabaseManager
from src.core.config_manager import ConfigManager
from src.core.logger import setup_logging
from src.strategies.adaptive_ml import AdaptiveMLStrategy

class TradingWorker(QThread):
    """
    Рабочий поток для торговых операций
    """
    balance_updated = Signal(dict)
    positions_updated = Signal(list)
    trade_executed = Signal(dict)
    log_message = Signal(str, str)  # level, message
    
    def __init__(self, api_client, db_manager, config_manager):
        super().__init__()
        self.api_client = api_client
        self.db_manager = db_manager
        self.config_manager = config_manager
        self.logger = logging.getLogger(__name__)
        
        self.trading_enabled = False
        self.daily_balance_used = 0.0
        self.daily_limit_percent = 20.0  # Максимум 20% баланса в день
        self.last_reset_date = datetime.now().date()
        
        # Инициализация ML стратегии
        strategy_config = {
            'feature_window': 50,
            'confidence_threshold': 0.65,
            'use_technical_indicators': True,
            'use_market_regime': True
        }
        self.ml_strategy = AdaptiveMLStrategy(
            "adaptive_ml", strategy_config, api_client, db_manager, config_manager
        )
        
    def enable_trading(self, enabled: bool):
        """Включить/выключить торговлю"""
        self.trading_enabled = enabled
        self.log_message.emit("INFO", f"Торговля {'включена' if enabled else 'выключена'}")
        
    def run(self):
        """Основной цикл торгового потока"""
        while True:
            try:
                # Сброс дневного лимита
                current_date = datetime.now().date()
                if current_date > self.last_reset_date:
                    self.daily_balance_used = 0.0
                    self.last_reset_date = current_date
                    self.log_message.emit("INFO", "Дневной лимит сброшен")
                
                # Получение баланса
                balance_info = self.get_balance()
                if balance_info:
                    self.balance_updated.emit(balance_info)
                
                # Получение позиций
                positions = self.get_positions()
                if positions:
                    self.positions_updated.emit(positions)
                
                # Торговая логика (если включена)
                if self.trading_enabled:
                    self.execute_trading_logic(balance_info, positions)
                
                # Пауза между циклами
                self.msleep(5000)  # 5 секунд
                
            except Exception as e:
                self.log_message.emit("ERROR", f"Ошибка в торговом потоке: {str(e)}")
                self.msleep(10000)  # 10 секунд при ошибке
    
    def get_balance(self) -> Optional[Dict]:
        """Получение баланса счета"""
        try:
            balance = self.api_client.get_wallet_balance()
            self.log_message.emit("DEBUG", "Баланс успешно получен")
            return balance
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка получения баланса: {str(e)}")
            return None
    
    def get_positions(self) -> Optional[List]:
        """Получение открытых позиций"""
        try:
            positions = self.api_client.get_positions()
            self.log_message.emit("DEBUG", f"Получено позиций: {len(positions) if positions else 0}")
            return positions
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка получения позиций: {str(e)}")
            return None
    
    def execute_trading_logic(self, balance_info: Dict, positions: List):
        """Выполнение торговой логики"""
        try:
            if not balance_info:
                return
            
            # Проверка дневного лимита
            total_balance = float(balance_info.get('totalWalletBalance', 0))
            daily_limit = total_balance * (self.daily_limit_percent / 100)
            
            if self.daily_balance_used >= daily_limit:
                self.log_message.emit("WARNING", "Достигнут дневной лимит использования баланса")
                return
            
            # Получение рыночных данных для анализа
            symbols = ['BTCUSDT', 'ETHUSDT', 'ADAUSDT', 'SOLUSDT']  # Основные пары
            
            for symbol in symbols:
                try:
                    # Получение исторических данных
                    klines = self.api_client.get_kline_data(symbol, '1h', 100)
                    if not klines:
                        continue
                    
                    # Анализ с помощью ML стратегии
                    market_data = {
                        'symbol': symbol,
                        'klines': klines,
                        'current_price': float(klines[-1]['close']) if klines else 0
                    }
                    
                    analysis = self.ml_strategy.analyze_market(market_data)
                    
                    # Принятие торгового решения
                    if analysis.get('signal') and analysis.get('confidence', 0) > 0.65:
                        available_balance = daily_limit - self.daily_balance_used
                        position_size = min(available_balance * 0.1, total_balance * 0.05)  # Максимум 5% от общего баланса на позицию
                        
                        if position_size > 10:  # Минимальный размер позиции
                            trade_result = self.execute_trade(symbol, analysis['signal'], position_size, analysis)
                            if trade_result:
                                self.daily_balance_used += position_size
                                self.trade_executed.emit(trade_result)
                                
                                # Обучение стратегии на результате
                                self.ml_strategy.learn_from_trade(trade_result)
                    
                except Exception as e:
                    self.log_message.emit("ERROR", f"Ошибка анализа {symbol}: {str(e)}")
                    
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка в торговой логике: {str(e)}")
    
    def execute_trade(self, symbol: str, signal: str, size: float, analysis: Dict) -> Optional[Dict]:
        """Выполнение торговой операции"""
        try:
            side = 'Buy' if signal == 'BUY' else 'Sell'
            
            # Размещение рыночного ордера
            order_result = self.api_client.place_order(
                category='linear',
                symbol=symbol,
                side=side,
                orderType='Market',
                qty=str(size)
            )
            
            if order_result:
                trade_info = {
                    'timestamp': datetime.now(),
                    'symbol': symbol,
                    'side': side,
                    'size': size,
                    'analysis': analysis,
                    'order_result': order_result
                }
                
                # Логирование в БД
                self.db_manager.log_trade(trade_info)
                
                self.log_message.emit("INFO", f"Выполнена сделка: {symbol} {side} {size}")
                return trade_info
                
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка выполнения сделки {symbol}: {str(e)}")
            return None

class TradingBotMainWindow(QMainWindow):
    """
    Главное окно торгового бота
    """
    
    def __init__(self):
        super().__init__()
        
        # Инициализация компонентов
        self.setup_logging()
        self.config_manager = ConfigManager()
        self.db_manager = DatabaseManager()
        
        # Загрузка API ключей
        self.load_api_keys()
        
        # Инициализация API клиента
        self.api_client = BybitClient(
            self.api_key, 
            self.api_secret, 
            testnet=True,  # Начинаем с testnet
            config_manager=self.config_manager,
            db_manager=self.db_manager
        )
        
        # Инициализация UI
        self.init_ui()
        
        # Создание рабочего потока
        self.trading_worker = TradingWorker(self.api_client, self.db_manager, self.config_manager)
        self.trading_worker.balance_updated.connect(self.update_balance_display)
        self.trading_worker.positions_updated.connect(self.update_positions_display)
        self.trading_worker.trade_executed.connect(self.add_trade_to_history)
        self.trading_worker.log_message.connect(self.add_log_message)
        
        # Запуск рабочего потока
        self.trading_worker.start()
        
        self.logger.info("Торговый бот запущен")
    
    def setup_logging(self):
        """Настройка логирования"""
        self.logger = setup_logging()
    
    def load_api_keys(self):
        """Загрузка API ключей из файла"""
        try:
            keys_file = Path(__file__).parent / 'keys'
            if keys_file.exists():
                with open(keys_file, 'r') as f:
                    content = f.read()
                    
                for line in content.split('\n'):
                    if 'BYBIT_TESTNET_API_KEY=' in line:
                        self.api_key = line.split('=')[1].strip()
                    elif 'BYBIT_TESTNET_API_SECRET=' in line:
                        self.api_secret = line.split('=')[1].strip()
                        
                self.logger.info("API ключи загружены")
            else:
                raise FileNotFoundError("Файл с ключами не найден")
                
        except Exception as e:
            self.logger.error(f"Ошибка загрузки API ключей: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить API ключи: {e}")
            sys.exit(1)
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        self.setWindowTitle("Bybit Trading Bot - Автоматическая торговля")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Верхняя панель с балансом и управлением
        self.create_control_panel(main_layout)
        
        # Разделитель
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Левая панель - позиции и торговля
        self.create_trading_panel(splitter)
        
        # Правая панель - история и логи
        self.create_history_panel(splitter)
        
        # Применение стилей
        self.apply_styles()
    
    def create_control_panel(self, parent_layout):
        """Создание панели управления"""
        control_group = QGroupBox("Управление торговлей")
        control_layout = QHBoxLayout(control_group)
        
        # Информация о балансе
        balance_frame = QFrame()
        balance_layout = QVBoxLayout(balance_frame)
        
        self.balance_label = QLabel("Баланс: Загрузка...")
        self.balance_label.setFont(QFont("Arial", 14, QFont.Bold))
        balance_layout.addWidget(self.balance_label)
        
        self.daily_used_label = QLabel("Использовано сегодня: 0%")
        balance_layout.addWidget(self.daily_used_label)
        
        control_layout.addWidget(balance_frame)
        
        # Кнопка включения/выключения торговли
        self.trading_button = QPushButton("Включить торговлю")
        self.trading_button.setMinimumSize(200, 50)
        self.trading_button.setCheckable(True)
        self.trading_button.clicked.connect(self.toggle_trading)
        control_layout.addWidget(self.trading_button)
        
        # Статус подключения
        status_frame = QFrame()
        status_layout = QVBoxLayout(status_frame)
        
        self.connection_label = QLabel("Статус: Подключение...")
        status_layout.addWidget(self.connection_label)
        
        self.mode_label = QLabel("Режим: Testnet")
        status_layout.addWidget(self.mode_label)
        
        control_layout.addWidget(status_frame)
        
        parent_layout.addWidget(control_group)
    
    def create_trading_panel(self, parent_splitter):
        """Создание панели торговли"""
        trading_widget = QWidget()
        trading_layout = QVBoxLayout(trading_widget)
        
        # Таблица позиций
        positions_group = QGroupBox("Открытые позиции")
        positions_layout = QVBoxLayout(positions_group)
        
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(6)
        self.positions_table.setHorizontalHeaderLabels([
            "Символ", "Сторона", "Размер", "Цена входа", "PnL", "Статус"
        ])
        self.positions_table.horizontalHeader().setStretchLastSection(True)
        positions_layout.addWidget(self.positions_table)
        
        trading_layout.addWidget(positions_group)
        
        # Информация о стратегии
        strategy_group = QGroupBox("ML Стратегия")
        strategy_layout = QVBoxLayout(strategy_group)
        
        self.strategy_status = QLabel("Статус: Инициализация...")
        strategy_layout.addWidget(self.strategy_status)
        
        self.strategy_performance = QLabel("Точность: 0%")
        strategy_layout.addWidget(self.strategy_performance)
        
        trading_layout.addWidget(strategy_group)
        
        parent_splitter.addWidget(trading_widget)
    
    def create_history_panel(self, parent_splitter):
        """Создание панели истории"""
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        
        # История торговли
        history_group = QGroupBox("История торговли")
        history_group_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels([
            "Время", "Символ", "Сторона", "Размер", "Цена", "Результат"
        ])
        self.history_table.horizontalHeader().setStretchLastSection(True)
        history_group_layout.addWidget(self.history_table)
        
        history_layout.addWidget(history_group)
        
        # Логи
        logs_group = QGroupBox("Логи системы")
        logs_layout = QVBoxLayout(logs_group)
        
        self.logs_text = QTextEdit()
        self.logs_text.setMaximumHeight(200)
        self.logs_text.setReadOnly(True)
        logs_layout.addWidget(self.logs_text)
        
        history_layout.addWidget(logs_group)
        
        parent_splitter.addWidget(history_widget)
    
    def apply_styles(self):
        """Применение стилей к интерфейсу"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                text-align: center;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:checked {
                background-color: #f44336;
            }
            QPushButton:checked:hover {
                background-color: #da190b;
            }
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
            }
            QTextEdit {
                background-color: #2b2b2b;
                color: #ffffff;
                font-family: 'Courier New', monospace;
            }
        """)
    
    def toggle_trading(self):
        """Переключение торговли"""
        if self.trading_button.isChecked():
            self.trading_button.setText("Выключить торговлю")
            self.trading_worker.enable_trading(True)
        else:
            self.trading_button.setText("Включить торговлю")
            self.trading_worker.enable_trading(False)
    
    def update_balance_display(self, balance_info: Dict):
        """Обновление отображения баланса"""
        try:
            total_balance = float(balance_info.get('totalWalletBalance', 0))
            available_balance = float(balance_info.get('availableBalance', 0))
            
            self.balance_label.setText(f"Баланс: {total_balance:.2f} USDT (Доступно: {available_balance:.2f})")
            
            # Обновление процента использования
            daily_used_percent = (self.trading_worker.daily_balance_used / total_balance) * 100 if total_balance > 0 else 0
            self.daily_used_label.setText(f"Использовано сегодня: {daily_used_percent:.1f}%")
            
            self.connection_label.setText("Статус: Подключен")
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления баланса: {e}")
    
    def update_positions_display(self, positions: List):
        """Обновление отображения позиций"""
        try:
            self.positions_table.setRowCount(len(positions))
            
            for i, position in enumerate(positions):
                self.positions_table.setItem(i, 0, QTableWidgetItem(position.get('symbol', '')))
                self.positions_table.setItem(i, 1, QTableWidgetItem(position.get('side', '')))
                self.positions_table.setItem(i, 2, QTableWidgetItem(str(position.get('size', 0))))
                self.positions_table.setItem(i, 3, QTableWidgetItem(str(position.get('avgPrice', 0))))
                self.positions_table.setItem(i, 4, QTableWidgetItem(str(position.get('unrealisedPnl', 0))))
                self.positions_table.setItem(i, 5, QTableWidgetItem(position.get('positionStatus', '')))
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления позиций: {e}")
    
    def add_trade_to_history(self, trade_info: Dict):
        """Добавление сделки в историю"""
        try:
            row_count = self.history_table.rowCount()
            self.history_table.insertRow(row_count)
            
            timestamp = trade_info['timestamp'].strftime("%H:%M:%S")
            self.history_table.setItem(row_count, 0, QTableWidgetItem(timestamp))
            self.history_table.setItem(row_count, 1, QTableWidgetItem(trade_info['symbol']))
            self.history_table.setItem(row_count, 2, QTableWidgetItem(trade_info['side']))
            self.history_table.setItem(row_count, 3, QTableWidgetItem(str(trade_info['size'])))
            self.history_table.setItem(row_count, 4, QTableWidgetItem("Market"))
            self.history_table.setItem(row_count, 5, QTableWidgetItem("Выполнено"))
            
            # Прокрутка к последней записи
            self.history_table.scrollToBottom()
            
        except Exception as e:
            self.logger.error(f"Ошибка добавления в историю: {e}")
    
    def add_log_message(self, level: str, message: str):
        """Добавление сообщения в логи"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}"
        
        self.logs_text.append(formatted_message)
        
        # Ограничение количества строк в логах
        if self.logs_text.document().blockCount() > 1000:
            cursor = self.logs_text.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()
    
    def closeEvent(self, event):
        """Обработка закрытия приложения"""
        self.trading_worker.trading_enabled = False
        self.trading_worker.quit()
        self.trading_worker.wait()
        
        self.logger.info("Торговый бот остановлен")
        event.accept()

def main():
    """Главная функция приложения"""
    app = QApplication(sys.argv)
    
    # Настройка приложения
    app.setApplicationName("Bybit Trading Bot")
    app.setApplicationVersion("1.0.0")
    
    try:
        # Создание и показ главного окна
        window = TradingBotMainWindow()
        window.show()
        
        # Запуск приложения
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()