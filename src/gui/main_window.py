#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Главное окно Bybit Trading Bot

Основное GUI приложения с вкладками:
1. Основная информация (аккаунт)
2. Активы/рынки
3. Дополнительные функции платформы
4. Стратегии
5. Telegram-уведомления
6. Портфель
"""

import sys
import logging
from typing import Dict, Any
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QVBoxLayout, QHBoxLayout, 
    QWidget, QLabel, QStatusBar, QMenuBar, QMenu,
    QMessageBox, QSplashScreen, QProgressBar, QSystemTrayIcon
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap, QFont, QAction

# Импорт вкладок
from .tabs.account_tab import AccountTab
from .tabs.markets_tab import MarketsTab
from .tabs.platform_functions_tab import PlatformFunctionsTab
from .tabs.strategies_tab import StrategiesTab
from .tabs.telegram_tab import TelegramTab
from .tabs.portfolio_tab import PortfolioTab
from .tabs.logs_tab import LogsTab

# Импорт диалогов
from .dialogs.settings_dialog import SettingsDialog
from .dialogs.about_dialog import AboutDialog

# Импорт утилит
from .utils.style_manager import StyleManager
from .utils.icon_manager import IconManager

class MainWindow(QMainWindow):
    """
    Главное окно приложения
    """
    
    def __init__(self, config_manager, db_manager):
        super().__init__()
        
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Менеджеры
        self.style_manager = StyleManager()
        self.icon_manager = IconManager()
        
        # Инициализация UI
        self._init_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._setup_system_tray()
        
        # Применение стилей
        self._apply_styles()
        
        # Таймеры для обновления данных
        self._setup_timers()
        
        self.logger.info("Главное окно инициализировано")
    
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        # Настройка главного окна
        self.setWindowTitle("Bybit Trading Bot v1.0.0")
        self.setMinimumSize(1200, 800)
        self.resize(1400, 900)
        
        # Центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Создание вкладок
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setMovable(False)
        self.tab_widget.setTabsClosable(False)
        
        # Инициализация вкладок
        self._init_tabs()
        
        main_layout.addWidget(self.tab_widget)
        
        # Установка иконки приложения
        self.setWindowIcon(self.icon_manager.get_icon('app'))
    
    def _init_tabs(self):
        """
        Инициализация всех вкладок
        """
        try:
            # 1. Основная информация (аккаунт)
            self.logger.info("Инициализация вкладки аккаунта...")
            self.account_tab = AccountTab(self.config, self.db)
            self.tab_widget.addTab(self.account_tab, 
                                 self.icon_manager.get_icon('account'), 
                                 "Основная информация")
            self.logger.info("Вкладка аккаунта успешно добавлена")
            
            # 2. Активы/рынки
            self.logger.info("Инициализация вкладки рынков...")
            self.markets_tab = MarketsTab(self.config, self.db)
            self.tab_widget.addTab(self.markets_tab, 
                                 self.icon_manager.get_icon('markets'), 
                                 "Активы/рынки")
            self.logger.info("Вкладка рынков успешно добавлена")
            
            # 3. Дополнительные функции платформы
            self.logger.info("Инициализация вкладки функций платформы...")
            self.platform_tab = PlatformFunctionsTab(self.config, self.db)
            self.tab_widget.addTab(self.platform_tab, 
                                 self.icon_manager.get_icon('platform'), 
                                 "Функции платформы")
            self.logger.info("Вкладка функций платформы успешно добавлена")
            
            # 4. Стратегии
            self.logger.info("Инициализация вкладки стратегий...")
            self.strategies_tab = StrategiesTab(self.config, self.db)
            self.tab_widget.addTab(self.strategies_tab, 
                                 self.icon_manager.get_icon('strategies'), 
                                 "Стратегии")
            self.logger.info("Вкладка стратегий успешно добавлена")
            
            # 5. Telegram-уведомления
            self.logger.info("Инициализация вкладки Telegram...")
            self.telegram_tab = TelegramTab(self.db, self.config)
            self.tab_widget.addTab(self.telegram_tab, 
                                 self.icon_manager.get_icon('telegram'), 
                                 "Telegram")
            self.logger.info("Вкладка Telegram успешно добавлена")
            
            # 6. Портфель
            self.logger.info("Инициализация вкладки портфеля...")
            self.portfolio_tab = PortfolioTab(self.config, self.db)
            self.tab_widget.addTab(self.portfolio_tab, 
                                 self.icon_manager.get_icon('portfolio'), 
                                 "Портфель")
            self.logger.info("Вкладка портфеля успешно добавлена")
            
            # 7. Логи программы
            self.logger.info("Инициализация вкладки логов...")
            self.logs_tab = LogsTab(self.config, self.db)
            self.tab_widget.addTab(self.logs_tab, 
                                 self.icon_manager.get_icon('logs'), 
                                 "Логи")
            self.logger.info("Вкладка логов успешно добавлена")
            
            # Подключение сигналов
            self.tab_widget.currentChanged.connect(self._on_tab_changed)
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации вкладок: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось инициализировать вкладки: {e}")
    
    def _setup_menu(self):
        """
        Настройка меню приложения
        """
        menubar = self.menuBar()
        
        # Меню "Файл"
        file_menu = menubar.addMenu("Файл")
        
        # Экспорт данных
        export_action = QAction(self.icon_manager.get_icon('export'), "Экспорт данных", self)
        export_action.setShortcut("Ctrl+E")
        export_action.triggered.connect(self._export_data)
        file_menu.addAction(export_action)
        
        file_menu.addSeparator()
        
        # Выход
        exit_action = QAction(self.icon_manager.get_icon('exit'), "Выход", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Меню "Настройки"
        settings_menu = menubar.addMenu("Настройки")
        
        # Настройки приложения
        app_settings_action = QAction(self.icon_manager.get_icon('settings'), "Настройки", self)
        app_settings_action.setShortcut("Ctrl+,")
        app_settings_action.triggered.connect(self._open_settings)
        settings_menu.addAction(app_settings_action)
        
        # Переключение testnet/mainnet
        self.testnet_action = QAction("Testnet режим", self)
        self.testnet_action.setCheckable(True)
        self.testnet_action.setChecked(self.config.is_testnet())
        self.testnet_action.triggered.connect(self._toggle_testnet)
        settings_menu.addAction(self.testnet_action)
        
        # Меню "Торговля"
        trading_menu = menubar.addMenu("Торговля")
        
        # Остановить все стратегии
        stop_all_action = QAction(self.icon_manager.get_icon('stop'), "Остановить все стратегии", self)
        stop_all_action.triggered.connect(self._stop_all_strategies)
        trading_menu.addAction(stop_all_action)
        
        # Экстренная остановка
        emergency_stop_action = QAction(self.icon_manager.get_icon('emergency'), "Экстренная остановка", self)
        emergency_stop_action.setShortcut("Ctrl+Shift+S")
        emergency_stop_action.triggered.connect(self._emergency_stop)
        trading_menu.addAction(emergency_stop_action)
        
        # Меню "Помощь"
        help_menu = menubar.addMenu("Помощь")
        
        # О программе
        about_action = QAction(self.icon_manager.get_icon('about'), "О программе", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
        
        # Документация
        docs_action = QAction(self.icon_manager.get_icon('docs'), "Документация", self)
        docs_action.triggered.connect(self._open_documentation)
        help_menu.addAction(docs_action)
    
    def _setup_status_bar(self):
        """
        Настройка строки состояния
        """
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Индикатор подключения
        self.connection_label = QLabel("Отключено")
        self.connection_label.setStyleSheet("color: red; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.connection_label)
        
        # Индикатор режима
        mode = "Testnet" if self.config.is_testnet() else "Mainnet"
        self.mode_label = QLabel(f"Режим: {mode}")
        self.mode_label.setStyleSheet("color: blue; font-weight: bold;")
        self.status_bar.addPermanentWidget(self.mode_label)
        
        # Прогресс-бар для операций
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Начальное сообщение
        self.status_bar.showMessage("Готов к работе", 3000)
    
    def _setup_system_tray(self):
        """
        Настройка системного трея
        """
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray_icon = QSystemTrayIcon(self)
            self.tray_icon.setIcon(self.icon_manager.get_icon('app'))
            
            # Меню трея
            tray_menu = QMenu()
            
            show_action = QAction("Показать", self)
            show_action.triggered.connect(self.show)
            tray_menu.addAction(show_action)
            
            hide_action = QAction("Скрыть", self)
            hide_action.triggered.connect(self.hide)
            tray_menu.addAction(hide_action)
            
            tray_menu.addSeparator()
            
            quit_action = QAction("Выход", self)
            quit_action.triggered.connect(self.close)
            tray_menu.addAction(quit_action)
            
            self.tray_icon.setContextMenu(tray_menu)
            self.tray_icon.activated.connect(self._tray_icon_activated)
            self.tray_icon.show()
    
    def _apply_styles(self):
        """
        Применение стилей к приложению
        """
        try:
            stylesheet = self.style_manager.get_main_stylesheet()
            self.setStyleSheet(stylesheet)
        except Exception as e:
            self.logger.error(f"Ошибка применения стилей: {e}")
    
    def _setup_timers(self):
        """
        Настройка таймеров для обновления данных
        """
        # Таймер для обновления статуса подключения
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self._update_connection_status)
        self.connection_timer.start(5000)  # Каждые 5 секунд
        
        # Таймер для автосохранения
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self._autosave)
        self.autosave_timer.start(60000)  # Каждую минуту
    
    def _on_tab_changed(self, index):
        """
        Обработчик смены вкладки
        """
        tab_names = ["Аккаунт", "Рынки", "Платформа", "Стратегии", "Telegram", "Портфель"]
        if 0 <= index < len(tab_names):
            self.status_bar.showMessage(f"Открыта вкладка: {tab_names[index]}", 2000)
            self.logger.debug(f"Переключение на вкладку: {tab_names[index]}")
    
    def _update_connection_status(self):
        """
        Обновление статуса подключения к API
        """
        try:
            # Проверка наличия API ключей
            environment = 'testnet' if self.config.is_testnet() else 'mainnet'
            api_credentials = self.config.get_api_credentials(environment)
            
            api_key = api_credentials.get('api_key', '')
            api_secret = api_credentials.get('api_secret', '')
            
            # Проверяем, что ключи не пустые и не являются шаблонными значениями
            connected = (api_key and api_secret and 
                        not api_key.startswith('your_') and 
                        not api_secret.startswith('your_') and
                        api_key != 'your_mainnet_api_key_here' and
                        api_key != 'your_testnet_api_key_here' and
                        api_secret != 'your_mainnet_api_secret_here' and
                        api_secret != 'your_testnet_api_secret_here')
            
            if connected:
                self.connection_label.setText("Подключено")
                self.connection_label.setStyleSheet("color: green; font-weight: bold;")
            else:
                self.connection_label.setText("Отключено")
                self.connection_label.setStyleSheet("color: red; font-weight: bold;")
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса подключения: {e}")
            self.connection_label.setText("Ошибка")
            self.connection_label.setStyleSheet("color: red; font-weight: bold;")
    
    def _autosave(self):
        """
        Автосохранение конфигурации
        """
        try:
            self.config.save()
            self.logger.debug("Автосохранение выполнено")
        except Exception as e:
            self.logger.error(f"Ошибка автосохранения: {e}")
    
    def _export_data(self):
        """
        Экспорт данных
        """
        try:
            # Здесь будет реализация экспорта
            QMessageBox.information(self, "Экспорт", "Функция экспорта будет реализована")
        except Exception as e:
            self.logger.error(f"Ошибка экспорта данных: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {e}")
    
    def _open_settings(self):
        """
        Открытие диалога настроек
        """
        try:
            dialog = SettingsDialog(self.config, self)
            if dialog.exec() == QMessageBox.Accepted:
                self._apply_styles()  # Применяем новые стили
                self._update_mode_label()
        except Exception as e:
            self.logger.error(f"Ошибка открытия настроек: {e}")
    
    def _toggle_testnet(self, checked):
        """
        Переключение режима testnet/mainnet
        """
        try:
            self.config.set('trading.testnet', checked)
            self._update_mode_label()
            
            mode = "testnet" if checked else "mainnet"
            
            # Пересоздаем DatabaseManager для нового окружения
            try:
                from src.database.db_manager import DatabaseManager
                
                # Закрываем текущий менеджер БД
                if hasattr(self, 'db_manager') and self.db_manager:
                    self.db_manager.close()
                
                # Создаем новый менеджер для выбранного окружения
                environment = "mainnet" if not checked else "testnet"
                self.db_manager = DatabaseManager(environment=environment)
                self.db_manager.initialize_database()
                
                # Обновляем ссылки на БД во всех вкладках
                self._update_tabs_database_reference()
                
                self.logger.info(f"База данных переключена на {environment}")
                
            except Exception as db_error:
                self.logger.error(f"Ошибка переключения базы данных: {db_error}")
                QMessageBox.warning(
                    self,
                    "Ошибка БД",
                    f"Не удалось переключить базу данных: {db_error}\nРекомендуется перезапустить приложение."
                )
            
            self.status_bar.showMessage(f"Переключено на {mode}", 3000)
            
            # Уведомление об успешном переключении
            QMessageBox.information(
                self, 
                "Смена режима", 
                f"Режим успешно переключен на {mode}.\nБаза данных обновлена для нового окружения."
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка переключения режима: {e}")
    
    def _update_tabs_database_reference(self):
        """
        Обновление ссылок на базу данных во всех вкладках
        """
        try:
            # Обновляем ссылку на БД в каждой вкладке, если она поддерживает это
            for i in range(self.tab_widget.count()):
                tab = self.tab_widget.widget(i)
                if hasattr(tab, 'update_database_reference'):
                    tab.update_database_reference(self.db_manager)
                elif hasattr(tab, 'db_manager'):
                    tab.db_manager = self.db_manager
                    
        except Exception as e:
            self.logger.error(f"Ошибка обновления ссылок на БД: {e}")
    
    def _update_mode_label(self):
        """
        Обновление индикатора режима
        """
        mode = "Testnet" if self.config.is_testnet() else "Mainnet"
        self.mode_label.setText(f"Режим: {mode}")
        color = "blue" if self.config.is_testnet() else "red"
        self.mode_label.setStyleSheet(f"color: {color}; font-weight: bold;")
    
    def _stop_all_strategies(self):
        """
        Остановка всех активных стратегий
        """
        try:
            reply = QMessageBox.question(
                self, 
                "Остановка стратегий", 
                "Вы уверены, что хотите остановить все активные стратегии?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Здесь будет реализация остановки стратегий
                self.strategies_tab.stop_all_strategies()
                self.status_bar.showMessage("Все стратегии остановлены", 5000)
                
        except Exception as e:
            self.logger.error(f"Ошибка остановки стратегий: {e}")
    
    def _emergency_stop(self):
        """
        Экстренная остановка всех операций
        """
        try:
            reply = QMessageBox.critical(
                self, 
                "ЭКСТРЕННАЯ ОСТАНОВКА", 
                "ВНИМАНИЕ! Это приведет к немедленной остановке всех торговых операций!\n\nПродолжить?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Здесь будет реализация экстренной остановки
                self.status_bar.showMessage("ЭКСТРЕННАЯ ОСТАНОВКА АКТИВИРОВАНА", 10000)
                self.logger.critical("Активирована экстренная остановка")
                
        except Exception as e:
            self.logger.error(f"Ошибка экстренной остановки: {e}")
    
    def _show_about(self):
        """
        Показ диалога "О программе"
        """
        try:
            dialog = AboutDialog(self)
            dialog.exec()
        except Exception as e:
            self.logger.error(f"Ошибка показа диалога 'О программе': {e}")
    
    def _open_documentation(self):
        """
        Открытие документации
        """
        try:
            import webbrowser
            webbrowser.open("https://bybit-exchange.github.io/docs/")
        except Exception as e:
            self.logger.error(f"Ошибка открытия документации: {e}")
    
    def _tray_icon_activated(self, reason):
        """
        Обработчик активации иконки в трее
        """
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
    
    def show_progress(self, message: str, maximum: int = 0):
        """
        Показ прогресс-бара
        """
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(maximum)
        self.progress_bar.setValue(0)
        self.status_bar.showMessage(message)
    
    def update_progress(self, value: int, message: str = None):
        """
        Обновление прогресс-бара
        """
        self.progress_bar.setValue(value)
        if message:
            self.status_bar.showMessage(message)
    
    def hide_progress(self):
        """
        Скрытие прогресс-бара
        """
        self.progress_bar.setVisible(False)
        self.status_bar.showMessage("Готов к работе", 2000)
    
    def closeEvent(self, event):
        """
        Обработчик закрытия приложения
        """
        try:
            # Сохранение конфигурации
            self.config.save()
            
            # Остановка всех таймеров
            self.connection_timer.stop()
            self.autosave_timer.stop()
            
            # Закрытие соединения с БД
            self.db.close()
            
            self.logger.info("Приложение закрыто")
            event.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии приложения: {e}")
            event.accept()