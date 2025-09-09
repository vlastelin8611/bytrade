import sys
import os
import logging
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

# Добавление корневой папки в путь для импорта модулей
sys.path.append(str(Path(__file__).parent))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QPushButton, QLabel, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTextEdit, QTabWidget, QDialog, QFormLayout,
    QLineEdit, QCheckBox, QMessageBox, QDialogButtonBox, QSystemTrayIcon,
    QMenu, QProgressBar, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QAction

from src.api.bybit_client import BybitClient
from src.database.db_manager import DatabaseManager
from src.core.config_manager import ConfigManager

class TradingWorker(QThread):
    """Рабочий поток для торговли"""
    balance_updated = Signal(dict)
    positions_updated = Signal(list)
    trade_executed = Signal(dict)
    log_message = Signal(str, str)
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = BybitClient(api_key, api_secret)
        self.trading_enabled = False
        self.daily_balance_used = 0.0
        self.logger = logging.getLogger(__name__)
    
    def run(self):
        """Запуск торгового потока"""
        self.log_message.emit("INFO", "Торговый поток запущен")
        
        while True:
            try:
                # Получение баланса и позиций
                balance = self.get_balance()
                positions = self.get_positions()
                
                # Обновление интерфейса
                if balance:
                    self.balance_updated.emit(balance)
                if positions:
                    self.positions_updated.emit(positions)
                
                # Выполнение торговой логики, если торговля включена
                if self.trading_enabled:
                    self.execute_trading_logic()
                
                # Пауза между обновлениями
                self.msleep(5000)  # 5 секунд
                
            except Exception as e:
                self.log_message.emit("ERROR", f"Ошибка в торговом потоке: {e}")
                self.msleep(10000)  # 10 секунд при ошибке
    
    def get_balance(self) -> Dict:
        """Получение баланса аккаунта"""
        try:
            response = self.client.get_wallet_balance()
            if response and 'result' in response:
                for coin_data in response['result']['list']:
                    if coin_data['coin'] == 'USDT':
                        return coin_data
            return {}
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка получения баланса: {e}")
            return {}
    
    def get_positions(self) -> List:
        """Получение открытых позиций"""
        try:
            response = self.client.get_positions()
            if response and 'result' in response:
                return [pos for pos in response['result']['list'] if float(pos['size']) > 0]
            return []
        except Exception as e:
            self.log_message.emit("ERROR", f"Ошибка получения позиций: {e}")
            return []
    
    def execute_trading_logic(self):
        """Выполнение торговой логики"""
        # Здесь будет реализована торговая логика
        pass
    
    def enable_trading(self, enabled: bool):
        """Включение/выключение торговли"""
        self.trading_enabled = enabled
        status = "включена" if enabled else "выключена"
        self.log_message.emit("INFO", f"Торговля {status}")

