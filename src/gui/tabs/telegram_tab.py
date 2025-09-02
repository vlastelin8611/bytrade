#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вкладка Telegram-уведомлений

Этот модуль содержит класс TelegramTab для управления Telegram-уведомлениями.
Включает настройки уведомлений, тихие часы, историю сообщений и тестирование.

Автор: Bybit Trading Bot
Версия: 1.0
"""

import asyncio
import logging
from datetime import datetime, time
from typing import Dict, Any, Optional

from PySide6.QtCore import (
    Qt, QTimer, QThread, Signal, QTime
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QTimeEdit, QPushButton, QTextEdit, QGroupBox, QGridLayout,
    QSplitter, QScrollArea, QFrame, QMessageBox, QLineEdit
)
from PySide6.QtGui import QFont, QTextCursor

from src.core.telegram_client import TelegramClient
from src.telegram_webhook import TelegramWebhookHandler, TelegramCommandProcessor

class TelegramTestWorker(QThread):
    """
    Рабочий поток для тестирования Telegram-уведомлений
    """
    
    # Сигналы
    test_completed = Signal(bool, str)  # success, message
    
    def __init__(self, telegram_client: TelegramClient, test_type: str, parent=None):
        super().__init__(parent)
        self.telegram_client = telegram_client
        self.test_type = test_type
        
    def run(self):
        """
        Выполнение теста
        """
        try:
            if self.test_type == "connection":
                # Тест подключения
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    result = loop.run_until_complete(
                        self.telegram_client.test_connection()
                    )
                    
                    if result['success']:
                        self.test_completed.emit(True, "Подключение к Telegram успешно!")
                    else:
                        self.test_completed.emit(False, f"Ошибка подключения: {result['message']}")
                        
                finally:
                    loop.close()
                    
            elif self.test_type == "message":
                # Тест отправки сообщения
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    result = loop.run_until_complete(
                        self.telegram_client.send_notification(
                            "test",
                            "Тестовое сообщение от торгового бота",
                            add_buttons=True
                        )
                    )
                    
                    if result['success']:
                        self.test_completed.emit(True, "Тестовое сообщение отправлено!")
                    else:
                        self.test_completed.emit(False, f"Ошибка отправки: {result['message']}")
                        
                finally:
                    loop.close()
                    
        except Exception as e:
            self.test_completed.emit(False, f"Ошибка теста: {str(e)}")


class TelegramTab(QWidget):
    """
    Вкладка для управления Telegram-уведомлениями
    """
    
    def __init__(self, db_manager, config_manager, parent=None):
        super().__init__(parent)
        
        # Основные компоненты
        self.db = db_manager
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        # Telegram клиент
        self.telegram_client: Optional[TelegramClient] = None
        
        # Webhook обработчик для кнопок
        self.webhook_handler: Optional[TelegramWebhookHandler] = None
        self.command_processor: Optional[TelegramCommandProcessor] = None
        
        # Настройки уведомлений
        self.notification_settings = {
            'trade_notifications': True,
            'error_notifications': True,
            'status_notifications': True,
            'balance_notifications': True,
            'strategy_notifications': True,
            'quiet_hours_enabled': False,
            'quiet_start': time(22, 0),  # 22:00
            'quiet_end': time(8, 0)      # 08:00
        }
        
        # История сообщений
        self.message_history = []
        
        # Рабочие потоки
        self.test_worker: Optional[TelegramTestWorker] = None
        
        # Инициализация
        self._init_telegram_client()
        self._init_ui()
        self._load_settings()
        self._load_connection_config()  # Загружаем настройки подключения
        self._setup_connections()
        
        # Таймер для обновления статистики
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_statistics)
        self.update_timer.start(30000)  # Обновление каждые 30 секунд
        
        self.logger.info("Вкладка Telegram-уведомлений инициализирована")
    
    def _init_telegram_client(self):
        """
        Инициализация Telegram клиента
        """
        try:
            # Получаем конфигурацию Telegram из config_manager
            telegram_config = self.config.get_telegram_config()
            
            bot_token = telegram_config.get('bot_token', '')
            chat_id = telegram_config.get('chat_id', '')
            
            if bot_token and chat_id:
                self.telegram_client = TelegramClient(bot_token, chat_id)
                
                # Инициализируем webhook обработчик для кнопок
                self.command_processor = TelegramCommandProcessor(
                    config_manager=self.config,
                    db_manager=self.db,
                    strategy_engine=None  # TODO: передать strategy_engine когда будет доступен
                )
                self.webhook_handler = TelegramWebhookHandler(
                    command_processor=self.command_processor
                )
                
                self.logger.info("Telegram клиент и webhook обработчик инициализированы")
            else:
                self.logger.warning("Telegram токен или chat_id не найдены в конфигурации")
                
        except Exception as e:
            self.logger.error(f"Ошибка инициализации Telegram клиента: {e}")
            self.telegram_client = None
            self.webhook_handler = None
            self.command_processor = None
    
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Telegram-уведомления")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Создаем сплиттер для разделения на две части
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Левая панель - настройки
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Группа настроек подключения
        self._create_connection_settings_group(left_layout)
        
        # Группа настроек уведомлений
        self._create_notification_settings_group(left_layout)
        
        # Группа тихих часов
        self._create_quiet_hours_group(left_layout)
        
        # Группа тестирования
        self._create_testing_group(left_layout)
        
        left_layout.addStretch()
        splitter.addWidget(left_widget)
        
        # Правая панель - история и статистика
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Группа истории сообщений
        self._create_message_history_group(right_layout)
        
        # Группа статистики
        self._create_statistics_group(right_layout)
        
        splitter.addWidget(right_widget)
        
        # Устанавливаем пропорции сплиттера
        splitter.setSizes([400, 600])
    
    def _create_connection_settings_group(self, parent_layout):
        """
        Создание группы настроек подключения
        """
        group = QGroupBox("Настройки подключения")
        layout = QGridLayout(group)
        
        # Поле для токена бота
        layout.addWidget(QLabel("Токен бота:"), 0, 0)
        self.bot_token_input = QLineEdit()
        self.bot_token_input.setPlaceholderText("Введите токен от @BotFather")
        self.bot_token_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.bot_token_input, 0, 1)
        
        # Кнопка показать/скрыть токен
        self.show_token_btn = QPushButton("👁")
        self.show_token_btn.setMaximumWidth(30)
        self.show_token_btn.setCheckable(True)
        self.show_token_btn.clicked.connect(self._toggle_token_visibility)
        layout.addWidget(self.show_token_btn, 0, 2)
        
        # Поле для Chat ID
        layout.addWidget(QLabel("Chat ID:"), 1, 0)
        self.chat_id_input = QLineEdit()
        self.chat_id_input.setPlaceholderText("Введите ID чата или канала")
        layout.addWidget(self.chat_id_input, 1, 1, 1, 2)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.save_config_btn = QPushButton("Сохранить")
        self.save_config_btn.clicked.connect(self._save_connection_config)
        buttons_layout.addWidget(self.save_config_btn)
        
        self.load_config_btn = QPushButton("Загрузить")
        self.load_config_btn.clicked.connect(self._load_connection_config)
        buttons_layout.addWidget(self.load_config_btn)
        
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout, 2, 0, 1, 3)
        
        # Статус подключения
        self.connection_status_label = QLabel("Статус: Не подключен")
        self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.connection_status_label, 3, 0, 1, 3)
        
        parent_layout.addWidget(group)
    
    def _create_notification_settings_group(self, parent_layout):
        """
        Создание группы настроек уведомлений
        """
        group = QGroupBox("Настройки уведомлений")
        layout = QVBoxLayout(group)
        
        # Чекбоксы для типов уведомлений
        self.trade_notifications_cb = QCheckBox("Уведомления о сделках")
        self.error_notifications_cb = QCheckBox("Уведомления об ошибках")
        self.status_notifications_cb = QCheckBox("Статусные уведомления")
        self.balance_notifications_cb = QCheckBox("Уведомления о балансе")
        self.strategy_notifications_cb = QCheckBox("Уведомления о стратегиях")
        
        layout.addWidget(self.trade_notifications_cb)
        layout.addWidget(self.error_notifications_cb)
        layout.addWidget(self.status_notifications_cb)
        layout.addWidget(self.balance_notifications_cb)
        layout.addWidget(self.strategy_notifications_cb)
        
        parent_layout.addWidget(group)
    
    def _create_quiet_hours_group(self, parent_layout):
        """
        Создание группы настроек тихих часов
        """
        group = QGroupBox("Тихие часы")
        layout = QVBoxLayout(group)
        
        # Включение тихих часов
        self.quiet_hours_cb = QCheckBox("Включить тихие часы")
        layout.addWidget(self.quiet_hours_cb)
        
        # Время начала и окончания
        time_layout = QHBoxLayout()
        
        time_layout.addWidget(QLabel("С:"))
        self.quiet_start_time = QTimeEdit()
        self.quiet_start_time.setDisplayFormat("HH:mm")
        time_layout.addWidget(self.quiet_start_time)
        
        time_layout.addWidget(QLabel("До:"))
        self.quiet_end_time = QTimeEdit()
        self.quiet_end_time.setDisplayFormat("HH:mm")
        time_layout.addWidget(self.quiet_end_time)
        
        layout.addLayout(time_layout)
        
        parent_layout.addWidget(group)
    
    def _create_testing_group(self, parent_layout):
        """
        Создание группы тестирования
        """
        group = QGroupBox("Тестирование")
        layout = QVBoxLayout(group)
        
        # Кнопки тестирования
        self.test_connection_btn = QPushButton("Тест подключения")
        self.test_message_btn = QPushButton("Отправить тестовое сообщение")
        
        layout.addWidget(self.test_connection_btn)
        layout.addWidget(self.test_message_btn)
        
        # Результат теста
        self.test_result_label = QLabel("Готов к тестированию")
        self.test_result_label.setWordWrap(True)
        layout.addWidget(self.test_result_label)
        
        parent_layout.addWidget(group)
    
    def _create_message_history_group(self, parent_layout):
        """
        Создание группы истории сообщений
        """
        group = QGroupBox("История сообщений")
        layout = QVBoxLayout(group)
        
        # Таблица истории
        self.history_text = QTextEdit()
        self.history_text.setReadOnly(True)
        self.history_text.setMaximumHeight(300)
        layout.addWidget(self.history_text)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        self.clear_history_btn = QPushButton("Очистить историю")
        self.refresh_history_btn = QPushButton("Обновить")
        
        buttons_layout.addWidget(self.clear_history_btn)
        buttons_layout.addWidget(self.refresh_history_btn)
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        
        parent_layout.addWidget(group)
    
    def _create_statistics_group(self, parent_layout):
        """
        Создание группы статистики
        """
        group = QGroupBox("Статистика")
        layout = QGridLayout(group)
        
        # Метки статистики
        self.total_messages_label = QLabel("Всего сообщений: 0")
        self.successful_messages_label = QLabel("Успешно отправлено: 0")
        self.failed_messages_label = QLabel("Ошибок отправки: 0")
        self.last_message_label = QLabel("Последнее сообщение: -")
        
        layout.addWidget(self.total_messages_label, 0, 0)
        layout.addWidget(self.successful_messages_label, 0, 1)
        layout.addWidget(self.failed_messages_label, 1, 0)
        layout.addWidget(self.last_message_label, 1, 1)
        
        parent_layout.addWidget(group)
    
    def _setup_connections(self):
        """
        Настройка соединений сигналов и слотов
        """
        # Настройки уведомлений
        self.trade_notifications_cb.toggled.connect(
            lambda checked: self._update_setting('trade_notifications', checked)
        )
        self.error_notifications_cb.toggled.connect(
            lambda checked: self._update_setting('error_notifications', checked)
        )
        self.status_notifications_cb.toggled.connect(
            lambda checked: self._update_setting('status_notifications', checked)
        )
        self.balance_notifications_cb.toggled.connect(
            lambda checked: self._update_setting('balance_notifications', checked)
        )
        self.strategy_notifications_cb.toggled.connect(
            lambda checked: self._update_setting('strategy_notifications', checked)
        )
        
        # Тихие часы
        self.quiet_hours_cb.toggled.connect(
            lambda checked: self._update_setting('quiet_hours_enabled', checked)
        )
        self.quiet_start_time.timeChanged.connect(self._update_quiet_start)
        self.quiet_end_time.timeChanged.connect(self._update_quiet_end)
        
        # Тестирование
        self.test_connection_btn.clicked.connect(self._test_connection)
        self.test_message_btn.clicked.connect(self._test_message)
        
        # История
        self.clear_history_btn.clicked.connect(self._clear_history)
        self.refresh_history_btn.clicked.connect(self._refresh_history)
        
        # Настройки подключения
        self.bot_token_input.textChanged.connect(self._on_connection_config_changed)
        self.chat_id_input.textChanged.connect(self._on_connection_config_changed)
    
    def _load_settings(self):
        """
        Загрузка настроек из конфигурации
        """
        try:
            # Загружаем настройки уведомлений
            telegram_config = self.config.get_telegram_config()
            
            # Обновляем настройки из конфигурации
            for key, default_value in self.notification_settings.items():
                if key in telegram_config:
                    if key in ['quiet_start', 'quiet_end']:
                        # Для времени нужна специальная обработка
                        time_str = telegram_config[key]
                        if isinstance(time_str, str):
                            hour, minute = map(int, time_str.split(':'))
                            self.notification_settings[key] = time(hour, minute)
                    else:
                        self.notification_settings[key] = telegram_config[key]
            
            # Применяем настройки к UI
            self._apply_settings_to_ui()
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки настроек Telegram: {e}")
    
    def _apply_settings_to_ui(self):
        """
        Применение настроек к элементам интерфейса
        """
        # Настройки уведомлений
        self.trade_notifications_cb.setChecked(
            self.notification_settings['trade_notifications']
        )
        self.error_notifications_cb.setChecked(
            self.notification_settings['error_notifications']
        )
        self.status_notifications_cb.setChecked(
            self.notification_settings['status_notifications']
        )
        self.balance_notifications_cb.setChecked(
            self.notification_settings['balance_notifications']
        )
        self.strategy_notifications_cb.setChecked(
            self.notification_settings['strategy_notifications']
        )
        
        # Тихие часы
        self.quiet_hours_cb.setChecked(
            self.notification_settings['quiet_hours_enabled']
        )
        
        quiet_start = self.notification_settings['quiet_start']
        quiet_end = self.notification_settings['quiet_end']
        
        self.quiet_start_time.setTime(
            QTime(quiet_start.hour, quiet_start.minute)
        )
        self.quiet_end_time.setTime(
            QTime(quiet_end.hour, quiet_end.minute)
        )
    
    def _update_setting(self, key: str, value: Any):
        """
        Обновление настройки
        
        Args:
            key: Ключ настройки
            value: Новое значение
        """
        try:
            self.notification_settings[key] = value
            self._save_settings()
            self.logger.debug(f"Настройка {key} обновлена: {value}")
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления настройки {key}: {e}")
    
    def _update_quiet_start(self, qtime):
        """
        Обновление времени начала тихих часов
        """
        try:
            self.notification_settings['quiet_start'] = time(
                qtime.hour(), qtime.minute()
            )
            self._save_settings()
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления времени начала тихих часов: {e}")
    
    def _update_quiet_end(self, qtime):
        """
        Обновление времени окончания тихих часов
        """
        try:
            self.notification_settings['quiet_end'] = time(
                qtime.hour(), qtime.minute()
            )
            self._save_settings()
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления времени окончания тихих часов: {e}")
    
    def _save_settings(self):
        """
        Сохранение настроек в конфигурацию
        """
        try:
            # Подготавливаем данные для сохранения
            settings_to_save = self.notification_settings.copy()
            
            # Конвертируем время в строки
            settings_to_save['quiet_start'] = self.notification_settings['quiet_start'].strftime('%H:%M')
            settings_to_save['quiet_end'] = self.notification_settings['quiet_end'].strftime('%H:%M')
            
            # Сохраняем в конфигурацию
            self.config.update_telegram_config(settings_to_save)
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек Telegram: {e}")
    
    def _toggle_token_visibility(self):
        """
        Переключение видимости токена
        """
        if self.show_token_btn.isChecked():
            self.bot_token_input.setEchoMode(QLineEdit.Normal)
            self.show_token_btn.setText("🙈")
        else:
            self.bot_token_input.setEchoMode(QLineEdit.Password)
            self.show_token_btn.setText("👁")
    
    def _save_connection_config(self):
        """
        Сохранение настроек подключения
        """
        try:
            bot_token = self.bot_token_input.text().strip()
            chat_id = self.chat_id_input.text().strip()
            
            if not bot_token:
                QMessageBox.warning(self, "Ошибка", "Введите токен бота")
                return
            
            if not chat_id:
                QMessageBox.warning(self, "Ошибка", "Введите Chat ID")
                return
            
            # Сохраняем в конфигурацию
            connection_config = {
                'bot_token': bot_token,
                'chat_id': chat_id
            }
            
            self.config.update_telegram_config(connection_config)
            
            # Переинициализируем клиент
            self._init_telegram_client()
            
            # Обновляем статус
            self._update_connection_status()
            
            QMessageBox.information(self, "Успех", "Настройки подключения сохранены")
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек подключения: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {str(e)}")
    
    def _load_connection_config(self):
        """
        Загрузка настроек подключения
        """
        try:
            telegram_config = self.config.get_telegram_config()
            
            bot_token = telegram_config.get('bot_token', '')
            chat_id = telegram_config.get('chat_id', '')
            
            self.bot_token_input.setText(bot_token)
            self.chat_id_input.setText(chat_id)
            
            self._update_connection_status()
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки настроек подключения: {e}")
    
    def _on_connection_config_changed(self):
        """
        Обработчик изменения настроек подключения
        """
        self._update_connection_status()
    
    def _update_connection_status(self):
        """
        Обновление статуса подключения
        """
        try:
            bot_token = self.bot_token_input.text().strip()
            chat_id = self.chat_id_input.text().strip()
            
            if bot_token and chat_id and self.telegram_client:
                self.connection_status_label.setText("Статус: Подключен")
                self.connection_status_label.setStyleSheet("color: green; font-weight: bold;")
            elif bot_token and chat_id:
                self.connection_status_label.setText("Статус: Настроен, но не инициализирован")
                self.connection_status_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.connection_status_label.setText("Статус: Не подключен")
                self.connection_status_label.setStyleSheet("color: red; font-weight: bold;")
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса подключения: {e}")
    
    def _test_connection(self):
        """
        Тестирование подключения к Telegram
        """
        if not self.telegram_client:
            self.test_result_label.setText("❌ Telegram клиент не инициализирован")
            return
        
        if self.test_worker and self.test_worker.isRunning():
            return
        
        self.test_result_label.setText("🔄 Тестирование подключения...")
        self.test_connection_btn.setEnabled(False)
        
        self.test_worker = TelegramTestWorker(
            self.telegram_client, "connection", self
        )
        self.test_worker.test_completed.connect(self._on_test_completed)
        self.test_worker.start()
    
    def _test_message(self):
        """
        Тестирование отправки сообщения
        """
        if not self.telegram_client:
            self.test_result_label.setText("❌ Telegram клиент не инициализирован")
            return
        
        if self.test_worker and self.test_worker.isRunning():
            return
        
        self.test_result_label.setText("🔄 Отправка тестового сообщения...")
        self.test_message_btn.setEnabled(False)
        
        self.test_worker = TelegramTestWorker(
            self.telegram_client, "message", self
        )
        self.test_worker.test_completed.connect(self._on_test_completed)
        self.test_worker.start()
    
    def _on_test_completed(self, success: bool, message: str):
        """
        Обработка завершения теста
        
        Args:
            success: Успешность теста
            message: Сообщение о результате
        """
        if success:
            self.test_result_label.setText(f"✅ {message}")
        else:
            self.test_result_label.setText(f"❌ {message}")
        
        self.test_connection_btn.setEnabled(True)
        self.test_message_btn.setEnabled(True)
        
        # Добавляем в историю
        self._add_message_to_history("Тест", message, "Выполнено" if success else "Ошибка")
    
    def _clear_history(self):
        """
        Очистка истории сообщений
        """
        self.message_history.clear()
        self.history_text.clear()
        self._update_statistics()
    
    def _refresh_history(self):
        """
        Обновление отображения истории
        """
        self._update_history_display()
        self._update_statistics()
    
    def _add_message_to_history(self, msg_type: str, message: str, status: str):
        """
        Добавление сообщения в историю
        
        Args:
            msg_type: Тип сообщения
            message: Текст сообщения
            status: Статус отправки
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        history_entry = {
            'timestamp': timestamp,
            'type': msg_type,
            'message': message,
            'status': status
        }
        
        self.message_history.append(history_entry)
        
        # Ограничиваем размер истории
        if len(self.message_history) > 100:
            self.message_history = self.message_history[-100:]
        
        self._update_history_display()
        self._update_statistics()
    
    def _update_history_display(self):
        """
        Обновление отображения истории сообщений
        """
        self.history_text.clear()
        
        for entry in reversed(self.message_history[-20:]):  # Показываем последние 20
            status_icon = "✅" if entry['status'] == "Отправлено" else "❌"
            
            text = f"[{entry['timestamp']}] {status_icon} {entry['type']}: {entry['message'][:100]}"
            if len(entry['message']) > 100:
                text += "..."
            
            self.history_text.append(text)
        
        # Прокручиваем к началу
        cursor = self.history_text.textCursor()
        cursor.movePosition(QTextCursor.Start)
        self.history_text.setTextCursor(cursor)
    
    def _update_statistics(self):
        """
        Обновление статистики
        """
        total = len(self.message_history)
        successful = len([h for h in self.message_history if h['status'] == "Отправлено"])
        failed = total - successful
        
        self.total_messages_label.setText(f"Всего сообщений: {total}")
        self.successful_messages_label.setText(f"Успешно отправлено: {successful}")
        self.failed_messages_label.setText(f"Ошибок отправки: {failed}")
        
        if self.message_history:
            last_message = self.message_history[-1]
            self.last_message_label.setText(
                f"Последнее сообщение: {last_message['timestamp']}"
            )
        else:
            self.last_message_label.setText("Последнее сообщение: -")
    
    def _add_log(self, message: str):
        """
        Добавление записи в лог
        
        Args:
            message: Сообщение для лога
        """
        self.logger.info(f"[Telegram] {message}")
    
    def _is_quiet_hours(self) -> bool:
        """
        Проверка, активны ли тихие часы
        
        Returns:
            bool: True если сейчас тихие часы
        """
        if not self.notification_settings['quiet_hours_enabled']:
            return False
        
        current_time = datetime.now().time()
        quiet_start = self.notification_settings['quiet_start']
        quiet_end = self.notification_settings['quiet_end']
        
        if quiet_start <= quiet_end:
            # Тихие часы в пределах одного дня
            return quiet_start <= current_time <= quiet_end
        else:
            # Тихие часы переходят через полночь
            return current_time >= quiet_start or current_time <= quiet_end
    
    def send_notification(self, msg_type: str, message: str, add_buttons: bool = False) -> bool:
        """
        Отправка уведомления через Telegram
        
        Args:
            msg_type: Тип сообщения (trade, error, status, balance, strategy)
            message: Текст сообщения
            add_buttons: Добавлять ли интерактивные кнопки
            
        Returns:
            bool: True если отправлено успешно
        """
        try:
            # Проверяем, включены ли уведомления данного типа
            setting_key = f"{msg_type}_notifications"
            if setting_key in self.notification_settings:
                if not self.notification_settings[setting_key]:
                    self._add_log(f"Уведомления типа {msg_type} отключены")
                    return False
            
            # Проверяем тихие часы
            if self._is_quiet_hours():
                self._add_log(f"Уведомление не отправлено - тихие часы")
                self._add_message_to_history(msg_type.capitalize(), message, "Тихие часы")
                return False
            
            # Отправляем уведомление
            if self.telegram_client:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        result = loop.run_until_complete(
                            self.telegram_client.send_notification(msg_type, message, add_buttons)
                        )
                        
                        if result['success']:
                            self._add_message_to_history(msg_type.capitalize(), message, "Отправлено")
                            self._add_log(f"Уведомление отправлено: [{msg_type}]: {message}")
                            return True
                        else:
                            self._add_message_to_history(msg_type.capitalize(), message, "Ошибка")
                            self._add_log(f"Ошибка отправки уведомления: {result['message']}")
                            return False
                    
                    finally:
                        loop.close()
                        
                except Exception as e:
                    self.logger.error(f"Ошибка асинхронной отправки: {e}")
                    self._add_message_to_history(msg_type.capitalize(), message, "Ошибка")
                    return False
            else:
                # Если клиент не инициализирован, только логируем
                self._add_message_to_history(msg_type.capitalize(), message, "Не отправлено")
                self._add_log(f"Telegram клиент не инициализирован. Сообщение: [{msg_type}]: {message}")
                return False
        
        except Exception as e:
            self.logger.error(f"Ошибка отправки уведомления: {e}")
            self._add_message_to_history(msg_type.capitalize(), message, "Ошибка")
            return False
    
    def send_status_update(self, account_data: Dict[str, Any]) -> bool:
        """
        Отправка обновления статуса аккаунта
        
        Args:
            account_data: Данные аккаунта
            
        Returns:
            bool: True если отправлено успешно
        """
        try:
            if not self.telegram_client:
                return False
            
            # Запускаем асинхронную отправку
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                result = loop.run_until_complete(
                    self.telegram_client.send_status_update(account_data)
                )
                
                if result['success']:
                    self._add_log("Отправлен статус аккаунта")
                    return True
                else:
                    self._add_log(f"Ошибка отправки статуса: {result['message']}")
                    return False
            
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Ошибка отправки статуса: {e}")
            return False
    
    def update_database_reference(self, new_db_manager):
        """
        Обновление ссылки на менеджер базы данных
        
        Args:
            new_db_manager: Новый экземпляр DatabaseManager
        """
        try:
            self.db = new_db_manager
            
            # Обновляем ссылку в command_processor если он существует
            if self.command_processor:
                self.command_processor.db_manager = new_db_manager
                
            self.logger.info("Ссылка на базу данных обновлена в TelegramTab")
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления ссылки на БД в TelegramTab: {e}")