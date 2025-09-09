#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для управления базой данных

Основные функции:
- Создание и инициализация базы данных
- Сохранение и загрузка данных стратегий
- Логирование торговых операций
- Хранение исторических данных
"""

import logging
import os
import sqlite3
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
import json

class DatabaseManager:
    """
    Класс для управления базой данных SQLite
    """
    
    def __init__(self, db_path: str, testnet: bool = True):
        """
        Инициализация менеджера базы данных
        
        Args:
            db_path: Путь к файлу базы данных
            testnet: Флаг использования тестовой сети
        """
        self.logger = logging.getLogger("DatabaseManager")
        
        # Добавление суффикса для testnet, чтобы разделить данные
        if testnet:
            base, ext = os.path.splitext(db_path)
            db_path = f"{base}_testnet{ext}"
        
        self.db_path = db_path
        self.testnet = testnet
        self.conn = None
        
        # Инициализация базы данных
        self._initialize_db()
        
        self.logger.info(f"DatabaseManager инициализирован (testnet={testnet})")
    
    def _initialize_db(self) -> None:
        """
        Инициализация базы данных и создание необходимых таблиц
        """
        try:
            # Создание директории для базы данных, если она не существует
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir)
            
            # Подключение к базе данных
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            
            # Создание таблиц
            self._create_tables()
            
            self.logger.info(f"База данных инициализирована: {self.db_path}")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def _create_tables(self) -> None:
        """
        Создание необходимых таблиц в базе данных
        """
        cursor = self.conn.cursor()
        
        # Таблица для логов
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            source TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT
        )
        """)
        
        # Таблица для торговых операций
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            strategy_name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            order_type TEXT NOT NULL,
            price REAL,
            quantity REAL NOT NULL,
            order_id TEXT,
            status TEXT NOT NULL,
            pnl REAL,
            details TEXT
        )
        """)
        
        # Таблица для стратегий
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            type TEXT NOT NULL,
            config TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        
        # Таблица для сессий стратегий
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT,
            status TEXT NOT NULL,
            total_trades INTEGER DEFAULT 0,
            winning_trades INTEGER DEFAULT 0,
            losing_trades INTEGER DEFAULT 0,
            total_pnl REAL DEFAULT 0.0,
            FOREIGN KEY (strategy_id) REFERENCES strategies (id)
        )
        """)
        
        # Таблица для событий стратегий
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategy_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            event_type TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT,
            FOREIGN KEY (strategy_id) REFERENCES strategies (id)
        )
        """)
        
        # Таблица для исторических данных
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS historical_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            open REAL NOT NULL,
            high REAL NOT NULL,
            low REAL NOT NULL,
            close REAL NOT NULL,
            volume REAL NOT NULL,
            UNIQUE(symbol, timeframe, timestamp)
        )
        """)
        
        # Таблица для настроек
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL UNIQUE,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        
        # Таблица для баланса
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_balance REAL NOT NULL,
            available_balance REAL NOT NULL,
            details TEXT
        )
        """)
        
        self.conn.commit()
    
    def log(self, level: str, source: str, message: str, details: Dict[str, Any] = None) -> int:
        """
        Добавление записи в лог
        
        Args:
            level: Уровень лога (info, warning, error, debug)
            source: Источник лога
            message: Сообщение
            details: Дополнительные детали (опционально)
            
        Returns:
            int: ID добавленной записи
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            details_json = json.dumps(details) if details else None
            
            cursor.execute(
                "INSERT INTO logs (timestamp, level, source, message, details) VALUES (?, ?, ?, ?, ?)",
                (timestamp, level, source, message, details_json)
            )
            self.conn.commit()
            
            return cursor.lastrowid
            
        except Exception as e:
            self.logger.error(f"Ошибка добавления записи в лог: {e}")
            return -1
    
    def add_trade(self, strategy_name: str, symbol: str, side: str, order_type: str,
                 price: float, quantity: float, order_id: str, status: str,
                 pnl: float = None, details: Dict[str, Any] = None) -> int:
        """
        Добавление торговой операции
        
        Args:
            strategy_name: Имя стратегии
            symbol: Символ торговой пары
            side: Сторона (buy, sell)
            order_type: Тип ордера (limit, market)
            price: Цена
            quantity: Количество
            order_id: ID ордера
            status: Статус операции
            pnl: Прибыль/убыток (опционально)
            details: Дополнительные детали (опционально)
            
        Returns:
            int: ID добавленной записи
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            details_json = json.dumps(details) if details else None
            
            cursor.execute(
                """INSERT INTO trades 
                (timestamp, strategy_name, symbol, side, order_type, price, quantity, order_id, status, pnl, details) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (timestamp, strategy_name, symbol, side, order_type, price, quantity, order_id, status, pnl, details_json)
            )
            self.conn.commit()
            
            return cursor.lastrowid
            
        except Exception as e:
            self.logger.error(f"Ошибка добавления торговой операции: {e}")
            return -1
    
    def update_trade(self, order_id: str, status: str, pnl: float = None, details: Dict[str, Any] = None) -> bool:
        """
        Обновление торговой операции
        
        Args:
            order_id: ID ордера
            status: Новый статус операции
            pnl: Прибыль/убыток (опционально)
            details: Дополнительные детали (опционально)
            
        Returns:
            bool: Успешность обновления
        """
        try:
            cursor = self.conn.cursor()
            
            # Получение текущих деталей
            cursor.execute("SELECT details FROM trades WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            # Обновление деталей
            current_details = json.loads(row[0]) if row[0] else {}
            if details:
                current_details.update(details)
            details_json = json.dumps(current_details)
            
            # Обновление записи
            if pnl is not None:
                cursor.execute(
                    "UPDATE trades SET status = ?, pnl = ?, details = ? WHERE order_id = ?",
                    (status, pnl, details_json, order_id)
                )
            else:
                cursor.execute(
                    "UPDATE trades SET status = ?, details = ? WHERE order_id = ?",
                    (status, details_json, order_id)
                )
            
            self.conn.commit()
            return cursor.rowcount > 0
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления торговой операции: {e}")
            return False
    
    def get_trades(self, strategy_name: str = None, symbol: str = None, 
                  start_time: str = None, end_time: str = None, 
                  limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получение торговых операций
        
        Args:
            strategy_name: Имя стратегии (опционально)
            symbol: Символ торговой пары (опционально)
            start_time: Начальное время в формате ISO (опционально)
            end_time: Конечное время в формате ISO (опционально)
            limit: Максимальное количество записей
            
        Returns:
            List[Dict[str, Any]]: Список торговых операций
        """
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM trades WHERE 1=1"
            params = []
            
            if strategy_name:
                query += " AND strategy_name = ?"
                params.append(strategy_name)
            
            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                trade = dict(row)
                if trade['details']:
                    trade['details'] = json.loads(trade['details'])
                result.append(trade)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка получения торговых операций: {e}")
            return []
    
    def add_strategy(self, name: str, strategy_type: str, config: Dict[str, Any]) -> int:
        """
        Добавление стратегии в базу данных
        
        Args:
            name: Имя стратегии
            strategy_type: Тип стратегии
            config: Конфигурация стратегии
            
        Returns:
            int: ID добавленной стратегии
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            config_json = json.dumps(config)
            
            cursor.execute(
                """INSERT INTO strategies 
                (name, type, config, status, created_at, updated_at) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (name, strategy_type, config_json, "stopped", timestamp, timestamp)
            )
            self.conn.commit()
            
            return cursor.lastrowid
            
        except sqlite3.IntegrityError:
            # Стратегия с таким именем уже существует, обновляем конфигурацию
            return self.update_strategy_config(name, config)
            
        except Exception as e:
            self.logger.error(f"Ошибка добавления стратегии: {e}")
            return -1
    
    def update_strategy_config(self, name: str, config: Dict[str, Any]) -> int:
        """
        Обновление конфигурации стратегии
        
        Args:
            name: Имя стратегии
            config: Новая конфигурация
            
        Returns:
            int: ID стратегии или -1 в случае ошибки
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            config_json = json.dumps(config)
            
            cursor.execute(
                "UPDATE strategies SET config = ?, updated_at = ? WHERE name = ?",
                (config_json, timestamp, name)
            )
            self.conn.commit()
            
            # Получение ID стратегии
            cursor.execute("SELECT id FROM strategies WHERE name = ?", (name,))
            row = cursor.fetchone()
            return row[0] if row else -1
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления конфигурации стратегии: {e}")
            return -1
    
    def update_strategy_status(self, name: str, status: str) -> bool:
        """
        Обновление статуса стратегии
        
        Args:
            name: Имя стратегии
            status: Новый статус
            
        Returns:
            bool: Успешность обновления
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            
            cursor.execute(
                "UPDATE strategies SET status = ?, updated_at = ? WHERE name = ?",
                (status, timestamp, name)
            )
            self.conn.commit()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса стратегии: {e}")
            return False
    
    def get_strategy(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Получение информации о стратегии
        
        Args:
            name: Имя стратегии
            
        Returns:
            Optional[Dict[str, Any]]: Информация о стратегии или None, если стратегия не найдена
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM strategies WHERE name = ?", (name,))
            row = cursor.fetchone()
            
            if not row:
                return None
            
            strategy = dict(row)
            strategy['config'] = json.loads(strategy['config'])
            
            return strategy
            
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о стратегии: {e}")
            return None
    
    def get_all_strategies(self) -> List[Dict[str, Any]]:
        """
        Получение информации о всех стратегиях
        
        Returns:
            List[Dict[str, Any]]: Список стратегий
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM strategies ORDER BY name")
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                strategy = dict(row)
                strategy['config'] = json.loads(strategy['config'])
                result.append(strategy)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о стратегиях: {e}")
            return []
    
    def delete_strategy(self, name: str) -> bool:
        """
        Удаление стратегии
        
        Args:
            name: Имя стратегии
            
        Returns:
            bool: Успешность удаления
        """
        try:
            cursor = self.conn.cursor()
            
            # Получение ID стратегии
            cursor.execute("SELECT id FROM strategies WHERE name = ?", (name,))
            row = cursor.fetchone()
            if not row:
                return False
            
            strategy_id = row[0]
            
            # Удаление связанных записей
            cursor.execute("DELETE FROM strategy_sessions WHERE strategy_id = ?", (strategy_id,))
            cursor.execute("DELETE FROM strategy_events WHERE strategy_id = ?", (strategy_id,))
            
            # Удаление стратегии
            cursor.execute("DELETE FROM strategies WHERE id = ?", (strategy_id,))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка удаления стратегии: {e}")
            return False
    
    def start_strategy_session(self, strategy_name: str, session_id: str) -> int:
        """
        Начало новой сессии стратегии
        
        Args:
            strategy_name: Имя стратегии
            session_id: ID сессии
            
        Returns:
            int: ID сессии в базе данных или -1 в случае ошибки
        """
        try:
            cursor = self.conn.cursor()
            
            # Получение ID стратегии
            cursor.execute("SELECT id FROM strategies WHERE name = ?", (strategy_name,))
            row = cursor.fetchone()
            if not row:
                return -1
            
            strategy_id = row[0]
            timestamp = datetime.utcnow().isoformat()
            
            # Создание новой сессии
            cursor.execute(
                """INSERT INTO strategy_sessions 
                (strategy_id, session_id, start_time, status) 
                VALUES (?, ?, ?, ?)""",
                (strategy_id, session_id, timestamp, "running")
            )
            self.conn.commit()
            
            return cursor.lastrowid
            
        except Exception as e:
            self.logger.error(f"Ошибка начала сессии стратегии: {e}")
            return -1
    
    def end_strategy_session(self, session_id: str, total_trades: int = 0, 
                           winning_trades: int = 0, losing_trades: int = 0, 
                           total_pnl: float = 0.0) -> bool:
        """
        Завершение сессии стратегии
        
        Args:
            session_id: ID сессии
            total_trades: Общее количество сделок
            winning_trades: Количество прибыльных сделок
            losing_trades: Количество убыточных сделок
            total_pnl: Общая прибыль/убыток
            
        Returns:
            bool: Успешность завершения сессии
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            
            cursor.execute(
                """UPDATE strategy_sessions 
                SET end_time = ?, status = ?, total_trades = ?, winning_trades = ?, losing_trades = ?, total_pnl = ? 
                WHERE session_id = ?""",
                (timestamp, "stopped", total_trades, winning_trades, losing_trades, total_pnl, session_id)
            )
            self.conn.commit()
            
            return cursor.rowcount > 0
            
        except Exception as e:
            self.logger.error(f"Ошибка завершения сессии стратегии: {e}")
            return False
    
    def log_strategy_event(self, strategy_name: str, session_id: str, event_type: str, 
                         message: str, details: Dict[str, Any] = None) -> int:
        """
        Логирование события стратегии
        
        Args:
            strategy_name: Имя стратегии
            session_id: ID сессии
            event_type: Тип события
            message: Сообщение
            details: Дополнительные детали (опционально)
            
        Returns:
            int: ID добавленной записи
        """
        try:
            cursor = self.conn.cursor()
            
            # Получение ID стратегии
            cursor.execute("SELECT id FROM strategies WHERE name = ?", (strategy_name,))
            row = cursor.fetchone()
            if not row:
                return -1
            
            strategy_id = row[0]
            timestamp = datetime.utcnow().isoformat()
            details_json = json.dumps(details) if details else None
            
            cursor.execute(
                """INSERT INTO strategy_events 
                (strategy_id, session_id, timestamp, event_type, message, details) 
                VALUES (?, ?, ?, ?, ?, ?)""",
                (strategy_id, session_id, timestamp, event_type, message, details_json)
            )
            self.conn.commit()
            
            return cursor.lastrowid
            
        except Exception as e:
            self.logger.error(f"Ошибка логирования события стратегии: {e}")
            return -1
    
    def get_strategy_events(self, strategy_name: str = None, session_id: str = None, 
                          event_type: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получение событий стратегии
        
        Args:
            strategy_name: Имя стратегии (опционально)
            session_id: ID сессии (опционально)
            event_type: Тип события (опционально)
            limit: Максимальное количество записей
            
        Returns:
            List[Dict[str, Any]]: Список событий
        """
        try:
            cursor = self.conn.cursor()
            query = """SELECT e.*, s.name as strategy_name 
                    FROM strategy_events e 
                    JOIN strategies s ON e.strategy_id = s.id 
                    WHERE 1=1"""
            params = []
            
            if strategy_name:
                query += " AND s.name = ?"
                params.append(strategy_name)
            
            if session_id:
                query += " AND e.session_id = ?"
                params.append(session_id)
            
            if event_type:
                query += " AND e.event_type = ?"
                params.append(event_type)
            
            query += " ORDER BY e.timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                event = dict(row)
                if event['details']:
                    event['details'] = json.loads(event['details'])
                result.append(event)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка получения событий стратегии: {e}")
            return []
    
    def save_historical_data(self, symbol: str, timeframe: str, data: List[Dict[str, Any]]) -> int:
        """
        Сохранение исторических данных
        
        Args:
            symbol: Символ торговой пары
            timeframe: Временной интервал
            data: Список свечей
            
        Returns:
            int: Количество добавленных записей
        """
        try:
            cursor = self.conn.cursor()
            count = 0
            
            for candle in data:
                try:
                    cursor.execute(
                        """INSERT OR REPLACE INTO historical_data 
                        (symbol, timeframe, timestamp, open, high, low, close, volume) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            symbol,
                            timeframe,
                            candle['timestamp'],
                            candle['open'],
                            candle['high'],
                            candle['low'],
                            candle['close'],
                            candle['volume']
                        )
                    )
                    count += 1
                except sqlite3.IntegrityError:
                    # Запись уже существует, пропускаем
                    pass
                    
            self.conn.commit()
            return count
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения исторических данных: {e}")
            return 0
    
    def get_historical_data(self, symbol: str, timeframe: str, 
                         start_time: str = None, end_time: str = None, 
                         limit: int = 1000) -> List[Dict[str, Any]]:
        """
        Получение исторических данных
        
        Args:
            symbol: Символ торговой пары
            timeframe: Временной интервал
            start_time: Начальное время в формате ISO (опционально)
            end_time: Конечное время в формате ISO (опционально)
            limit: Максимальное количество записей
            
        Returns:
            List[Dict[str, Any]]: Список свечей
        """
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM historical_data WHERE symbol = ? AND timeframe = ?"
            params = [symbol, timeframe]
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp ASC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"Ошибка получения исторических данных: {e}")
            return []
    
    def save_setting(self, key: str, value: Any) -> bool:
        """
        Сохранение настройки
        
        Args:
            key: Ключ настройки
            value: Значение настройки
            
        Returns:
            bool: Успешность сохранения
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            
            # Преобразование значения в строку
            if not isinstance(value, str):
                value = json.dumps(value)
            
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, timestamp)
            )
            self.conn.commit()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения настройки: {e}")
            return False
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Получение настройки
        
        Args:
            key: Ключ настройки
            default: Значение по умолчанию
            
        Returns:
            Any: Значение настройки или значение по умолчанию
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            
            if not row:
                return default
            
            value = row[0]
            
            # Попытка преобразования значения из JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
            
        except Exception as e:
            self.logger.error(f"Ошибка получения настройки: {e}")
            return default
    
    def save_balance(self, total_balance: float, available_balance: float, details: Dict[str, Any] = None) -> int:
        """
        Сохранение информации о балансе
        
        Args:
            total_balance: Общий баланс
            available_balance: Доступный баланс
            details: Дополнительные детали (опционально)
            
        Returns:
            int: ID добавленной записи
        """
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.utcnow().isoformat()
            details_json = json.dumps(details) if details else None
            
            cursor.execute(
                "INSERT INTO balance_history (timestamp, total_balance, available_balance, details) VALUES (?, ?, ?, ?)",
                (timestamp, total_balance, available_balance, details_json)
            )
            self.conn.commit()
            
            return cursor.lastrowid
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения информации о балансе: {e}")
            return -1
    
    def get_balance_history(self, start_time: str = None, end_time: str = None, 
                          limit: int = 100) -> List[Dict[str, Any]]:
        """
        Получение истории баланса
        
        Args:
            start_time: Начальное время в формате ISO (опционально)
            end_time: Конечное время в формате ISO (опционально)
            limit: Максимальное количество записей
            
        Returns:
            List[Dict[str, Any]]: История баланса
        """
        try:
            cursor = self.conn.cursor()
            query = "SELECT * FROM balance_history WHERE 1=1"
            params = []
            
            if start_time:
                query += " AND timestamp >= ?"
                params.append(start_time)
            
            if end_time:
                query += " AND timestamp <= ?"
                params.append(end_time)
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            result = []
            for row in rows:
                balance = dict(row)
                if balance['details']:
                    balance['details'] = json.loads(balance['details'])
                result.append(balance)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка получения истории баланса: {e}")
            return []
    
    def close(self) -> None:
        """
        Закрытие соединения с базой данных
        """
        if self.conn:
            self.conn.close()
            self.logger.info("Соединение с базой данных закрыто")