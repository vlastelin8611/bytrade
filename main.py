#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit Trading Bot - Главный файл приложения
Автор: AI Assistant
Лицензия: MIT
Версия: 1.0.0

Описание:
Главный файл для запуска торгового бота Bybit с графическим интерфейсом.
Поддерживает работу с testnet и mainnet, включает модульную архитектуру
для торговых стратегий, управления рисками и уведомлений.
"""

import sys
import os
import logging
from pathlib import Path

# Добавляем корневую папку проекта в путь
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.gui.main_window import MainWindow
from src.core.config_manager import ConfigManager
from src.core.logger import setup_logging
from src.database.db_manager import DatabaseManager

def main():
    """
    Главная функция запуска приложения
    """
    try:
        # Инициализация конфигурации
        config = ConfigManager()
        
        # Определяем окружение из конфигурации
        environment = "mainnet" if not config.is_testnet() else "testnet"
        
        # Инициализация базы данных с учетом окружения
        db_manager = DatabaseManager(environment=environment)
        db_manager.initialize_database()
        
        # Настройка логирования с интеграцией БД
        setup_logging()
        logger = logging.getLogger(__name__)
        
        # Добавляем обработчик для записи логов в БД
        from src.core.logger import DatabaseLogHandler
        db_handler = DatabaseLogHandler(db_manager)
        db_handler.setLevel(logging.INFO)
        
        # Добавляем обработчик ко всем логгерам
        root_logger = logging.getLogger()
        root_logger.addHandler(db_handler)
        
        logger.info(f"Запуск Bybit Trading Bot v1.0.0 ({environment}) с полным логированием в БД")
        
        # Создание и запуск GUI приложения
        from PySide6.QtWidgets import QApplication
        
        app = QApplication(sys.argv)
        app.setApplicationName("Bybit Trading Bot")
        app.setApplicationVersion("1.0.0")
        app.setOrganizationName("Trading Bot Solutions")
        
        # Создание главного окна
        main_window = MainWindow(config, db_manager)
        main_window.show()
        
        logger.info("GUI приложение успешно запущено")
        
        # Запуск основного цикла приложения
        sys.exit(app.exec())
        
    except Exception as e:
        logging.error(f"Критическая ошибка при запуске приложения: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()