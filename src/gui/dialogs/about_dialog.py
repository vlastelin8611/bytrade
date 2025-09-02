#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Диалог "О программе"

Отображает информацию о приложении:
- Версия и описание
- Информация об авторе
- Лицензия
- Системная информация
"""

import sys
import platform
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QTextEdit, QTabWidget, QWidget,
    QDialogButtonBox, QGroupBox, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPixmap

class AboutDialog(QDialog):
    """
    Диалог "О программе"
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("О программе")
        self.setFixedSize(500, 400)
        self.setModal(True)
        
        self._init_ui()
        
    def _init_ui(self):
        """
        Инициализация интерфейса
        """
        layout = QVBoxLayout(self)
        
        # Создание вкладок
        tab_widget = QTabWidget()
        
        # Вкладка "О программе"
        self._create_about_tab(tab_widget)
        
        # Вкладка "Система"
        self._create_system_tab(tab_widget)
        
        # Вкладка "Лицензия"
        self._create_license_tab(tab_widget)
        
        layout.addWidget(tab_widget)
        
        # Кнопка закрытия
        button_box = QDialogButtonBox(QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)
        
    def _create_about_tab(self, tab_widget):
        """
        Создание вкладки "О программе"
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Заголовок
        title_label = QLabel("Bybit Trading Bot")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Версия
        version_label = QLabel("Версия 1.0.0")
        version_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(version_label)
        
        layout.addSpacing(20)
        
        # Описание
        description = QTextEdit()
        description.setReadOnly(True)
        description.setMaximumHeight(150)
        description.setHtml("""
        <p><b>Bybit Trading Bot</b> - это профессиональное приложение для автоматической торговли 
        на криптовалютной бирже Bybit.</p>
        
        <p><b>Основные возможности:</b></p>
        <ul>
            <li>Автоматические торговые стратегии</li>
            <li>Управление рисками</li>
            <li>Мониторинг портфеля в реальном времени</li>
            <li>Telegram уведомления</li>
            <li>Бэктестинг стратегий</li>
            <li>Анализ рынка и технические индикаторы</li>
        </ul>
        
        <p><b>Автор:</b> AI Assistant</p>
        <p><b>Лицензия:</b> MIT License</p>
        """)
        layout.addWidget(description)
        
        layout.addStretch()
        tab_widget.addTab(tab, "О программе")
        
    def _create_system_tab(self, tab_widget):
        """
        Создание вкладки "Система"
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Группа системной информации
        system_group = QGroupBox("Системная информация")
        system_layout = QGridLayout(system_group)
        
        # Информация о системе
        system_info = [
            ("Операционная система:", f"{platform.system()} {platform.release()}"),
            ("Архитектура:", platform.machine()),
            ("Процессор:", platform.processor() or "Неизвестно"),
            ("Python версия:", f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
            ("PySide6 версия:", self._get_pyside_version()),
        ]
        
        for i, (label, value) in enumerate(system_info):
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: bold;")
            value_widget = QLabel(value)
            
            system_layout.addWidget(label_widget, i, 0)
            system_layout.addWidget(value_widget, i, 1)
            
        layout.addWidget(system_group)
        
        # Группа информации о приложении
        app_group = QGroupBox("Информация о приложении")
        app_layout = QGridLayout(app_group)
        
        app_info = [
            ("Путь к приложению:", sys.executable),
            ("Рабочая директория:", sys.path[0]),
            ("Кодировка:", sys.getdefaultencoding()),
        ]
        
        for i, (label, value) in enumerate(app_info):
            label_widget = QLabel(label)
            label_widget.setStyleSheet("font-weight: bold;")
            value_widget = QLabel(value)
            value_widget.setWordWrap(True)
            
            app_layout.addWidget(label_widget, i, 0)
            app_layout.addWidget(value_widget, i, 1)
            
        layout.addWidget(app_group)
        
        layout.addStretch()
        tab_widget.addTab(tab, "Система")
        
    def _create_license_tab(self, tab_widget):
        """
        Создание вкладки "Лицензия"
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        license_text = QTextEdit()
        license_text.setReadOnly(True)
        license_text.setPlainText("""
MIT License

Copyright (c) 2024 AI Assistant

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Данное программное обеспечение предоставляется "как есть", без каких-либо
гарантий. Автор не несет ответственности за любые убытки, возникшие в
результате использования данного программного обеспечения.

ВНИМАНИЕ: Торговля криптовалютами связана с высокими рисками. Используйте
данное программное обеспечение на свой страх и риск. Всегда тестируйте
стратегии на демо-счете перед использованием реальных средств.
        """)
        
        layout.addWidget(license_text)
        tab_widget.addTab(tab, "Лицензия")
        
    def _get_pyside_version(self):
        """
        Получение версии PySide6
        """
        try:
            import PySide6
            return PySide6.__version__
        except (ImportError, AttributeError):
            return "Неизвестно"