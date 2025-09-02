#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер иконок для Bybit Trading Bot

Управляет иконками интерфейса, создает SVG иконки программно
"""

import logging
from typing import Dict, Optional
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtCore import QSize, Qt
from PySide6.QtSvg import QSvgRenderer

class IconManager:
    """
    Менеджер иконок приложения
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._icon_cache: Dict[str, QIcon] = {}
        
        # SVG иконки в виде строк
        self.svg_icons = {
            "app": """
            <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="32" height="32" rx="8" fill="#0078d4"/>
                <path d="M8 12h16v2H8v-2zm0 4h16v2H8v-2zm0 4h12v2H8v-2z" fill="white"/>
                <circle cx="20" cy="20" r="3" fill="#ffd700"/>
            </svg>
            """,
            
            "account": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="8" r="4" stroke="#0078d4" stroke-width="2"/>
                <path d="M6 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "markets": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M3 3v18h18" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
                <path d="M7 12l3-3 4 4 5-5" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <circle cx="7" cy="12" r="1" fill="#0078d4"/>
                <circle cx="10" cy="9" r="1" fill="#0078d4"/>
                <circle cx="14" cy="13" r="1" fill="#0078d4"/>
                <circle cx="19" cy="8" r="1" fill="#0078d4"/>
            </svg>
            """,
            
            "platform": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="3" width="18" height="18" rx="2" stroke="#0078d4" stroke-width="2"/>
                <path d="M9 9h6v6H9V9z" fill="#0078d4" opacity="0.3"/>
                <path d="M7 7h2v2H7V7zm8 0h2v2h-2V7zm0 8h2v2h-2v-2zm-8 0h2v2H7v-2z" fill="#0078d4"/>
            </svg>
            """,
            
            "strategies": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2L2 7l10 5 10-5-10-5z" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M2 17l10 5 10-5" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M2 12l10 5 10-5" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            """,
            
            "telegram": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 5L2 12.5l7 1L15 8l-6.5 8.5L11 19l8-14z" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            """,
            
            "portfolio": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="4" width="18" height="16" rx="2" stroke="#0078d4" stroke-width="2"/>
                <path d="M7 8h10M7 12h6M7 16h8" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "settings": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="3" stroke="#0078d4" stroke-width="2"/>
                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" stroke="#0078d4" stroke-width="2"/>
            </svg>
            """,
            
            "export": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <polyline points="7,10 12,15 17,10" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="12" y1="15" x2="12" y2="3" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "exit": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <polyline points="16,17 21,12 16,7" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="21" y1="12" x2="9" y2="12" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "stop": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="6" y="6" width="12" height="12" rx="2" fill="#d13438"/>
            </svg>
            """,
            
            "emergency": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="#d13438" stroke-width="2" fill="#d13438" opacity="0.1"/>
                <path d="M12 8v4" stroke="#d13438" stroke-width="2" stroke-linecap="round"/>
                <path d="M12 16h.01" stroke="#d13438" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "about": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="#0078d4" stroke-width="2"/>
                <path d="M12 16v-4" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
                <path d="M12 8h.01" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "docs": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <polyline points="14,2 14,8 20,8" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="16" y1="13" x2="8" y2="13" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
                <line x1="16" y1="17" x2="8" y2="17" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
                <polyline points="10,9 9,9 8,9" stroke="#0078d4" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "play": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <polygon points="5,3 19,12 5,21" fill="#107c10"/>
            </svg>
            """,
            
            "pause": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="6" y="4" width="4" height="16" fill="#ff8c00"/>
                <rect x="14" y="4" width="4" height="16" fill="#ff8c00"/>
            </svg>
            """,
            
            "refresh": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <polyline points="23,4 23,10 17,10" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <polyline points="1,20 1,14 7,14" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            """,
            
            "add": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="#107c10" stroke-width="2"/>
                <line x1="12" y1="8" x2="12" y2="16" stroke="#107c10" stroke-width="2" stroke-linecap="round"/>
                <line x1="8" y1="12" x2="16" y2="12" stroke="#107c10" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "remove": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="#d13438" stroke-width="2"/>
                <line x1="8" y1="12" x2="16" y2="12" stroke="#d13438" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "edit": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" stroke="#0078d4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            """,
            
            "save": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" stroke="#107c10" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <polyline points="17,21 17,13 7,13 7,21" stroke="#107c10" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <polyline points="7,3 7,8 15,8" stroke="#107c10" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            """,
            
            "delete": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <polyline points="3,6 5,6 21,6" stroke="#d13438" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" stroke="#d13438" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="10" y1="11" x2="10" y2="17" stroke="#d13438" stroke-width="2" stroke-linecap="round"/>
                <line x1="14" y1="11" x2="14" y2="17" stroke="#d13438" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "warning": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" stroke="#ff8c00" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <line x1="12" y1="9" x2="12" y2="13" stroke="#ff8c00" stroke-width="2" stroke-linecap="round"/>
                <line x1="12" y1="17" x2="12.01" y2="17" stroke="#ff8c00" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """,
            
            "success": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="#107c10" stroke-width="2"/>
                <polyline points="9,12 12,15 16,10" stroke="#107c10" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            """,
            
            "error": """
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="12" cy="12" r="10" stroke="#d13438" stroke-width="2"/>
                <line x1="15" y1="9" x2="9" y2="15" stroke="#d13438" stroke-width="2" stroke-linecap="round"/>
                <line x1="9" y1="9" x2="15" y2="15" stroke="#d13438" stroke-width="2" stroke-linecap="round"/>
            </svg>
            """
        }
    
    def get_icon(self, name: str, size: QSize = QSize(24, 24)) -> QIcon:
        """
        Получение иконки по имени
        """
        cache_key = f"{name}_{size.width()}x{size.height()}"
        
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        if name in self.svg_icons:
            icon = self._create_icon_from_svg(self.svg_icons[name], size)
            self._icon_cache[cache_key] = icon
            return icon
        else:
            # Возвращаем пустую иконку если не найдена
            self.logger.warning(f"Иконка '{name}' не найдена")
            return QIcon()
    
    def _create_icon_from_svg(self, svg_content: str, size: QSize) -> QIcon:
        """
        Создание иконки из SVG контента
        """
        try:
            # Создаем pixmap из SVG
            renderer = QSvgRenderer(svg_content.encode('utf-8'))
            pixmap = QPixmap(size)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
            
        except Exception as e:
            self.logger.error(f"Ошибка создания иконки из SVG: {e}")
            return QIcon()
    
    def create_colored_icon(self, name: str, color: str, size: QSize = QSize(24, 24)) -> QIcon:
        """
        Создание цветной версии иконки
        """
        if name not in self.svg_icons:
            return QIcon()
        
        # Заменяем цвет в SVG
        svg_content = self.svg_icons[name]
        # Простая замена цвета (можно улучшить)
        colored_svg = svg_content.replace('#0078d4', color)
        colored_svg = colored_svg.replace('#107c10', color)
        colored_svg = colored_svg.replace('#ff8c00', color)
        colored_svg = colored_svg.replace('#d13438', color)
        
        return self._create_icon_from_svg(colored_svg, size)
    
    def get_status_icon(self, status: str, size: QSize = QSize(16, 16)) -> QIcon:
        """
        Получение иконки статуса
        """
        status_icons = {
            "success": "success",
            "warning": "warning",
            "error": "error",
            "info": "about",
            "running": "play",
            "stopped": "stop",
            "paused": "pause"
        }
        
        icon_name = status_icons.get(status, "about")
        return self.get_icon(icon_name, size)
    
    def clear_cache(self):
        """
        Очистка кэша иконок
        """
        self._icon_cache.clear()
        self.logger.debug("Кэш иконок очищен")
    
    def preload_icons(self):
        """
        Предзагрузка основных иконок
        """
        main_icons = [
            "app", "account", "markets", "platform", 
            "strategies", "telegram", "portfolio", "settings"
        ]
        
        for icon_name in main_icons:
            self.get_icon(icon_name)
        
        self.logger.info(f"Предзагружено {len(main_icons)} иконок")