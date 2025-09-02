#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Система логирования для Bybit Trading Bot

Обеспечивает централизованное логирование всех операций приложения
с поддержкой ротации файлов и различных уровней логирования.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

def setup_logging(log_level: str = "INFO", 
                 log_dir: Optional[str] = None,
                 max_file_size_mb: int = 10,
                 backup_count: int = 5,
                 enable_console: bool = True,
                 enable_file: bool = True) -> logging.Logger:
    """
    Настройка системы логирования
    
    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Директория для файлов логов
        max_file_size_mb: Максимальный размер файла лога в МБ
        backup_count: Количество резервных файлов логов
        enable_console: Включить вывод в консоль
        enable_file: Включить запись в файл
    
    Returns:
        Настроенный logger
    """
    
    # Определяем директорию для логов
    if log_dir:
        log_directory = Path(log_dir)
    else:
        log_directory = Path.home() / ".bybit_trading_bot" / "logs"
    
    log_directory.mkdir(parents=True, exist_ok=True)
    
    # Настройка уровня логирования
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Создаем корневой logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Очищаем существующие обработчики
    root_logger.handlers.clear()
    
    # Формат логирования
    detailed_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(funcName)-15s:%(lineno)-4d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # Консольный обработчик
    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Файловый обработчик с ротацией
    if enable_file:
        log_file = log_directory / f"trading_bot_{datetime.now().strftime('%Y%m%d')}.log"
        
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,  # Конвертируем МБ в байты
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
    
    # Отдельный файл для ошибок
    if enable_file:
        error_log_file = log_directory / f"errors_{datetime.now().strftime('%Y%m%d')}.log"
        
        error_handler = logging.handlers.RotatingFileHandler(
            filename=error_log_file,
            maxBytes=max_file_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(error_handler)
    
    # Настройка логирования для внешних библиотек
    # Уменьшаем уровень логирования для шумных библиотек
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('websockets').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)
    
    # Создаем специализированные логгеры
    setup_specialized_loggers(log_directory, detailed_formatter, max_file_size_mb, backup_count)
    
    logger = logging.getLogger(__name__)
    logger.info(f"Система логирования инициализирована. Уровень: {log_level}")
    logger.info(f"Директория логов: {log_directory}")
    
    return root_logger

def setup_specialized_loggers(log_directory: Path, 
                            formatter: logging.Formatter,
                            max_file_size_mb: int,
                            backup_count: int):
    """
    Настройка специализированных логгеров для разных компонентов
    """
    
    # Логгер для торговых операций
    trading_logger = logging.getLogger('trading')
    trading_handler = logging.handlers.RotatingFileHandler(
        filename=log_directory / f"trading_{datetime.now().strftime('%Y%m%d')}.log",
        maxBytes=max_file_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    trading_handler.setFormatter(formatter)
    trading_logger.addHandler(trading_handler)
    
    # Логгер для стратегий
    strategy_logger = logging.getLogger('strategy')
    strategy_handler = logging.handlers.RotatingFileHandler(
        filename=log_directory / f"strategies_{datetime.now().strftime('%Y%m%d')}.log",
        maxBytes=max_file_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    strategy_handler.setFormatter(formatter)
    strategy_logger.addHandler(strategy_handler)
    
    # Логгер для API операций
    api_logger = logging.getLogger('api')
    api_handler = logging.handlers.RotatingFileHandler(
        filename=log_directory / f"api_{datetime.now().strftime('%Y%m%d')}.log",
        maxBytes=max_file_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    api_handler.setFormatter(formatter)
    api_logger.addHandler(api_handler)
    
    # Логгер для риск-менеджмента
    risk_logger = logging.getLogger('risk')
    risk_handler = logging.handlers.RotatingFileHandler(
        filename=log_directory / f"risk_{datetime.now().strftime('%Y%m%d')}.log",
        maxBytes=max_file_size_mb * 1024 * 1024,
        backupCount=backup_count,
        encoding='utf-8'
    )
    risk_handler.setFormatter(formatter)
    risk_logger.addHandler(risk_handler)

class DatabaseLogHandler(logging.Handler):
    """
    Кастомный обработчик для записи логов в базу данных
    """
    
    def __init__(self, db_manager):
        super().__init__()
        self.db_manager = db_manager
    
    def emit(self, record):
        """
        Запись лога в базу данных
        """
        try:
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created),
                'level': record.levelname,
                'logger_name': record.name,
                'module': record.module,
                'function': record.funcName,
                'line_number': record.lineno,
                'message': record.getMessage(),
                'exception': self.format(record) if record.exc_info else None
            }
            
            # Асинхронная запись в БД
            self.db_manager.log_entry(log_entry)
            
        except Exception:
            # Избегаем рекурсивного логирования ошибок
            pass

def get_logger(name: str) -> logging.Logger:
    """
    Получение именованного логгера
    
    Args:
        name: Имя логгера
    
    Returns:
        Настроенный logger
    """
    return logging.getLogger(name)

def log_function_call(func):
    """
    Декоратор для логирования вызовов функций
    """
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        logger.debug(f"Вызов функции {func.__name__} с аргументами: args={args}, kwargs={kwargs}")
        
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Функция {func.__name__} завершена успешно")
            return result
        except Exception as e:
            logger.error(f"Ошибка в функции {func.__name__}: {e}")
            raise
    
    return wrapper

def log_performance(func):
    """
    Декоратор для логирования производительности функций
    """
    import time
    
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"Функция {func.__name__} выполнена за {execution_time:.4f} секунд")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Функция {func.__name__} завершилась с ошибкой за {execution_time:.4f} секунд: {e}")
            raise
    
    return wrapper