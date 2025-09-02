#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вкладка "Основная информация" (аккаунт)

Отображает информацию об аккаунте Bybit:
- Баланс и активы
- Статус подключения
- Информация о счете
- Настройки API
"""

import logging
from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QProgressBar, QTextEdit, QSplitter,
    QHeaderView, QAbstractItemView, QMessageBox, QLineEdit, QCheckBox
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QPixmap

class AccountInfoWorker(QThread):
    """
    Воркер для получения информации об аккаунте
    """
    
    data_received = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(self, config_manager, bybit_client=None):
        super().__init__()
        self.config = config_manager
        self.bybit_client = bybit_client
        self.logger = logging.getLogger(__name__)
        self.running = True
    
    def run(self):
        """
        Получение данных об аккаунте
        """
        try:
            if self.bybit_client:
                # Реальное API подключение
                try:
                    # Получение баланса кошелька
                    wallet_balance = self.bybit_client.get_wallet_balance()
                    
                    # Получение информации об аккаунте
                    account_info = self.bybit_client.get_account_info()
                    
                    # Формирование данных для UI
                    account_data = {
                        "balance": self._format_balance_data(wallet_balance),
                        "account_info": self._format_account_info(account_info),
                        "api_info": {
                            "connected": True,
                            "testnet": self.config.is_testnet(),
                            "permissions": ["read", "trade", "derivatives"],
                            "rate_limit": self.bybit_client.get_rate_limit_status()
                        }
                    }
                    
                    self.data_received.emit(account_data)
                    
                except Exception as api_error:
                    self.logger.error(f"Ошибка API запроса: {api_error}")
                    # Fallback к тестовым данным при ошибке API
                    self.data_received.emit({
                        "balance": {},
                        "account_info": {
                            "account_type": "-",
                            "margin_mode": "-",
                            "total_equity": 0.0,
                            "total_wallet_balance": 0.0,
                            "total_margin_balance": 0.0,
                            "total_available_balance": 0.0,
                            "total_perp_upl": 0.0,
                            "total_initial_margin": 0.0,
                            "total_maintenance_margin": 0.0
                        },
                        "api_info": {
                            "connected": False,
                            "testnet": self.config.is_testnet(),
                            "permissions": [],
                            "rate_limit": {"used": 0, "limit": 120}
                        }
                    })
            else:
                # Тестовые данные если нет API клиента
                self.data_received.emit({
                    "balance": {},
                    "account_info": {
                        "account_type": "-",
                        "margin_mode": "-",
                        "total_equity": 0.0,
                        "total_wallet_balance": 0.0,
                        "total_margin_balance": 0.0,
                        "total_available_balance": 0.0,
                        "total_perp_upl": 0.0,
                        "total_initial_margin": 0.0,
                        "total_maintenance_margin": 0.0
                    },
                    "api_info": {
                        "connected": False,
                        "testnet": self.config.is_testnet(),
                        "permissions": [],
                        "rate_limit": {"used": 0, "limit": 120}
                    }
                })
            
        except Exception as e:
            self.logger.error(f"Ошибка получения данных аккаунта: {e}")
            self.error_occurred.emit(str(e))
    

    
    def _format_balance_data(self, wallet_data):
        """Форматирование данных баланса"""
        balance = {}
        try:
            if wallet_data and isinstance(wallet_data, dict) and 'result' in wallet_data:
                result = wallet_data['result']
                if isinstance(result, dict) and 'list' in result:
                    account_list = result['list']
                    if isinstance(account_list, list):
                        for account in account_list:
                            if isinstance(account, dict):
                                for coin in account.get('coin', []):
                                    if isinstance(coin, dict) and 'coin' in coin:
                                        symbol = coin['coin']
                                        balance[symbol] = {
                                            "total": float(coin.get('walletBalance', 0)),
                                            "available": float(coin.get('availableToWithdraw', 0)),
                                            "locked": float(coin.get('locked', 0))
                                        }
        except Exception as e:
            self.logger.error(f"Ошибка форматирования данных баланса: {e}")
        return balance
    
    def _format_account_info(self, account_data):
        """Форматирование информации об аккаунте"""
        try:
            if account_data and isinstance(account_data, dict) and 'result' in account_data:
                result_data = account_data['result']
                if isinstance(result_data, dict) and 'list' in result_data:
                    account_list = result_data['list']
                    if isinstance(account_list, list) and len(account_list) > 0:
                        result = account_list[0] if isinstance(account_list[0], dict) else {}
                        return {
                            "account_type": result.get('accountType', 'Unknown'),
                            "margin_mode": result.get('marginMode', 'Unknown'),
                            "total_equity": float(result.get('totalEquity', 0)),
                            "total_wallet_balance": float(result.get('totalWalletBalance', 0)),
                            "total_margin_balance": float(result.get('totalMarginBalance', 0)),
                            "total_available_balance": float(result.get('totalAvailableBalance', 0)),
                            "total_perp_upl": float(result.get('totalPerpUPL', 0)),
                            "total_initial_margin": float(result.get('totalInitialMargin', 0)),
                            "total_maintenance_margin": float(result.get('totalMaintenanceMargin', 0))
                        }
        except Exception as e:
            self.logger.error(f"Ошибка форматирования информации об аккаунте: {e}")
        return {}
    
    def stop(self):
        """
        Остановка воркера
        """
        self.running = False
        self.quit()
        self.wait()

class AccountTab(QWidget):
    """
    Вкладка основной информации об аккаунте
    """
    
    def __init__(self, config_manager, db_manager):
        super().__init__()
        
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Данные аккаунта
        self.account_data: Optional[Dict[str, Any]] = None
        
        # Воркер для получения данных
        self.worker = None
        
        # Автоматическая инициализация Bybit клиента для testnet
        self.bybit_client = self._init_bybit_client()
        
        # Инициализация UI
        self._init_ui()
        
        # Таймер для обновления данных
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._refresh_data)
        
        # Автоматический запуск таймера если есть подключение
        if self.bybit_client:
            self.update_timer.start(30000)  # Обновление каждые 30 секунд
            self._refresh_data()  # Первоначальная загрузка данных
        
        self.logger.info("Вкладка аккаунта инициализирована")
    
    def _init_bybit_client(self):
        """
        Инициализация Bybit API клиента (только testnet)
        """
        try:
            # Принудительно используем только testnet
            self.config.set_testnet(True)
            api_credentials = self.config.get_api_credentials('testnet')
            
            api_key = api_credentials.get('api_key', '')
            api_secret = api_credentials.get('api_secret', '')
            
            if api_key and api_secret:
                from src.api.bybit_client import BybitClient
                client = BybitClient(
                    api_key=api_key,
                    api_secret=api_secret,
                    testnet=True,
                    config_manager=self.config,
                    db_manager=self.db
                )
                self.logger.info("Bybit клиент инициализирован (testnet)")
                return client
            else:
                self.logger.warning("API ключи не найдены для testnet")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка инициализации Bybit клиента: {e}")
            return None
    
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Основная информация об аккаунте")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Секция управления API ключами
        self._create_api_controls(layout)
        
        # Проверка API ключей - если не подключены, показываем только управление
        if not self.bybit_client:
            return
        
        # Сплиттер для разделения на две части
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Левая панель - основная информация
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Предупреждение о тестовых данных
        if not self.bybit_client:
            warning_label = QLabel("⚠️ Отображаются тестовые данные. Для получения реальных данных настройте API ключи в меню Настройки.")
            warning_label.setStyleSheet("background-color: #fff3cd; color: #856404; padding: 10px; border: 1px solid #ffeaa7; border-radius: 5px; font-weight: bold;")
            warning_label.setWordWrap(True)
            left_layout.addWidget(warning_label)
        
        # Статус подключения
        self._create_connection_status(left_layout)
        
        # Информация об аккаунте
        self._create_account_info(left_layout)
        
        # Баланс активов
        self._create_balance_info(left_layout)
        
        splitter.addWidget(left_widget)
        
        # Правая панель - детальная информация
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # API информация
        self._create_api_info(right_layout)
        
        # Лог активности
        self._create_activity_log(right_layout)
        
        splitter.addWidget(right_widget)
        
        # Установка пропорций сплиттера
        splitter.setSizes([600, 400])
        
        # Кнопки управления
        self._create_control_buttons(layout)
    
    def _create_api_warning(self, layout):
        """
        Создание предупреждения о необходимости ввода API ключей
        """
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Основная информация")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        warning_frame = QFrame()
        warning_frame.setStyleSheet("""
            QFrame {
                background-color: #fff3cd;
                border: 2px solid #ffeaa7;
                border-radius: 8px;
                padding: 20px;
                margin: 10px;
            }
        """)
        warning_layout = QVBoxLayout(warning_frame)
        
        # Иконка и заголовок
        header_layout = QHBoxLayout()
        warning_icon = QLabel("⚠️")
        warning_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(warning_icon)
        
        warning_title = QLabel("API ключи не настроены")
        warning_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #856404;")
        header_layout.addWidget(warning_title)
        header_layout.addStretch()
        warning_layout.addLayout(header_layout)
        
        # Описание
        warning_text = QLabel(
            "Для отображения информации об аккаунте необходимо настроить API ключи Bybit.\n"
            "Пока API ключи не введены, информация об аккаунте недоступна."
        )
        warning_text.setStyleSheet("color: #856404; margin: 10px 0;")
        warning_text.setWordWrap(True)
        warning_layout.addWidget(warning_text)
        
        # Кнопка настройки
        setup_button = QPushButton("Настроить API ключи")
        setup_button.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        setup_button.clicked.connect(self._open_api_settings)
        warning_layout.addWidget(setup_button)
        
        layout.addWidget(warning_frame)
        
        # Показать базовую информацию
        self._show_basic_info(layout)
    
    def _show_basic_info(self, layout):
        """
        Отображение базовой информации без API
        """
        info_group = QGroupBox("Информация о режиме")
        info_layout = QGridLayout(info_group)
        
        # Режим (testnet/mainnet)
        mode = "Testnet" if self.config.is_testnet() else "Mainnet"
        mode_color = "blue" if self.config.is_testnet() else "red"
        mode_label = QLabel(mode)
        mode_label.setStyleSheet(f"color: {mode_color}; font-weight: bold; font-size: 14px;")
        info_layout.addWidget(QLabel("Текущий режим:"), 0, 0)
        info_layout.addWidget(mode_label, 0, 1)
        
        # Статус подключения
        status_label = QLabel("Не подключен")
        status_label.setStyleSheet("color: red; font-weight: bold;")
        info_layout.addWidget(QLabel("Статус:"), 1, 0)
        info_layout.addWidget(status_label, 1, 1)
        
        # Инструкция
        instruction_label = QLabel(
            "Настройте API ключи для получения:\n"
            "• Информации о балансе\n"
            "• Данных об аккаунте\n"
            "• Истории операций\n"
            "• Статуса подключения"
        )
        instruction_label.setStyleSheet("color: #6c757d; margin-top: 10px;")
        info_layout.addWidget(instruction_label, 2, 0, 1, 2)
        
        layout.addWidget(info_group)
    
    def _create_api_controls(self, layout):
        """
        Создание элементов управления API ключами
        """
        api_group = QGroupBox("Настройки подключения к API")
        api_layout = QGridLayout(api_group)
        
        # Поля ввода API ключей
        api_layout.addWidget(QLabel("API Key:"), 0, 0)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Введите ваш API ключ")
        api_layout.addWidget(self.api_key_edit, 0, 1)
        
        api_layout.addWidget(QLabel("API Secret:"), 1, 0)
        self.api_secret_edit = QLineEdit()
        self.api_secret_edit.setEchoMode(QLineEdit.Password)
        self.api_secret_edit.setPlaceholderText("Введите ваш API секрет")
        api_layout.addWidget(self.api_secret_edit, 1, 1)
        
        # Переключатель testnet/mainnet
        self.testnet_checkbox = QCheckBox("Использовать Testnet")
        self.testnet_checkbox.setChecked(self.config.is_testnet())
        api_layout.addWidget(self.testnet_checkbox, 2, 0, 1, 2)
        
        # Кнопки управления подключением
        button_layout = QHBoxLayout()
        
        self.connect_button = QPushButton("Подключиться")
        self.connect_button.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.connect_button.clicked.connect(self._connect_api)
        button_layout.addWidget(self.connect_button)
        
        self.disconnect_button = QPushButton("Отключиться")
        self.disconnect_button.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        self.disconnect_button.clicked.connect(self._disconnect_api)
        self.disconnect_button.setEnabled(False)  # Изначально отключена
        button_layout.addWidget(self.disconnect_button)
        
        button_layout.addStretch()
        
        # Статус подключения
        self.connection_status_label = QLabel("Не подключен")
        self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
        button_layout.addWidget(QLabel("Статус:"))
        button_layout.addWidget(self.connection_status_label)
        
        api_layout.addLayout(button_layout, 3, 0, 1, 2)
        
        # Подключение сигналов
        self.testnet_checkbox.stateChanged.connect(self._on_network_changed)
        
        # Загрузка сохраненных ключей
        self._load_saved_credentials()
        
        layout.addWidget(api_group)
    
    def _create_connection_status(self, layout):
        """
        Создание виджета статуса подключения
        """
        group = QGroupBox("Статус подключения")
        group_layout = QGridLayout(group)
        
        # Статус подключения
        self.connection_status_label = QLabel("Проверка...")
        self.connection_status_label.setStyleSheet("color: orange; font-weight: bold;")
        group_layout.addWidget(QLabel("Статус:"), 0, 0)
        group_layout.addWidget(self.connection_status_label, 0, 1)
        
        # Режим (testnet/mainnet)
        mode = "Testnet" if self.config.is_testnet() else "Mainnet"
        mode_color = "blue" if self.config.is_testnet() else "red"
        self.mode_label = QLabel(mode)
        self.mode_label.setStyleSheet(f"color: {mode_color}; font-weight: bold;")
        group_layout.addWidget(QLabel("Режим:"), 1, 0)
        group_layout.addWidget(self.mode_label, 1, 1)
        
        # Последнее обновление
        self.last_update_label = QLabel("Никогда")
        group_layout.addWidget(QLabel("Обновлено:"), 2, 0)
        group_layout.addWidget(self.last_update_label, 2, 1)
        
        layout.addWidget(group)
    
    def _create_account_info(self, layout):
        """
        Создание виджета информации об аккаунте
        """
        group = QGroupBox("Информация об аккаунте")
        group_layout = QGridLayout(group)
        
        # Тип аккаунта
        self.account_type_label = QLabel("-")
        group_layout.addWidget(QLabel("Тип аккаунта:"), 0, 0)
        group_layout.addWidget(self.account_type_label, 0, 1)
        
        # Режим маржи
        self.margin_mode_label = QLabel("-")
        group_layout.addWidget(QLabel("Режим маржи:"), 1, 0)
        group_layout.addWidget(self.margin_mode_label, 1, 1)
        
        # Общий капитал
        self.total_equity_label = QLabel("-")
        group_layout.addWidget(QLabel("Общий капитал:"), 2, 0)
        group_layout.addWidget(self.total_equity_label, 2, 1)
        
        # Доступный баланс
        self.available_balance_label = QLabel("-")
        group_layout.addWidget(QLabel("Доступно:"), 3, 0)
        group_layout.addWidget(self.available_balance_label, 3, 1)
        
        # Нереализованная прибыль/убыток
        self.unrealized_pnl_label = QLabel("-")
        group_layout.addWidget(QLabel("Нереализ. P&L:"), 4, 0)
        group_layout.addWidget(self.unrealized_pnl_label, 4, 1)
        
        layout.addWidget(group)
    
    def _create_balance_info(self, layout):
        """
        Создание таблицы балансов активов
        """
        group = QGroupBox("Баланс активов")
        group_layout = QVBoxLayout(group)
        
        # Таблица балансов
        self.balance_table = QTableWidget()
        self.balance_table.setColumnCount(4)
        self.balance_table.setHorizontalHeaderLabels(["Актив", "Всего", "Доступно", "Заблокировано"])
        
        # Настройка таблицы
        header = self.balance_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        
        self.balance_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.balance_table.setAlternatingRowColors(True)
        
        group_layout.addWidget(self.balance_table)
        layout.addWidget(group)
    
    def _create_api_info(self, layout):
        """
        Создание виджета информации об API
        """
        group = QGroupBox("API информация")
        group_layout = QGridLayout(group)
        
        # Разрешения API
        self.api_permissions_label = QLabel("-")
        group_layout.addWidget(QLabel("Разрешения:"), 0, 0)
        group_layout.addWidget(self.api_permissions_label, 0, 1)
        
        # Лимит запросов
        self.rate_limit_label = QLabel("-")
        group_layout.addWidget(QLabel("Лимит запросов:"), 1, 0)
        group_layout.addWidget(self.rate_limit_label, 1, 1)
        
        # Прогресс-бар лимита
        self.rate_limit_progress = QProgressBar()
        self.rate_limit_progress.setMaximum(120)
        self.rate_limit_progress.setValue(0)
        group_layout.addWidget(QLabel("Использовано:"), 2, 0)
        group_layout.addWidget(self.rate_limit_progress, 2, 1)
        
        layout.addWidget(group)
    
    def _create_activity_log(self, layout):
        """
        Создание лога активности
        """
        group = QGroupBox("Лог активности")
        group_layout = QVBoxLayout(group)
        
        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMaximumHeight(200)
        
        # Добавляем начальное сообщение
        self.activity_log.append("Инициализация вкладки аккаунта...")
        
        group_layout.addWidget(self.activity_log)
        layout.addWidget(group)
    
    def _create_control_buttons(self, layout):
        """
        Создание кнопок управления
        """
        button_layout = QHBoxLayout()
        
        # Кнопка обновления
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self._refresh_data)
        button_layout.addWidget(self.refresh_button)
        
        # Кнопка экспорта
        self.export_button = QPushButton("Экспорт")
        self.export_button.clicked.connect(self._export_data)
        button_layout.addWidget(self.export_button)
        
        button_layout.addStretch()
        
        # Кнопка настроек API
        self.api_settings_button = QPushButton("Настройки API")
        self.api_settings_button.clicked.connect(self._open_api_settings)
        button_layout.addWidget(self.api_settings_button)
        
        layout.addLayout(button_layout)
    
    def _load_saved_credentials(self):
        """
        Загрузка сохраненных учетных данных
        """
        try:
            environment = 'testnet' if self.testnet_checkbox.isChecked() else 'mainnet'
            credentials = self.config.get_api_credentials(environment)
            
            api_key = credentials.get('api_key', '')
            api_secret = credentials.get('api_secret', '')
            
            # Проверяем, что это не шаблонные значения
            if (api_key and not api_key.startswith('your_') and 
                api_key not in ['your_mainnet_api_key_here', 'your_testnet_api_key_here']):
                self.api_key_edit.setText(api_key)
            
            if (api_secret and not api_secret.startswith('your_') and 
                api_secret not in ['your_mainnet_api_secret_here', 'your_testnet_api_secret_here']):
                self.api_secret_edit.setText(api_secret)
                
        except Exception as e:
            self.logger.error(f"Ошибка загрузки учетных данных: {e}")
    
    def _connect_api(self):
        """
        Заглушка для кнопки подключения (подключение происходит автоматически)
        """
        QMessageBox.information(
            self, 
            "Информация", 
            "Подключение происходит автоматически при запуске приложения.\n"
            "Если подключение не установлено, проверьте настройки API ключей в конфигурации."
        )
    
    def _disconnect_api(self):
        """
        Заглушка для кнопки отключения (отключение недоступно в автоматическом режиме)
        """
        QMessageBox.information(
            self, 
            "Информация", 
            "В текущем режиме отключение от API недоступно.\n"
            "Подключение управляется автоматически при запуске приложения."
        )
    
    def _reinit_ui_with_connection(self):
        """
        Переинициализация UI после подключения
        """
        # Очищаем текущий layout (кроме заголовка и API контролов)
        layout = self.layout()
        
        # Удаляем все виджеты после API контролов
        for i in reversed(range(2, layout.count())):
            item = layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setParent(None)
        
        # Добавляем основной интерфейс
        # Сплиттер для разделения на две части
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Левая панель - основная информация
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Информация об аккаунте
        self._create_account_info(left_layout)
        
        # Баланс активов
        self._create_balance_info(left_layout)
        
        splitter.addWidget(left_widget)
        
        # Правая панель - детальная информация
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # API информация
        self._create_api_info(right_layout)
        
        # Лог активности
        self._create_activity_log(right_layout)
        
        splitter.addWidget(right_widget)
        
        # Установка пропорций сплиттера
        splitter.setSizes([600, 400])
        
        # Кнопки управления
        self._create_control_buttons(layout)
        
        # Автоматическое обновление данных
        self._refresh_data()
    
    def _clear_account_data(self):
        """
        Очистка данных аккаунта при отключении
        """
        # Здесь можно добавить логику очистки отображаемых данных
        pass
    
    def _refresh_data(self):
        """
        Обновление данных аккаунта
        """
        try:
            # Обновление состояния кнопки обновления (если виджет существует)
            if hasattr(self, 'refresh_button'):
                self.refresh_button.setEnabled(False)
                self.refresh_button.setText("Обновление...")
            
            # Остановка предыдущего воркера
            if self.worker and self.worker.isRunning():
                self.worker.stop()
            
            # Создание нового воркера
            self.worker = AccountInfoWorker(self.config, self.bybit_client)
            self.worker.data_received.connect(self._on_data_received)
            self.worker.error_occurred.connect(self._on_error_occurred)
            self.worker.finished.connect(self._on_worker_finished)
            
            # Запуск воркера
            self.worker.start()
            
            # Добавление записи в лог активности (если виджет существует)
            if hasattr(self, 'activity_log'):
                self.activity_log.append("Запрос данных аккаунта...")
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления данных: {e}")
            self._on_error_occurred(str(e))
    
    def _on_data_received(self, data: Dict[str, Any]):
        """
        Обработка полученных данных
        """
        try:
            self.account_data = data
            self._update_ui_with_data(data)
            
            # Обновление времени последнего обновления (если виджет существует)
            if hasattr(self, 'last_update_label'):
                from datetime import datetime
                self.last_update_label.setText(datetime.now().strftime("%H:%M:%S"))
            
            # Добавление записи в лог активности (если виджет существует)
            if hasattr(self, 'activity_log'):
                self.activity_log.append("Данные аккаунта успешно обновлены")
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки данных: {e}")
            self._on_error_occurred(str(e))
    
    def _on_error_occurred(self, error_message: str):
        """
        Обработка ошибок
        """
        # Обновление статуса подключения (если виджет существует)
        if hasattr(self, 'connection_status_label'):
            self.connection_status_label.setText("Ошибка подключения")
            self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # Добавление записи в лог активности (если виджет существует)
        if hasattr(self, 'activity_log'):
            self.activity_log.append(f"ОШИБКА: {error_message}")
        
        QMessageBox.warning(self, "Ошибка", f"Не удалось получить данные аккаунта:\n{error_message}")
    
    def _on_worker_finished(self):
        """
        Завершение работы воркера
        """
        # Восстановление кнопки обновления (если виджет существует)
        if hasattr(self, 'refresh_button'):
            self.refresh_button.setEnabled(True)
            self.refresh_button.setText("Обновить")
    
    def _update_ui_with_data(self, data: Dict[str, Any]):
        """
        Обновление интерфейса с полученными данными
        """
        try:
            # Обновление статуса подключения (если виджет существует)
            if hasattr(self, 'connection_status_label'):
                api_info = data.get('api_info', {})
                if api_info.get('connected', False):
                    self.connection_status_label.setText("Подключено")
                    self.connection_status_label.setStyleSheet("color: green; font-weight: bold;")
                else:
                    self.connection_status_label.setText("Отключено")
                    self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
            
            # Обновление информации об аккаунте (если виджеты существуют)
            account_info = data.get('account_info', {})
            if hasattr(self, 'account_type_label'):
                self.account_type_label.setText(account_info.get('account_type', '-'))
            if hasattr(self, 'margin_mode_label'):
                self.margin_mode_label.setText(account_info.get('margin_mode', '-'))
            
            if hasattr(self, 'total_equity_label'):
                total_equity = account_info.get('total_equity', 0)
                self.total_equity_label.setText(f"${total_equity:,.2f}")
            
            if hasattr(self, 'available_balance_label'):
                available_balance = account_info.get('total_available_balance', 0)
                self.available_balance_label.setText(f"${available_balance:,.2f}")
            
            if hasattr(self, 'unrealized_pnl_label'):
                unrealized_pnl = account_info.get('total_perp_upl', 0)
                pnl_color = "green" if unrealized_pnl >= 0 else "red"
                pnl_sign = "+" if unrealized_pnl >= 0 else ""
                self.unrealized_pnl_label.setText(f"{pnl_sign}${unrealized_pnl:,.2f}")
                self.unrealized_pnl_label.setStyleSheet(f"color: {pnl_color}; font-weight: bold;")
            
            # Обновление API информации (если виджеты существуют)
            api_info = data.get('api_info', {})
            if hasattr(self, 'api_permissions_label'):
                permissions = api_info.get('permissions', [])
                self.api_permissions_label.setText(", ".join(permissions))
            
            if hasattr(self, 'rate_limit_label') and hasattr(self, 'rate_limit_progress'):
                rate_limit = api_info.get('rate_limit', {})
                used = rate_limit.get('used', 0)
                limit = rate_limit.get('limit', 120)
                self.rate_limit_label.setText(f"{used}/{limit}")
                self.rate_limit_progress.setMaximum(limit)
                self.rate_limit_progress.setValue(used)
            
            # Обновление таблицы балансов (если метод существует)
            if hasattr(self, '_update_balance_table'):
                self._update_balance_table(data.get('balance', {}))
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления UI: {e}")
    
    def _update_balance_table(self, balance_data: Dict[str, Dict[str, float]]):
        """
        Обновление таблицы балансов
        """
        try:
            self.balance_table.setRowCount(len(balance_data))
            
            for row, (asset, balance_info) in enumerate(balance_data.items()):
                # Актив
                self.balance_table.setItem(row, 0, QTableWidgetItem(asset))
                
                # Всего
                total = balance_info.get('total', 0)
                self.balance_table.setItem(row, 1, QTableWidgetItem(f"{total:,.8f}"))
                
                # Доступно
                available = balance_info.get('available', 0)
                self.balance_table.setItem(row, 2, QTableWidgetItem(f"{available:,.8f}"))
                
                # Заблокировано
                locked = balance_info.get('locked', 0)
                self.balance_table.setItem(row, 3, QTableWidgetItem(f"{locked:,.8f}"))
                
                # Выделение строк с нулевым балансом
                if total == 0:
                    for col in range(4):
                        item = self.balance_table.item(row, col)
                        if item:
                            item.setForeground(Qt.gray)
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления таблицы балансов: {e}")
    
    def _export_data(self):
        """
        Экспорт данных аккаунта
        """
        try:
            if not self.account_data:
                QMessageBox.information(self, "Экспорт", "Нет данных для экспорта")
                return
            
            # Здесь будет реализация экспорта
            QMessageBox.information(self, "Экспорт", "Функция экспорта будет реализована")
            
        except Exception as e:
            self.logger.error(f"Ошибка экспорта данных: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {e}")
    
    def _on_network_changed(self):
        """
        Обработчик изменения сети (testnet/mainnet)
        """
        try:
            # Загрузка учетных данных для выбранной сети
            self._load_saved_credentials()
            
            # Если есть активное подключение, переподключаемся
            if self.bybit_client:
                self._disconnect_api()
                
        except Exception as e:
            self.logger.error(f"Ошибка при изменении сети: {e}")
    
    def _open_api_settings(self):
        """
        Открытие настроек API
        """
        try:
            # Здесь будет диалог настроек API
            QMessageBox.information(self, "Настройки API", "Диалог настроек API будет реализован")
            
        except Exception as e:
            self.logger.error(f"Ошибка открытия настроек API: {e}")
    
    def closeEvent(self, event):
        """
        Обработчик закрытия вкладки
        """
        try:
            # Остановка таймера
            self.update_timer.stop()
            
            # Остановка воркера
            if self.worker and self.worker.isRunning():
                self.worker.stop()
            
            event.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка закрытия вкладки аккаунта: {e}")
            event.accept()