class SettingsDialog(QDialog):
    """Диалог настроек приложения"""
    
    settings_changed = Signal()
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        self.setWindowTitle("Настройки")
        self.setMinimumSize(600, 400)
        
        self._init_ui()
        self._load_settings()
    
    def _init_ui(self):
        """Инициализация интерфейса"""
        layout = QVBoxLayout(self)
        
        # Создание вкладок
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Создание вкладок настроек
        self._create_api_tab()
        self._create_trading_tab()
        self._create_interface_tab()
        
        # Кнопки диалога
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self._save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _create_api_tab(self):
        """Создание вкладки настроек API"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Группа основных настроек API
        api_group = QGroupBox("Настройки API")
        api_layout = QFormLayout(api_group)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Key:", self.api_key_edit)
        
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.Password)
        api_layout.addRow("API Secret:", self.api_secret_edit)
        
        self.testnet_checkbox = QCheckBox("Использовать Testnet")
        api_layout.addRow(self.testnet_checkbox)
        
        # Кнопка тестирования подключения
        test_button = QPushButton("Тестировать подключение")
        test_button.clicked.connect(self._test_connection)
        api_layout.addRow(test_button)
        
        layout.addWidget(api_group)
        
        # Группа настроек подключения
        connection_group = QGroupBox("Настройки подключения")
        connection_layout = QFormLayout(connection_group)
        
        self.timeout_spin = QLineEdit("30")
        connection_layout.addRow("Таймаут запросов (сек):", self.timeout_spin)
        
        self.retry_count = QLineEdit("3")
        connection_layout.addRow("Количество повторов:", self.retry_count)
        
        layout.addWidget(connection_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "API")
    
    def _create_trading_tab(self):
        """Создание вкладки настроек торговли"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Группа риск-менеджмента
        risk_group = QGroupBox("Риск-менеджмент")
        risk_layout = QFormLayout(risk_group)
        
        self.max_position_size = QLineEdit("5.0")
        risk_layout.addRow("Макс. размер позиции (%):", self.max_position_size)
        
        self.default_stop_loss = QLineEdit("2.0")
        risk_layout.addRow("Стоп-лосс по умолчанию (%):", self.default_stop_loss)
        
        self.default_take_profit = QLineEdit("4.0")
        risk_layout.addRow("Тейк-профит по умолчанию (%):", self.default_take_profit)
        
        layout.addWidget(risk_group)
        
        # Группа настроек стратегий
        strategy_group = QGroupBox("Настройки стратегий")
        strategy_layout = QFormLayout(strategy_group)
        
        self.auto_start_checkbox = QCheckBox()
        strategy_layout.addRow("Автозапуск стратегий:", self.auto_start_checkbox)
        
        self.max_concurrent = QLineEdit("3")
        strategy_layout.addRow("Макс. одновременных стратегий:", self.max_concurrent)
        
        layout.addWidget(strategy_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Торговля")
    
    def _create_interface_tab(self):
        """Создание вкладки настроек интерфейса"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Группа настроек интерфейса
        ui_group = QGroupBox("Интерфейс")
        ui_layout = QFormLayout(ui_group)
        
        self.theme_combo = QLineEdit("Светлая")
        ui_layout.addRow("Тема:", self.theme_combo)
        
        self.font_size = QLineEdit("10")
        ui_layout.addRow("Размер шрифта:", self.font_size)
        
        layout.addWidget(ui_group)
        
        # Группа обновлений
        update_group = QGroupBox("Обновления данных")
        update_layout = QFormLayout(update_group)
        
        self.update_interval = QLineEdit("5")
        update_layout.addRow("Интервал обновления (сек):", self.update_interval)
        
        self.auto_refresh_checkbox = QCheckBox()
        update_layout.addRow("Автообновление данных:", self.auto_refresh_checkbox)
        
        layout.addWidget(update_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Интерфейс")
    
    def _load_settings(self):
        """Загрузка текущих настроек"""
        try:
            # API настройки
            environment = 'testnet' if self.config.get('trading.testnet', True) else 'mainnet'
            api_credentials = self.config.get_api_credentials(environment)
            
            self.api_key_edit.setText(api_credentials.get('api_key', ''))
            self.api_secret_edit.setText(api_credentials.get('api_secret', ''))
            self.testnet_checkbox.setChecked(self.config.get('trading.testnet', True))
            
            # Настройки подключения
            self.timeout_spin.setText(str(self.config.get('connection.timeout', 30)))
            self.retry_count.setText(str(self.config.get('connection.retry_count', 3)))
            
            # Риск-менеджмент
            self.max_position_size.setText(str(self.config.get('risk.max_position_size', 5.0)))
            self.default_stop_loss.setText(str(self.config.get('risk.default_stop_loss', 2.0)))
            self.default_take_profit.setText(str(self.config.get('risk.default_take_profit', 4.0)))
            
            # Настройки стратегий
            self.auto_start_checkbox.setChecked(self.config.get('strategies.auto_start', False))
            self.max_concurrent.setText(str(self.config.get('strategies.max_concurrent', 3)))
            
            # Интерфейс
            self.theme_combo.setText(self.config.get('ui.theme', 'Светлая'))
            self.font_size.setText(str(self.config.get('ui.font_size', 10)))
            self.update_interval.setText(str(self.config.get('ui.update_interval', 5)))
            self.auto_refresh_checkbox.setChecked(self.config.get('ui.auto_refresh', True))
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки настроек: {e}")
    
    def _save_settings(self):
        """Сохранение настроек"""
        try:
            # API настройки
            environment = 'testnet' if self.testnet_checkbox.isChecked() else 'mainnet'
            self.config.set_api_credentials(environment, self.api_key_edit.text(), self.api_secret_edit.text())
            self.config.set('trading.testnet', self.testnet_checkbox.isChecked())
            
            # Настройки подключения
            self.config.set('connection.timeout', int(self.timeout_spin.text()))
            self.config.set('connection.retry_count', int(self.retry_count.text()))
            
            # Риск-менеджмент
            self.config.set('risk.max_position_size', float(self.max_position_size.text()))
            self.config.set('risk.default_stop_loss', float(self.default_stop_loss.text()))
            self.config.set('risk.default_take_profit', float(self.default_take_profit.text()))
            
            # Настройки стратегий
            self.config.set('strategies.auto_start', self.auto_start_checkbox.isChecked())
            self.config.set('strategies.max_concurrent', int(self.max_concurrent.text()))
            
            # Интерфейс
            self.config.set('ui.theme', self.theme_combo.text())
            self.config.set('ui.font_size', int(self.font_size.text()))
            self.config.set('ui.update_interval', int(self.update_interval.text()))
            self.config.set('ui.auto_refresh', self.auto_refresh_checkbox.isChecked())
            
            # Сохранение конфигурации
            self.config.save()
            
            self.settings_changed.emit()
            self.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {e}")
    
    def _test_connection(self):
        """Тестирование подключения к API"""
        try:
            api_key = self.api_key_edit.text()
            api_secret = self.api_secret_edit.text()
            
            if not api_key or not api_secret:
                QMessageBox.warning(self, "Ошибка", "Введите API ключ и секрет")
                return
            
            # Создание временного клиента для проверки
            from src.api.bybit_client import BybitClient
            client = BybitClient(api_key, api_secret, testnet=self.testnet_checkbox.isChecked())
            
            # Проверка подключения
            response = client.get_wallet_balance()
            
            if response and 'result' in response:
                QMessageBox.information(self, "Успех", "Подключение успешно установлено!")
            else:
                QMessageBox.warning(self, "Ошибка", f"Ошибка подключения: {response}")
                
        except Exception as e:
            self.logger.error(f"Ошибка тестирования подключения: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка подключения: {e}")


class TradingBotMainWindow(QMainWindow):
    """Главное окно торгового бота"""
    
    def __init__(self):
        super().__init__()
        
        # Настройка логгера
        self.logger = logging.getLogger(__name__)
        
        # Загрузка конфигурации
        self.config = ConfigManager()
        
        # Настройка интерфейса
        self.setWindowTitle("Bybit Trading Bot")
        self.setMinimumSize(1000, 800)
        
        # Инициализация базы данных
        self.db = DatabaseManager(environment="testnet" if self.config.get('trading.testnet', True) else "mainnet")
        
        # Инициализация интерфейса
        self.init_ui()
        self.setup_menu()
        self.setup_status_bar()
        self.setup_timers()
        self.apply_styles()
        
        # Проверка API ключей и запуск торгового потока
        self.init_trading_worker()
        
        # Показываем сообщение о готовности
        self.status_bar.showMessage("Приложение готово к работе", 3000)
    
    def init_ui(self):
        """Инициализация пользовательского интерфейса"""
        # Создание центрального виджета
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной вертикальный макет
        main_layout = QVBoxLayout(central_widget)
        
        # Создание вкладок
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # Инициализация вкладок
        self.init_main_tab()
        self.init_markets_tab()
        self.init_strategies_tab()
        self.init_positions_tab()
        self.init_orders_tab()
        self.init_history_tab()
        self.init_log_tab()
    
    def setup_menu(self):
        """Настройка главного меню"""
        # Создание меню
        menu_bar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menu_bar.addMenu("Файл")
        
        # Действие "Настройки"
        settings_action = QAction("Настройки", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)
        
        # Действие "Экспорт данных"
        export_action = QAction("Экспорт данных", self)
        export_action.triggered.connect(self.export_data)
        file_menu.addAction(export_action)
        
        # Разделитель
        file_menu.addSeparator()
        
        # Действие "Выход"
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню "Режим"
        mode_menu = menu_bar.addMenu("Режим")
        
        # Действие "Testnet/Mainnet"
        self.testnet_action = QAction("Переключить на Mainnet", self)
        self.testnet_action.triggered.connect(self.toggle_testnet)
        mode_menu.addAction(self.testnet_action)
        
        # Обновление текста действия в зависимости от текущего режима
        self.update_testnet_action()
        
        # Меню "Справка"
        help_menu = menu_bar.addMenu("Справка")
        
        # Действие "О программе"
        about_action = QAction("О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
        # Действие "Документация"
        docs_action = QAction("Документация", self)
        docs_action.triggered.connect(self.open_documentation)
        help_menu.addAction(docs_action)
    
    def setup_status_bar(self):
        """Настройка статус-бара"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Индикатор режима (Testnet/Mainnet)
        self.mode_indicator = QLabel()
        self.status_bar.addPermanentWidget(self.mode_indicator)
        self.update_mode_indicator()
        
        # Индикатор подключения
        self.connection_indicator = QLabel("Нет подключения")
        self.status_bar.addPermanentWidget(self.connection_indicator)
        
        # Прогресс-бар для операций
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(150)
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
    
    def setup_timers(self):
        """Настройка таймеров"""
        # Таймер обновления статуса подключения
        self.connection_timer = QTimer(self)
        self.connection_timer.timeout.connect(self.update_connection_status)
        self.connection_timer.start(30000)  # 30 секунд
        
        # Таймер автосохранения
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(300000)  # 5 минут
    
    def init_trading_worker(self):
        """Инициализация торгового потока"""
        try:
            # Загрузка API ключей
            use_testnet = self.config.get('trading.testnet', True)
            environment = 'testnet' if use_testnet else 'mainnet'
            api_credentials = self.config.get_api_credentials(environment)
            
            api_key = api_credentials.get('api_key')
            api_secret = api_credentials.get('api_secret')
            
            if not api_key or not api_secret:
                self.logger.warning("API ключи не настроены")
                QMessageBox.warning(self, "Предупреждение", "API ключи не настроены. Пожалуйста, настройте API ключи в настройках.")
                return
            
            # Создание рабочего потока для торговли
            self.trading_worker = TradingWorker(api_key, api_secret)
            self.trading_worker.balance_updated.connect(self.update_balance_display)
            self.trading_worker.positions_updated.connect(self.update_positions_display)
            self.trading_worker.trade_executed.connect(self.add_trade_to_history)
            self.trading_worker.log_message.connect(self.add_log_message)
            
            # Запуск торгового потока
            self.trading_worker.start()
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации торгового потока: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось инициализировать торговый поток: {e}")
    
    def init_main_tab(self):
        """Инициализация главной вкладки"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Верхняя панель с информацией о балансе и кнопками управления
        control_panel = QGroupBox("Управление")
        control_layout = QVBoxLayout(control_panel)
        
        # Информация о балансе
        balance_group = QGroupBox("Баланс")
        balance_layout = QFormLayout(balance_group)
        
        self.balance_label = QLabel("0.00 USDT")
        balance_layout.addRow("Доступно:", self.balance_label)
        
        self.equity_label = QLabel("0.00 USDT")
        balance_layout.addRow("Эквити:", self.equity_label)
        
        self.margin_label = QLabel("0.00 USDT")
        balance_layout.addRow("Маржа:", self.margin_label)
        
        control_layout.addWidget(balance_group)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.trading_button = QPushButton("Включить торговлю")
        self.trading_button.setCheckable(True)
        self.trading_button.clicked.connect(self.toggle_trading)
        buttons_layout.addWidget(self.trading_button)
        
        self.settings_button = QPushButton("Настройки")
        self.settings_button.clicked.connect(self.open_settings)
        buttons_layout.addWidget(self.settings_button)
        
        control_layout.addLayout(buttons_layout)
        layout.addWidget(control_panel)
        
        # Панель с текущими позициями
        positions_group = QGroupBox("Текущие позиции")
        positions_layout = QVBoxLayout(positions_group)
        
        self.positions_table = QTableWidget(0, 5)
        self.positions_table.setHorizontalHeaderLabels(["Символ", "Сторона", "Размер", "Цена входа", "PnL"])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        positions_layout.addWidget(self.positions_table)
        
        layout.addWidget(positions_group)
        
        # Добавление вкладки
        self.tab_widget.addTab(tab, "Главная")
    
    def init_markets_tab(self):
        """Инициализация вкладки рынков"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Таблица рынков
        self.markets_table = QTableWidget(0, 5)
        self.markets_table.setHorizontalHeaderLabels(["Символ", "Последняя цена", "24ч Изм.", "24ч Объем", "Действия"])
        self.markets_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.markets_table)
        
        # Добавление вкладки
        self.tab_widget.addTab(tab, "Рынки")
    
    def init_strategies_tab(self):
        """Инициализация вкладки стратегий"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Верхняя панель с кнопками управления стратегиями
        buttons_layout = QHBoxLayout()
        
        add_strategy_button = QPushButton("Добавить стратегию")
        add_strategy_button.clicked.connect(self.add_strategy)
        buttons_layout.addWidget(add_strategy_button)
        
        start_all_button = QPushButton("Запустить все")
        start_all_button.clicked.connect(self.start_all_strategies)
        buttons_layout.addWidget(start_all_button)
        
        stop_all_button = QPushButton("Остановить все")
        stop_all_button.clicked.connect(self.stop_all_strategies)
        buttons_layout.addWidget(stop_all_button)
        
        layout.addLayout(buttons_layout)
        
        # Таблица стратегий
        self.strategies_table = QTableWidget(0, 6)
        self.strategies_table.setHorizontalHeaderLabels(["Название", "Символ", "Статус", "P&L", "Сигналы", "Действия"])
        self.strategies_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.strategies_table)
        
        # Добавление вкладки
        self.tab_widget.addTab(tab, "Стратегии")
    
    def init_positions_tab(self):
        """Инициализация вкладки позиций"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Таблица позиций
        self.detailed_positions_table = QTableWidget(0, 8)
        self.detailed_positions_table.setHorizontalHeaderLabels(["Символ", "Сторона", "Размер", "Цена входа", "Маржа", "PnL", "ROE%", "Действия"])
        self.detailed_positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.detailed_positions_table)
        
        # Добавление вкладки
        self.tab_widget.addTab(tab, "Позиции")
    
    def init_orders_tab(self):
        """Инициализация вкладки ордеров"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Таблица ордеров
        self.orders_table = QTableWidget(0, 7)
        self.orders_table.setHorizontalHeaderLabels(["ID", "Символ", "Тип", "Сторона", "Цена", "Размер", "Статус"])
        self.orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.orders_table)
        
        # Добавление вкладки
        self.tab_widget.addTab(tab, "Ордера")
    
    def init_history_tab(self):
        """Инициализация вкладки истории"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Таблица истории сделок
        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels(["Дата", "Символ", "Тип", "Цена", "Размер", "P&L"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.history_table)
        
        # Добавление вкладки
        self.tab_widget.addTab(tab, "История")
    
    def init_log_tab(self):
        """Инициализация вкладки лога"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Текстовое поле для лога
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)
        
        # Добавление вкладки
        self.tab_widget.addTab(tab, "Лог")
    
    def init_control_panel(self, parent_splitter):
        """Инициализация панели управления"""
        control_widget = QWidget()
        control_layout = QHBoxLayout(control_widget)
        
        # Группа статуса
        status_group = QGroupBox("Статус")
        status_layout = QVBoxLayout(status_group)
        
        self.connection_label = QLabel("Статус: Подключение...")
        status_layout.addWidget(self.connection_label)
        
        self.balance_label = QLabel("Баланс: 0.00 USDT")
        status_layout.addWidget(self.balance_label)
        
        self.daily_used_label = QLabel("Использовано сегодня: 0.0%")
        status_layout.addWidget(self.daily_used_label)
        
        control_layout.addWidget(status_group)
        
        # Группа управления
        control_group = QGroupBox("Управление")
        control_buttons_layout = QVBoxLayout(control_group)
        
        self.trading_button = QPushButton("Включить торговлю")
        self.trading_button.setCheckable(True)
        self.trading_button.clicked.connect(self.toggle_trading)
        control_buttons_layout.addWidget(self.trading_button)
        
        control_layout.addWidget(control_group)
        
        parent_splitter.addWidget(control_widget)
    
    def init_trading_panel(self, parent_splitter):
        """Инициализация панели торговли"""
        trading_widget = QWidget()
        trading_layout = QVBoxLayout(trading_widget)
        
        # Группа позиций
        positions_group = QGroupBox("Текущие позиции")
        positions_layout = QVBoxLayout(positions_group)
        
        self.positions_table = QTableWidget(0, 6)
        self.positions_table.setHorizontalHeaderLabels(["Символ", "Сторона", "Размер", "Средняя цена", "PnL", "Статус"])
        self.positions_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        positions_layout.addWidget(self.positions_table)
        
        trading_layout.addWidget(positions_group)
        
        parent_splitter.addWidget(trading_widget)
    
    def init_history_panel(self, parent_splitter):
        """Инициализация панели истории"""
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)
        
        # Группа истории сделок
        history_group = QGroupBox("История сделок")
        history_table_layout = QVBoxLayout(history_group)
        
        self.history_table = QTableWidget(0, 6)
        self.history_table.setHorizontalHeaderLabels(["Время", "Символ", "Сторона", "Размер", "Тип", "Статус"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        history_table_layout.addWidget(self.history_table)
        
        history_layout.addWidget(history_group)
        
        # Группа логов
        logs_group = QGroupBox("Логи")
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
            
            # Проверка наличия API ключей
            use_testnet = self.config.get('trading.testnet', True)
            environment = 'testnet' if use_testnet else 'mainnet'
            api_credentials = self.config.get_api_credentials(environment)
            
            if not api_credentials.get('api_key') or not api_credentials.get('api_secret'):
                QMessageBox.warning(self, "Предупреждение", "API ключи не настроены. Пожалуйста, настройте API ключи в настройках.")
                self.trading_button.setChecked(False)
                self.trading_button.setText("Включить торговлю")
                return
            
            # Запуск торгового потока, если он не запущен
            if not hasattr(self, 'trading_worker') or not self.trading_worker.isRunning():
                self.init_trading_worker()
            
            # Включение торговли в рабочем потоке
            if hasattr(self, 'trading_worker'):
                self.trading_worker.enable_trading(True)
            
            # Запуск активных стратегий
            self.start_active_strategies()
            
            self.logger.info("Торговля включена")
            self.add_log_message("INFO", "Торговля включена")
        else:
            self.trading_button.setText("Включить торговлю")
            
            # Выключение торговли в рабочем потоке
            if hasattr(self, 'trading_worker'):
                self.trading_worker.enable_trading(False)
            
            # Остановка активных стратегий
            self.stop_all_strategies()
            
            self.logger.info("Торговля выключена")
            self.add_log_message("INFO", "Торговля выключена")
    
    def add_strategy(self):
        """Добавление новой стратегии"""
        # Создаем диалог настройки параметров стратегии
        dialog = QDialog(self)
        dialog.setWindowTitle("Новая стратегия")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # Основные параметры
        form_layout = QFormLayout()
        
        # Название стратегии
        name_edit = QLineEdit("Новая стратегия")
        form_layout.addRow("Название:", name_edit)
        
        # Торговая пара
        symbol_combo = QComboBox()
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
        symbol_combo.addItems(symbols)
        symbol_combo.setCurrentText("BTCUSDT")
        form_layout.addRow("Торговая пара:", symbol_combo)
        
        # Тип стратегии
        strategy_type_combo = QComboBox()
        strategy_type_combo.addItems(["Скользящие средние", "RSI", "MACD", "Bollinger Bands"])
        form_layout.addRow("Тип стратегии:", strategy_type_combo)
        
        # Таймфрейм
        timeframe_combo = QComboBox()
        timeframe_combo.addItems(["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
        timeframe_combo.setCurrentText("15m")
        form_layout.addRow("Таймфрейм:", timeframe_combo)
        
        # Размер позиции
        position_size_spin = QDoubleSpinBox()
        position_size_spin.setRange(0.001, 1.0)
        position_size_spin.setSingleStep(0.001)
        position_size_spin.setValue(0.01)
        position_size_spin.setDecimals(3)
        form_layout.addRow("Размер позиции (BTC):", position_size_spin)
        
        # Кредитное плечо
        leverage_spin = QSpinBox()
        leverage_spin.setRange(1, 20)
        leverage_spin.setValue(5)
        form_layout.addRow("Кредитное плечо:", leverage_spin)
        
        # Стоп-лосс (в %)
        stop_loss_spin = QDoubleSpinBox()
        stop_loss_spin.setRange(0.1, 10.0)
        stop_loss_spin.setSingleStep(0.1)
        stop_loss_spin.setValue(2.0)
        stop_loss_spin.setDecimals(1)
        form_layout.addRow("Стоп-лосс (%):", stop_loss_spin)
        
        # Тейк-профит (в %)
        take_profit_spin = QDoubleSpinBox()
        take_profit_spin.setRange(0.1, 20.0)
        take_profit_spin.setSingleStep(0.1)
        take_profit_spin.setValue(5.0)
        take_profit_spin.setDecimals(1)
        form_layout.addRow("Тейк-профит (%):", take_profit_spin)
        
        # Автозапуск
        auto_start_check = QCheckBox()
        auto_start_check.setChecked(False)
        form_layout.addRow("Автозапуск:", auto_start_check)
        
        layout.addLayout(form_layout)
        
        # Группа параметров индикаторов
        indicator_group = QGroupBox("Параметры индикаторов")
        indicator_layout = QVBoxLayout(indicator_group)
        
        # Создаем стек виджетов для разных типов стратегий
        indicator_stack = QStackedWidget()
        
        # 1. Скользящие средние
        ma_widget = QWidget()
        ma_layout = QFormLayout(ma_widget)
        
        fast_ma_spin = QSpinBox()
        fast_ma_spin.setRange(5, 50)
        fast_ma_spin.setValue(9)
        ma_layout.addRow("Быстрая MA (период):", fast_ma_spin)
        
        slow_ma_spin = QSpinBox()
        slow_ma_spin.setRange(10, 200)
        slow_ma_spin.setValue(21)
        ma_layout.addRow("Медленная MA (период):", slow_ma_spin)
        
        ma_type_combo = QComboBox()
        ma_type_combo.addItems(["SMA", "EMA", "WMA"])
        ma_layout.addRow("Тип MA:", ma_type_combo)
        
        indicator_stack.addWidget(ma_widget)
        
        # 2. RSI
        rsi_widget = QWidget()
        rsi_layout = QFormLayout(rsi_widget)
        
        rsi_period_spin = QSpinBox()
        rsi_period_spin.setRange(5, 30)
        rsi_period_spin.setValue(14)
        rsi_layout.addRow("Период RSI:", rsi_period_spin)
        
        rsi_overbought_spin = QSpinBox()
        rsi_overbought_spin.setRange(50, 90)
        rsi_overbought_spin.setValue(70)
        rsi_layout.addRow("Уровень перекупленности:", rsi_overbought_spin)
        
        rsi_oversold_spin = QSpinBox()
        rsi_oversold_spin.setRange(10, 50)
        rsi_oversold_spin.setValue(30)
        rsi_layout.addRow("Уровень перепроданности:", rsi_oversold_spin)
        
        indicator_stack.addWidget(rsi_widget)
        
        # 3. MACD
        macd_widget = QWidget()
        macd_layout = QFormLayout(macd_widget)
        
        macd_fast_spin = QSpinBox()
        macd_fast_spin.setRange(5, 20)
        macd_fast_spin.setValue(12)
        macd_layout.addRow("Быстрый период:", macd_fast_spin)
        
        macd_slow_spin = QSpinBox()
        macd_slow_spin.setRange(10, 40)
        macd_slow_spin.setValue(26)
        macd_layout.addRow("Медленный период:", macd_slow_spin)
        
        macd_signal_spin = QSpinBox()
        macd_signal_spin.setRange(5, 15)
        macd_signal_spin.setValue(9)
        macd_layout.addRow("Сигнальный период:", macd_signal_spin)
        
        indicator_stack.addWidget(macd_widget)
        
        # 4. Bollinger Bands
        bb_widget = QWidget()
        bb_layout = QFormLayout(bb_widget)
        
        bb_period_spin = QSpinBox()
        bb_period_spin.setRange(5, 50)
        bb_period_spin.setValue(20)
        bb_layout.addRow("Период:", bb_period_spin)
        
        bb_dev_spin = QDoubleSpinBox()
        bb_dev_spin.setRange(1.0, 4.0)
        bb_dev_spin.setSingleStep(0.1)
        bb_dev_spin.setValue(2.0)
        bb_dev_spin.setDecimals(1)
        bb_layout.addRow("Стандартное отклонение:", bb_dev_spin)
        
        indicator_stack.addWidget(bb_widget)
        
        # Добавляем стек в layout
        indicator_layout.addWidget(indicator_stack)
        layout.addWidget(indicator_group)
        
        # Связываем выбор типа стратегии с отображением соответствующих параметров
        strategy_type_combo.currentIndexChanged.connect(indicator_stack.setCurrentIndex)
        
        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Показываем диалог
        if dialog.exec() == QDialog.Accepted:
            # Добавляем новую стратегию в таблицу
            row_position = self.strategies_table.rowCount()
            self.strategies_table.insertRow(row_position)
            
            # Заполнение данных стратегии
            strategy_name = name_edit.text()
            symbol = symbol_combo.currentText()
            
            self.strategies_table.setItem(row_position, 0, QTableWidgetItem(strategy_name))
            self.strategies_table.setItem(row_position, 1, QTableWidgetItem(symbol))
            self.strategies_table.setItem(row_position, 2, QTableWidgetItem("Остановлена"))
            self.strategies_table.setItem(row_position, 3, QTableWidgetItem("0.00"))
            self.strategies_table.setItem(row_position, 4, QTableWidgetItem("0"))
            
            # Добавление кнопок действий
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)
            
            start_button = QPushButton("Старт")
            start_button.clicked.connect(lambda: self.start_strategy(row_position))
            actions_layout.addWidget(start_button)
            
            edit_button = QPushButton("Настройки")
            edit_button.clicked.connect(lambda: self.edit_strategy(row_position))
            actions_layout.addWidget(edit_button)
            
            delete_button = QPushButton("Удалить")
            delete_button.clicked.connect(lambda: self.delete_strategy(row_position))
            actions_layout.addWidget(delete_button)
            
            self.strategies_table.setCellWidget(row_position, 5, actions_widget)
            
            # Автозапуск стратегии, если выбрано
            if auto_start_check.isChecked():
                self.start_strategy(row_position)
            
            # Сохраняем параметры стратегии (в реальном приложении)
            strategy_params = {
                'name': strategy_name,
                'symbol': symbol,
                'type': strategy_type_combo.currentText(),
                'timeframe': timeframe_combo.currentText(),
                'position_size': position_size_spin.value(),
                'leverage': leverage_spin.value(),
                'stop_loss': stop_loss_spin.value(),
                'take_profit': take_profit_spin.value(),
                'auto_start': auto_start_check.isChecked(),
                # Параметры индикаторов в зависимости от типа стратегии
                'indicator_params': {}
            }
            
            # Добавляем параметры индикаторов в зависимости от типа стратегии
            strategy_type = strategy_type_combo.currentIndex()
            if strategy_type == 0:  # Скользящие средние
                strategy_params['indicator_params'] = {
                    'fast_period': fast_ma_spin.value(),
                    'slow_period': slow_ma_spin.value(),
                    'ma_type': ma_type_combo.currentText()
                }
            elif strategy_type == 1:  # RSI
                strategy_params['indicator_params'] = {
                    'period': rsi_period_spin.value(),
                    'overbought': rsi_overbought_spin.value(),
                    'oversold': rsi_oversold_spin.value()
                }
            elif strategy_type == 2:  # MACD
                strategy_params['indicator_params'] = {
                    'fast_period': macd_fast_spin.value(),
                    'slow_period': macd_slow_spin.value(),
                    'signal_period': macd_signal_spin.value()
                }
            elif strategy_type == 3:  # Bollinger Bands
                strategy_params['indicator_params'] = {
                    'period': bb_period_spin.value(),
                    'deviation': bb_dev_spin.value()
                }
            
            self.logger.info(f"Добавлена новая стратегия: {strategy_name} ({symbol})")
            self.add_log_message("INFO", f"Добавлена новая стратегия: {strategy_name} ({symbol})")
            
            # В реальном приложении здесь бы сохранялись параметры стратегии
            # self.config.set(f'strategies.{strategy_name}', strategy_params)
            # self.config.save()
    
    def start_strategy(self, row):
        """Запуск стратегии"""
        strategy_name = self.strategies_table.item(row, 0).text()
        symbol = self.strategies_table.item(row, 1).text()
        
        # Изменение статуса стратегии
        self.strategies_table.setItem(row, 2, QTableWidgetItem("Запущена"))
        
        self.logger.info(f"Запущена стратегия: {strategy_name} ({symbol})")
        self.add_log_message("INFO", f"Запущена стратегия: {strategy_name} ({symbol})")
    
    def edit_strategy(self, row):
        """Редактирование параметров стратегии"""
        strategy_name = self.strategies_table.item(row, 0).text()
        symbol = self.strategies_table.item(row, 1).text()
        
        # Создаем диалог настройки параметров стратегии
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Настройка стратегии: {strategy_name}")
        dialog.setMinimumWidth(400)
        
        layout = QVBoxLayout(dialog)
        
        # Основные параметры
        form_layout = QFormLayout()
        
        # Название стратегии
        name_edit = QLineEdit(strategy_name)
        form_layout.addRow("Название:", name_edit)
        
        # Торговая пара
        symbol_combo = QComboBox()
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"]
        symbol_combo.addItems(symbols)
        symbol_combo.setCurrentText(symbol)
        form_layout.addRow("Торговая пара:", symbol_combo)
        
        # Тип стратегии
        strategy_type_combo = QComboBox()
        strategy_type_combo.addItems(["Скользящие средние", "RSI", "MACD", "Bollinger Bands"])
        form_layout.addRow("Тип стратегии:", strategy_type_combo)
        
        # Таймфрейм
        timeframe_combo = QComboBox()
        timeframe_combo.addItems(["1m", "5m", "15m", "30m", "1h", "4h", "1d"])
        timeframe_combo.setCurrentText("15m")
        form_layout.addRow("Таймфрейм:", timeframe_combo)
        
        # Размер позиции
        position_size_spin = QDoubleSpinBox()
        position_size_spin.setRange(0.001, 1.0)
        position_size_spin.setSingleStep(0.001)
        position_size_spin.setValue(0.01)
        position_size_spin.setDecimals(3)
        form_layout.addRow("Размер позиции (BTC):", position_size_spin)
        
        # Кредитное плечо
        leverage_spin = QSpinBox()
        leverage_spin.setRange(1, 20)
        leverage_spin.setValue(5)
        form_layout.addRow("Кредитное плечо:", leverage_spin)
        
        # Стоп-лосс (в %)
        stop_loss_spin = QDoubleSpinBox()
        stop_loss_spin.setRange(0.1, 10.0)
        stop_loss_spin.setSingleStep(0.1)
        stop_loss_spin.setValue(2.0)
        stop_loss_spin.setDecimals(1)
        form_layout.addRow("Стоп-лосс (%):", stop_loss_spin)
        
        # Тейк-профит (в %)
        take_profit_spin = QDoubleSpinBox()
        take_profit_spin.setRange(0.1, 20.0)
        take_profit_spin.setSingleStep(0.1)
        take_profit_spin.setValue(5.0)
        take_profit_spin.setDecimals(1)
        form_layout.addRow("Тейк-профит (%):", take_profit_spin)
        
        # Автозапуск
        auto_start_check = QCheckBox()
        auto_start_check.setChecked(False)
        form_layout.addRow("Автозапуск:", auto_start_check)
        
        layout.addLayout(form_layout)
        
        # Группа параметров индикаторов
        indicator_group = QGroupBox("Параметры индикаторов")
        indicator_layout = QVBoxLayout(indicator_group)
        
        # Создаем стек виджетов для разных типов стратегий
        indicator_stack = QStackedWidget()
        
        # 1. Скользящие средние
        ma_widget = QWidget()
        ma_layout = QFormLayout(ma_widget)
        
        fast_ma_spin = QSpinBox()
        fast_ma_spin.setRange(5, 50)
        fast_ma_spin.setValue(9)
        ma_layout.addRow("Быстрая MA (период):", fast_ma_spin)
        
        slow_ma_spin = QSpinBox()
        slow_ma_spin.setRange(10, 200)
        slow_ma_spin.setValue(21)
        ma_layout.addRow("Медленная MA (период):", slow_ma_spin)
        
        ma_type_combo = QComboBox()
        ma_type_combo.addItems(["SMA", "EMA", "WMA"])
        ma_layout.addRow("Тип MA:", ma_type_combo)
        
        indicator_stack.addWidget(ma_widget)
        
        # 2. RSI
        rsi_widget = QWidget()
        rsi_layout = QFormLayout(rsi_widget)
        
        rsi_period_spin = QSpinBox()
        rsi_period_spin.setRange(5, 30)
        rsi_period_spin.setValue(14)
        rsi_layout.addRow("Период RSI:", rsi_period_spin)
        
        rsi_overbought_spin = QSpinBox()
        rsi_overbought_spin.setRange(50, 90)
        rsi_overbought_spin.setValue(70)
        rsi_layout.addRow("Уровень перекупленности:", rsi_overbought_spin)
        
        rsi_oversold_spin = QSpinBox()
        rsi_oversold_spin.setRange(10, 50)
        rsi_oversold_spin.setValue(30)
        rsi_layout.addRow("Уровень перепроданности:", rsi_oversold_spin)
        
        indicator_stack.addWidget(rsi_widget)
        
        # 3. MACD
        macd_widget = QWidget()
        macd_layout = QFormLayout(macd_widget)
        
        macd_fast_spin = QSpinBox()
        macd_fast_spin.setRange(5, 20)
        macd_fast_spin.setValue(12)
        macd_layout.addRow("Быстрый период:", macd_fast_spin)
        
        macd_slow_spin = QSpinBox()
        macd_slow_spin.setRange(10, 40)
        macd_slow_spin.setValue(26)
        macd_layout.addRow("Медленный период:", macd_slow_spin)
        
        macd_signal_spin = QSpinBox()
        macd_signal_spin.setRange(5, 15)
        macd_signal_spin.setValue(9)
        macd_layout.addRow("Сигнальный период:", macd_signal_spin)
        
        indicator_stack.addWidget(macd_widget)
        
        # 4. Bollinger Bands
        bb_widget = QWidget()
        bb_layout = QFormLayout(bb_widget)
        
        bb_period_spin = QSpinBox()
        bb_period_spin.setRange(5, 50)
        bb_period_spin.setValue(20)
        bb_layout.addRow("Период:", bb_period_spin)
        
        bb_dev_spin = QDoubleSpinBox()
        bb_dev_spin.setRange(1.0, 4.0)
        bb_dev_spin.setSingleStep(0.1)
        bb_dev_spin.setValue(2.0)
        bb_dev_spin.setDecimals(1)
        bb_layout.addRow("Стандартное отклонение:", bb_dev_spin)
        
        indicator_stack.addWidget(bb_widget)
        
        # Добавляем стек в layout
        indicator_layout.addWidget(indicator_stack)
        layout.addWidget(indicator_group)
        
        # Связываем выбор типа стратегии с отображением соответствующих параметров
        strategy_type_combo.currentIndexChanged.connect(indicator_stack.setCurrentIndex)
        
        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        # Показываем диалог
        if dialog.exec() == QDialog.Accepted:
            # Обновляем данные стратегии в таблице
            self.strategies_table.setItem(row, 0, QTableWidgetItem(name_edit.text()))
            self.strategies_table.setItem(row, 1, QTableWidgetItem(symbol_combo.currentText()))
            
            # Логируем изменения
            self.logger.info(f"Отредактированы параметры стратегии: {name_edit.text()}")
            self.add_log_message("INFO", f"Отредактированы параметры стратегии: {name_edit.text()}")
    
    def delete_strategy(self, row):
        """Удаление стратегии"""
        strategy_name = self.strategies_table.item(row, 0).text()
        
        # Подтверждение удаления
        reply = QMessageBox.question(self, "Удаление стратегии", 
                                   f"Вы уверены, что хотите удалить стратегию {strategy_name}?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.strategies_table.removeRow(row)
            self.logger.info(f"Удалена стратегия: {strategy_name}")
            self.add_log_message("INFO", f"Удалена стратегия: {strategy_name}")
    
    def start_all_strategies(self):
        """Запуск всех стратегий"""
        for row in range(self.strategies_table.rowCount()):
            self.strategies_table.setItem(row, 2, QTableWidgetItem("Запущена"))
        
        self.logger.info("Запущены все стратегии")
        self.add_log_message("INFO", "Запущены все стратегии")
    
    def start_active_strategies(self):
        """Запуск активных стратегий"""
        # Проверка настройки автозапуска
        if not self.config.get('strategies.auto_start', False):
            return
        
        # Запуск всех стратегий
        self.start_all_strategies()
    
    def stop_all_strategies(self):
        """Остановка всех стратегий"""
        for row in range(self.strategies_table.rowCount()):
            self.strategies_table.setItem(row, 2, QTableWidgetItem("Остановлена"))
        
        self.logger.info("Остановлены все стратегии")
        self.add_log_message("INFO", "Остановлены все стратегии")
    
    def update_testnet_action(self):
        """Обновление текста действия Testnet/Mainnet"""
        use_testnet = self.config.get('trading.testnet', True)
        if use_testnet:
            self.testnet_action.setText("Переключить на Mainnet")
        else:
            self.testnet_action.setText("Переключить на Testnet")
    
    def update_mode_indicator(self):
        """Обновление индикатора режима"""
        use_testnet = self.config.get('trading.testnet', True)
        if use_testnet:
            self.mode_indicator.setText("TESTNET")
            self.mode_indicator.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.mode_indicator.setText("MAINNET")
            self.mode_indicator.setStyleSheet("color: green; font-weight: bold;")
    
    def toggle_testnet(self):
        """Переключение между Testnet и Mainnet"""
        use_testnet = self.config.get('trading.testnet', True)
        
        # Подтверждение переключения
        new_mode = "Testnet" if not use_testnet else "Mainnet"
        reply = QMessageBox.question(self, "Переключение режима", 
                                   f"Вы уверены, что хотите переключиться на {new_mode}?",
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Переключение режима
            self.config.set('trading.testnet', not use_testnet)
            self.config.save()
            
            # Обновление интерфейса
            self.update_testnet_action()
            self.update_mode_indicator()
            
            # Перезапуск торгового потока
            if hasattr(self, 'trading_worker') and self.trading_worker.isRunning():
                self.trading_worker.stop()
                self.trading_worker.wait()
                self.init_trading_worker()
            
            self.logger.info(f"Режим переключен на {new_mode}")
            self.add_log_message("INFO", f"Режим переключен на {new_mode}")
    
    def update_connection_status(self):
        """Обновление статуса подключения"""
        if hasattr(self, 'trading_worker') and self.trading_worker.isRunning():
            self.connection_indicator.setText("Подключено")
            self.connection_indicator.setStyleSheet("color: green;")
        else:
            self.connection_indicator.setText("Нет подключения")
            self.connection_indicator.setStyleSheet("color: red;")
    
    def autosave(self):
        """Автосохранение данных"""
        self.logger.debug("Выполнено автосохранение")
    
    def open_settings(self):
        """Открытие диалога настроек"""
        settings_dialog = SettingsDialog(self.config, self)
        settings_dialog.settings_changed.connect(self.apply_settings)
        settings_dialog.exec()
    
    def apply_settings(self):
        """Применение измененных настроек"""
        # Обновление режима
        self.update_testnet_action()
        self.update_mode_indicator()
        
        # Перезапуск торгового потока при необходимости
        if hasattr(self, 'trading_worker') and self.trading_worker.isRunning():
            self.trading_worker.stop()
            self.trading_worker.wait()
            self.init_trading_worker()
        
        self.logger.info("Настройки применены")
        self.add_log_message("INFO", "Настройки применены")
    
    def export_data(self):
        """Экспорт данных"""
        # Здесь будет реализован экспорт данных
        QMessageBox.information(self, "Экспорт данных", "Функция экспорта данных будет реализована в следующей версии.")
    
    def show_about(self):
        """Показ информации о программе"""
        QMessageBox.about(self, "О программе", 
                         "<h3>Bybit Trading Bot</h3>"
                         "<p>Версия: 1.0.0</p>"
                         "<p>Автоматизированная торговая система для криптовалютной биржи Bybit.</p>"
                         "<p>&copy; 2023 Все права защищены.</p>")
    
    def open_documentation(self):
        """Открытие документации"""
        QMessageBox.information(self, "Документация", "Документация будет доступна в следующей версии.")
    
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