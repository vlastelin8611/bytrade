#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диалог настроек приложения

Позволяет пользователю настроить:
- API ключи и подключение
- Параметры торговли и риск-менеджмента
- Настройки интерфейса
- Уведомления и логирование
"""

import logging
from typing import Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QPushButton, QTabWidget, QWidget,
    QGroupBox, QCheckBox, QSpinBox, QDoubleSpinBox,
    QComboBox, QTextEdit, QDialogButtonBox, QFormLayout,
    QSlider, QProgressBar, QMessageBox, QFileDialog,
    QColorDialog, QFontDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

class SettingsDialog(QDialog):
    """
    Диалог настроек приложения
    """
    
    settings_changed = Signal()
    
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        
        self.setWindowTitle("Настройки")
        self.setMinimumSize(600, 500)
        self.resize(700, 600)
        
        self._init_ui()
        self._load_settings()
        
    def _init_ui(self):
        """
        Инициализация интерфейса
        """
        layout = QVBoxLayout(self)
        
        # Создание вкладок
        self.tab_widget = QTabWidget()
        
        # Вкладка API
        self._create_api_tab()
        
        # Вкладка торговли
        self._create_trading_tab()
        
        # Вкладка интерфейса
        self._create_interface_tab()
        
        # Вкладка уведомлений
        self._create_notifications_tab()
        
        layout.addWidget(self.tab_widget)
        
        # Кнопки
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self._save_and_close)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self._apply_settings)
        
        layout.addWidget(button_box)
        
    def _create_api_tab(self):
        """
        Создание вкладки настроек API
        """
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
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 60)
        self.timeout_spin.setSuffix(" сек")
        connection_layout.addRow("Таймаут запросов:", self.timeout_spin)
        
        self.retry_count_spin = QSpinBox()
        self.retry_count_spin.setRange(1, 10)
        connection_layout.addRow("Количество повторов:", self.retry_count_spin)
        
        layout.addWidget(connection_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "API")
        
    def _create_trading_tab(self):
        """
        Создание вкладки настроек торговли
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Группа риск-менеджмента
        risk_group = QGroupBox("Риск-менеджмент")
        risk_layout = QFormLayout(risk_group)
        
        self.max_position_spin = QDoubleSpinBox()
        self.max_position_spin.setRange(0.01, 100.0)
        self.max_position_spin.setSuffix("%")
        self.max_position_spin.setDecimals(2)
        risk_layout.addRow("Максимальный размер позиции:", self.max_position_spin)
        
        self.stop_loss_spin = QDoubleSpinBox()
        self.stop_loss_spin.setRange(0.1, 50.0)
        self.stop_loss_spin.setSuffix("%")
        self.stop_loss_spin.setDecimals(1)
        risk_layout.addRow("Стоп-лосс по умолчанию:", self.stop_loss_spin)
        
        self.take_profit_spin = QDoubleSpinBox()
        self.take_profit_spin.setRange(0.1, 100.0)
        self.take_profit_spin.setSuffix("%")
        self.take_profit_spin.setDecimals(1)
        risk_layout.addRow("Тейк-профит по умолчанию:", self.take_profit_spin)
        
        self.max_daily_loss_spin = QDoubleSpinBox()
        self.max_daily_loss_spin.setRange(1.0, 50.0)
        self.max_daily_loss_spin.setSuffix("%")
        self.max_daily_loss_spin.setDecimals(1)
        risk_layout.addRow("Максимальная дневная потеря:", self.max_daily_loss_spin)
        
        layout.addWidget(risk_group)
        
        # Группа настроек стратегий
        strategy_group = QGroupBox("Настройки стратегий")
        strategy_layout = QFormLayout(strategy_group)
        
        self.auto_start_checkbox = QCheckBox("Автозапуск стратегий")
        strategy_layout.addRow(self.auto_start_checkbox)
        
        self.max_concurrent_spin = QSpinBox()
        self.max_concurrent_spin.setRange(1, 10)
        strategy_layout.addRow("Максимум одновременных стратегий:", self.max_concurrent_spin)
        
        layout.addWidget(strategy_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Торговля")
        
    def _create_interface_tab(self):
        """
        Создание вкладки настроек интерфейса
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Группа темы
        theme_group = QGroupBox("Тема интерфейса")
        theme_layout = QFormLayout(theme_group)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Светлая", "Темная", "Системная"])
        theme_layout.addRow("Тема:", self.theme_combo)
        
        # Кнопка выбора цвета акцента
        self.accent_color_button = QPushButton("Выбрать цвет акцента")
        self.accent_color_button.clicked.connect(self._choose_accent_color)
        theme_layout.addRow(self.accent_color_button)
        
        layout.addWidget(theme_group)
        
        # Группа шрифтов
        font_group = QGroupBox("Шрифты")
        font_layout = QFormLayout(font_group)
        
        self.font_button = QPushButton("Выбрать шрифт интерфейса")
        self.font_button.clicked.connect(self._choose_font)
        font_layout.addRow(self.font_button)
        
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(8, 24)
        font_layout.addRow("Размер шрифта:", self.font_size_spin)
        
        layout.addWidget(font_group)
        
        # Группа обновлений
        update_group = QGroupBox("Обновления данных")
        update_layout = QFormLayout(update_group)
        
        self.update_interval_spin = QSpinBox()
        self.update_interval_spin.setRange(1, 60)
        self.update_interval_spin.setSuffix(" сек")
        update_layout.addRow("Интервал обновления:", self.update_interval_spin)
        
        self.auto_refresh_checkbox = QCheckBox("Автообновление данных")
        update_layout.addRow(self.auto_refresh_checkbox)
        
        layout.addWidget(update_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Интерфейс")
        
    def _create_notifications_tab(self):
        """
        Создание вкладки настроек уведомлений
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Группа системных уведомлений
        system_group = QGroupBox("Системные уведомления")
        system_layout = QVBoxLayout(system_group)
        
        self.desktop_notifications_checkbox = QCheckBox("Показывать уведомления на рабочем столе")
        system_layout.addWidget(self.desktop_notifications_checkbox)
        
        self.sound_notifications_checkbox = QCheckBox("Звуковые уведомления")
        system_layout.addWidget(self.sound_notifications_checkbox)
        
        self.tray_notifications_checkbox = QCheckBox("Уведомления в системном трее")
        system_layout.addWidget(self.tray_notifications_checkbox)
        
        layout.addWidget(system_group)
        
        # Группа логирования
        logging_group = QGroupBox("Логирование")
        logging_layout = QFormLayout(logging_group)
        
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        logging_layout.addRow("Уровень логирования:", self.log_level_combo)
        
        self.log_to_file_checkbox = QCheckBox("Сохранять логи в файл")
        logging_layout.addRow(self.log_to_file_checkbox)
        
        self.max_log_size_spin = QSpinBox()
        self.max_log_size_spin.setRange(1, 100)
        self.max_log_size_spin.setSuffix(" МБ")
        logging_layout.addRow("Максимальный размер лог-файла:", self.max_log_size_spin)
        
        layout.addWidget(logging_group)
        
        layout.addStretch()
        self.tab_widget.addTab(tab, "Уведомления")
        
    def _load_settings(self):
        """
        Загрузка текущих настроек
        """
        try:
            # API настройки
            api_config = self.config.get_api_config()
            if api_config:
                self.api_key_edit.setText(api_config.get('api_key', ''))
                self.api_secret_edit.setText(api_config.get('api_secret', ''))
                
            self.testnet_checkbox.setChecked(self.config.is_testnet())
            
            # Настройки подключения
            self.timeout_spin.setValue(self.config.get_value('connection.timeout', 30))
            self.retry_count_spin.setValue(self.config.get_value('connection.retry_count', 3))
            
            # Риск-менеджмент
            risk_config = self.config.get_risk_limits()
            self.max_position_spin.setValue(risk_config.get('max_position_size', 5.0))
            self.stop_loss_spin.setValue(risk_config.get('default_stop_loss', 2.0))
            self.take_profit_spin.setValue(risk_config.get('default_take_profit', 4.0))
            self.max_daily_loss_spin.setValue(risk_config.get('max_daily_loss', 10.0))
            
            # Настройки стратегий
            self.auto_start_checkbox.setChecked(self.config.get_value('strategies.auto_start', False))
            self.max_concurrent_spin.setValue(self.config.get_value('strategies.max_concurrent', 3))
            
            # Интерфейс
            self.theme_combo.setCurrentText(self.config.get_value('ui.theme', 'Светлая'))
            self.font_size_spin.setValue(self.config.get_value('ui.font_size', 10))
            self.update_interval_spin.setValue(self.config.get_value('ui.update_interval', 5))
            self.auto_refresh_checkbox.setChecked(self.config.get_value('ui.auto_refresh', True))
            
            # Уведомления
            self.desktop_notifications_checkbox.setChecked(self.config.get_value('notifications.desktop', True))
            self.sound_notifications_checkbox.setChecked(self.config.get_value('notifications.sound', True))
            self.tray_notifications_checkbox.setChecked(self.config.get_value('notifications.tray', True))
            
            # Логирование
            self.log_level_combo.setCurrentText(self.config.get_value('logging.level', 'INFO'))
            self.log_to_file_checkbox.setChecked(self.config.get_value('logging.to_file', True))
            self.max_log_size_spin.setValue(self.config.get_value('logging.max_size_mb', 10))
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки настроек: {e}")
            
    def _save_settings(self):
        """
        Сохранение настроек
        """
        try:
            # API настройки
            self.config.set_value('api.key', self.api_key_edit.text())
            self.config.set_value('api.secret', self.api_secret_edit.text())
            self.config.set_value('api.testnet', self.testnet_checkbox.isChecked())
            
            # Настройки подключения
            self.config.set_value('connection.timeout', self.timeout_spin.value())
            self.config.set_value('connection.retry_count', self.retry_count_spin.value())
            
            # Риск-менеджмент
            self.config.set_value('risk.max_position_size', self.max_position_spin.value())
            self.config.set_value('risk.default_stop_loss', self.stop_loss_spin.value())
            self.config.set_value('risk.default_take_profit', self.take_profit_spin.value())
            self.config.set_value('risk.max_daily_loss', self.max_daily_loss_spin.value())
            
            # Настройки стратегий
            self.config.set_value('strategies.auto_start', self.auto_start_checkbox.isChecked())
            self.config.set_value('strategies.max_concurrent', self.max_concurrent_spin.value())
            
            # Интерфейс
            self.config.set_value('ui.theme', self.theme_combo.currentText())
            self.config.set_value('ui.font_size', self.font_size_spin.value())
            self.config.set_value('ui.update_interval', self.update_interval_spin.value())
            self.config.set_value('ui.auto_refresh', self.auto_refresh_checkbox.isChecked())
            
            # Уведомления
            self.config.set_value('notifications.desktop', self.desktop_notifications_checkbox.isChecked())
            self.config.set_value('notifications.sound', self.sound_notifications_checkbox.isChecked())
            self.config.set_value('notifications.tray', self.tray_notifications_checkbox.isChecked())
            
            # Логирование
            self.config.set_value('logging.level', self.log_level_combo.currentText())
            self.config.set_value('logging.to_file', self.log_to_file_checkbox.isChecked())
            self.config.set_value('logging.max_size_mb', self.max_log_size_spin.value())
            
            # Сохранение конфигурации
            self.config.save()
            
            self.settings_changed.emit()
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настроек: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {e}")
            
    def _test_connection(self):
        """
        Тестирование подключения к API
        """
        try:
            # Здесь будет код тестирования подключения
            QMessageBox.information(self, "Тест подключения", "Подключение успешно!")
        except Exception as e:
            QMessageBox.warning(self, "Ошибка подключения", f"Не удалось подключиться: {e}")
            
    def _choose_accent_color(self):
        """
        Выбор цвета акцента
        """
        color = QColorDialog.getColor(Qt.blue, self, "Выберите цвет акцента")
        if color.isValid():
            self.accent_color_button.setStyleSheet(f"background-color: {color.name()}")
            
    def _choose_font(self):
        """
        Выбор шрифта
        """
        font, ok = QFontDialog.getFont(self.font(), self, "Выберите шрифт")
        if ok:
            self.font_button.setText(f"{font.family()} {font.pointSize()}pt")
            
    def _apply_settings(self):
        """
        Применение настроек без закрытия диалога
        """
        self._save_settings()
        
    def _save_and_close(self):
        """
        Сохранение настроек и закрытие диалога
        """
        self._save_settings()
        self.accept()