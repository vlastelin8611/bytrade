#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер стилей для Bybit Trading Bot

Обеспечивает современное и красивое оформление интерфейса
с поддержкой темной и светлой тем
"""

import logging
from typing import Dict, Any
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor, QPalette

class StyleManager(QObject):
    """
    Менеджер стилей приложения
    """
    
    style_changed = Signal(str)  # Сигнал изменения стиля
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.current_theme = "dark"  # По умолчанию темная тема
        
        # Цветовые схемы
        self.themes = {
            "dark": {
                "primary": "#2b2b2b",
                "secondary": "#3c3c3c",
                "accent": "#0078d4",
                "success": "#107c10",
                "warning": "#ff8c00",
                "error": "#d13438",
                "text_primary": "#ffffff",
                "text_secondary": "#cccccc",
                "text_disabled": "#666666",
                "border": "#555555",
                "hover": "#404040",
                "selected": "#0078d4",
                "background": "#1e1e1e",
                "surface": "#2d2d2d"
            },
            "light": {
                "primary": "#ffffff",
                "secondary": "#f5f5f5",
                "accent": "#0078d4",
                "success": "#107c10",
                "warning": "#ff8c00",
                "error": "#d13438",
                "text_primary": "#000000",
                "text_secondary": "#333333",
                "text_disabled": "#999999",
                "border": "#cccccc",
                "hover": "#e5e5e5",
                "selected": "#0078d4",
                "background": "#ffffff",
                "surface": "#f9f9f9"
            }
        }
    
    def set_theme(self, theme_name: str):
        """
        Установка темы
        """
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.logger.info(f"Установлена тема: {theme_name}")
            self.style_changed.emit(theme_name)
        else:
            self.logger.warning(f"Неизвестная тема: {theme_name}")
    
    def get_color(self, color_name: str) -> str:
        """
        Получение цвета из текущей темы
        """
        return self.themes[self.current_theme].get(color_name, "#000000")
    
    def get_main_stylesheet(self) -> str:
        """
        Получение основного стиля приложения
        """
        colors = self.themes[self.current_theme]
        
        return f"""
        /* Основные стили приложения */
        QMainWindow {{
            background-color: {colors['background']};
            color: {colors['text_primary']};
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 9pt;
        }}
        
        /* Вкладки */
        QTabWidget::pane {{
            border: 1px solid {colors['border']};
            background-color: {colors['primary']};
            border-radius: 4px;
        }}
        
        QTabWidget::tab-bar {{
            alignment: left;
        }}
        
        QTabBar::tab {{
            background-color: {colors['secondary']};
            color: {colors['text_secondary']};
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            border: 1px solid {colors['border']};
            border-bottom: none;
            min-width: 100px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {colors['primary']};
            color: {colors['text_primary']};
            border-color: {colors['accent']};
            font-weight: bold;
        }}
        
        QTabBar::tab:hover:!selected {{
            background-color: {colors['hover']};
            color: {colors['text_primary']};
        }}
        
        /* Кнопки */
        QPushButton {{
            background-color: {colors['accent']};
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
            min-width: 80px;
        }}
        
        QPushButton:hover {{
            background-color: #106ebe;
        }}
        
        QPushButton:pressed {{
            background-color: #005a9e;
        }}
        
        QPushButton:disabled {{
            background-color: {colors['text_disabled']};
            color: {colors['text_secondary']};
        }}
        
        /* Кнопки успеха */
        QPushButton.success {{
            background-color: {colors['success']};
        }}
        
        QPushButton.success:hover {{
            background-color: #0e6e0e;
        }}
        
        /* Кнопки предупреждения */
        QPushButton.warning {{
            background-color: {colors['warning']};
        }}
        
        QPushButton.warning:hover {{
            background-color: #e67c00;
        }}
        
        /* Кнопки ошибки */
        QPushButton.error {{
            background-color: {colors['error']};
        }}
        
        QPushButton.error:hover {{
            background-color: #b92b2f;
        }}
        
        /* Поля ввода */
        QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
            background-color: {colors['surface']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
            padding: 6px;
            font-size: 9pt;
        }}
        
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, 
        QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
            border-color: {colors['accent']};
            border-width: 2px;
        }}
        
        /* Комбобоксы */
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        
        QComboBox::down-arrow {{
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDFMNiA2TDExIDEiIHN0cm9rZT0iIzk5OTk5OSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {colors['surface']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
            selection-background-color: {colors['selected']};
        }}
        
        /* Таблицы */
        QTableWidget, QTableView {{
            background-color: {colors['primary']};
            color: {colors['text_primary']};
            gridline-color: {colors['border']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
        }}
        
        QTableWidget::item, QTableView::item {{
            padding: 8px;
            border-bottom: 1px solid {colors['border']};
        }}
        
        QTableWidget::item:selected, QTableView::item:selected {{
            background-color: {colors['selected']};
            color: white;
        }}
        
        QHeaderView::section {{
            background-color: {colors['secondary']};
            color: {colors['text_primary']};
            padding: 8px;
            border: 1px solid {colors['border']};
            font-weight: bold;
        }}
        
        /* Списки */
        QListWidget {{
            background-color: {colors['primary']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
        }}
        
        QListWidget::item {{
            padding: 8px;
            border-bottom: 1px solid {colors['border']};
        }}
        
        QListWidget::item:selected {{
            background-color: {colors['selected']};
            color: white;
        }}
        
        QListWidget::item:hover {{
            background-color: {colors['hover']};
        }}
        
        /* Группы */
        QGroupBox {{
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
            margin-top: 10px;
            font-weight: bold;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 8px 0 8px;
            background-color: {colors['primary']};
        }}
        
        /* Чекбоксы и радиокнопки */
        QCheckBox, QRadioButton {{
            color: {colors['text_primary']};
            spacing: 8px;
        }}
        
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 16px;
            height: 16px;
        }}
        
        QCheckBox::indicator:unchecked {{
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 2px;
        }}
        
        QCheckBox::indicator:checked {{
            background-color: {colors['accent']};
            border: 1px solid {colors['accent']};
            border-radius: 2px;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOSIgdmlld0JveD0iMCAwIDEyIDkiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDQuNUw0LjUgOEwxMSAxIiBzdHJva2U9IndoaXRlIiBzdHJva2Utd2lkdGg9IjIiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPgo8L3N2Zz4=);
        }}
        
        /* Прогресс-бары */
        QProgressBar {{
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
            text-align: center;
            color: {colors['text_primary']};
        }}
        
        QProgressBar::chunk {{
            background-color: {colors['accent']};
            border-radius: 3px;
        }}
        
        /* Слайдеры */
        QSlider::groove:horizontal {{
            background-color: {colors['surface']};
            height: 6px;
            border-radius: 3px;
        }}
        
        QSlider::handle:horizontal {{
            background-color: {colors['accent']};
            width: 16px;
            height: 16px;
            border-radius: 8px;
            margin: -5px 0;
        }}
        
        QSlider::sub-page:horizontal {{
            background-color: {colors['accent']};
            border-radius: 3px;
        }}
        
        /* Скроллбары */
        QScrollBar:vertical {{
            background-color: {colors['secondary']};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {colors['border']};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {colors['text_disabled']};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        
        QScrollBar:horizontal {{
            background-color: {colors['secondary']};
            height: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:horizontal {{
            background-color: {colors['border']};
            border-radius: 6px;
            min-width: 20px;
        }}
        
        QScrollBar::handle:horizontal:hover {{
            background-color: {colors['text_disabled']};
        }}
        
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}
        
        /* Меню */
        QMenuBar {{
            background-color: {colors['secondary']};
            color: {colors['text_primary']};
            border-bottom: 1px solid {colors['border']};
        }}
        
        QMenuBar::item {{
            padding: 6px 12px;
            background-color: transparent;
        }}
        
        QMenuBar::item:selected {{
            background-color: {colors['hover']};
        }}
        
        QMenu {{
            background-color: {colors['surface']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
        }}
        
        QMenu::item {{
            padding: 8px 16px;
        }}
        
        QMenu::item:selected {{
            background-color: {colors['selected']};
            color: white;
        }}
        
        QMenu::separator {{
            height: 1px;
            background-color: {colors['border']};
            margin: 4px 0;
        }}
        
        /* Статус-бар */
        QStatusBar {{
            background-color: {colors['secondary']};
            color: {colors['text_primary']};
            border-top: 1px solid {colors['border']};
        }}
        
        /* Диалоги */
        QDialog {{
            background-color: {colors['primary']};
            color: {colors['text_primary']};
        }}
        
        /* Сплиттеры */
        QSplitter::handle {{
            background-color: {colors['border']};
        }}
        
        QSplitter::handle:horizontal {{
            width: 2px;
        }}
        
        QSplitter::handle:vertical {{
            height: 2px;
        }}
        
        /* Тултипы */
        QToolTip {{
            background-color: {colors['surface']};
            color: {colors['text_primary']};
            border: 1px solid {colors['border']};
            border-radius: 4px;
            padding: 4px;
        }}
        """
    
    def get_button_style(self, button_type: str = "primary") -> str:
        """
        Получение стиля для кнопок определенного типа
        """
        colors = self.themes[self.current_theme]
        
        styles = {
            "primary": f"""
                QPushButton {{
                    background-color: {colors['accent']};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #106ebe;
                }}
            """,
            "success": f"""
                QPushButton {{
                    background-color: {colors['success']};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #0e6e0e;
                }}
            """,
            "warning": f"""
                QPushButton {{
                    background-color: {colors['warning']};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #e67c00;
                }}
            """,
            "error": f"""
                QPushButton {{
                    background-color: {colors['error']};
                    color: white;
                    border: none;
                    padding: 8px 16px;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: #b92b2f;
                }}
            """
        }
        
        return styles.get(button_type, styles["primary"])
    
    def get_card_style(self) -> str:
        """
        Получение стиля для карточек
        """
        colors = self.themes[self.current_theme]
        
        return f"""
        QFrame {{
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
            padding: 16px;
        }}
        """
    
    def get_status_style(self, status: str) -> str:
        """
        Получение стиля для статусов
        """
        colors = self.themes[self.current_theme]
        
        status_colors = {
            "success": colors['success'],
            "warning": colors['warning'],
            "error": colors['error'],
            "info": colors['accent'],
            "default": colors['text_secondary']
        }
        
        color = status_colors.get(status, status_colors['default'])
        
        return f"""
        QLabel {{
            color: {color};
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 4px;
            background-color: {color}20;
        }}
        """