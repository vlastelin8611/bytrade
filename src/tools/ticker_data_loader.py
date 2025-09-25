#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для загрузки данных тикеров из файла
"""

import json
import logging
import datetime
from pathlib import Path
from typing import List


logger = logging.getLogger(__name__)

class TickerDataLoader:
    """Класс для загрузки данных тикеров из файла"""
    
    def __init__(self, data_path=None):
        """
        Инициализация загрузчика данных тикеров
        
        Args:
            data_path (Path, optional): Путь к директории с данными. 
                                       По умолчанию используется директория data в корне проекта.
        """
        if data_path is None:
            # Если путь не указан, используем директорию data в корне проекта
            self.data_path = Path.home() / "AppData" / "Local" / "BybitTradingBot" / "data"
        else:
            self.data_path = Path(data_path)
        
        # Убедимся, что директория существует
        self.data_path.mkdir(parents=True, exist_ok=True)
        
        self.tickers_data = {}
        self.historical_data = {}
        self._raw_tickers = None
        self._raw_historical = None
        self.last_update_timestamp = None

    def _normalize_tickers(self, data) -> dict:
        """Приводит данные тикеров к словарю {symbol: payload}."""

        normalized = {}

        if isinstance(data, dict):
            # Если словарь уже содержит символы в качестве ключей
            for key, value in data.items():
                if isinstance(value, dict):
                    symbol = value.get('symbol') or key
                    if isinstance(symbol, str) and symbol:
                        payload = value.copy()
                        payload.setdefault('symbol', symbol)
                        normalized[symbol] = payload
                elif isinstance(value, list):
                    for entry in value:
                        if isinstance(entry, dict):
                            symbol = entry.get('symbol')
                            if isinstance(symbol, str) and symbol:
                                normalized[symbol] = entry
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    symbol = entry.get('symbol')
                    if isinstance(symbol, str) and symbol:
                        normalized[symbol] = entry

        return normalized

    def _normalize_historical(self, data) -> dict:
        """Приводит исторические данные к словарю {symbol: [klines]}"""

        normalized = {}

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, list):
                    normalized[key] = value
                elif isinstance(value, dict):
                    klines = value.get('klines') or value.get('data')
                    symbol = value.get('symbol') or key
                    if isinstance(symbol, str) and isinstance(klines, list):
                        normalized[symbol] = klines
        elif isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    symbol = entry.get('symbol')
                    klines = entry.get('klines') or entry.get('data')
                    if isinstance(symbol, str) and isinstance(klines, list):
                        normalized[symbol] = klines

        return normalized

    def get_data_file_path(self) -> Path:
        """Возвращает путь к файлу с сохранёнными данными тикеров."""
        return self.data_path / 'tickers_data.json'
    
    def load_tickers_data(self):
        """
        Загрузка данных тикеров из файла
        
        Returns:
            dict: Словарь с данными тикеров и временем последнего обновления
                  или None в случае ошибки
        """
        try:
            data_file = self.get_data_file_path()
            
            if not data_file.exists():
                logger.warning(f"Файл с данными тикеров не найден: {data_file}")
                return None
            
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Проверяем структуру данных
            if not all(key in data for key in ['timestamp', 'tickers', 'historical_data']):
                logger.error("Некорректная структура данных в файле тикеров")
                return None
            
            self._raw_tickers = data['tickers']
            self._raw_historical = data['historical_data']

            self.tickers_data = self._normalize_tickers(self._raw_tickers)
            self.historical_data = self._normalize_historical(self._raw_historical)
            self.last_update_timestamp = data['timestamp']
            
            # Преобразуем timestamp в читаемый формат для логирования
            update_time = datetime.datetime.fromtimestamp(self.last_update_timestamp)
            logger.info(f"Загружены данные тикеров. Последнее обновление: {update_time}")
            
            return {
                'tickers': self.tickers_data,
                'historical_data': self.historical_data,
                'timestamp': self.last_update_timestamp,
                'update_time': update_time
            }
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке данных тикеров: {e}")
            return None
    
    def get_ticker_data(self, symbol=None):
        """
        Получение данных конкретного тикера или всех тикеров
        
        Args:
            symbol (str, optional): Символ тикера. Если None, возвращаются все тикеры.
        
        Returns:
            dict: Данные тикера или словарь всех тикеров
        """
        if not self.tickers_data:
            self.load_tickers_data()

        if symbol:
            if isinstance(self.tickers_data, dict):
                entry = self.tickers_data.get(symbol)
                if entry is not None:
                    return entry

            # Пытаемся найти символ в исходной структуре
            if isinstance(self._raw_tickers, dict):
                raw_entry = self._raw_tickers.get(symbol)
                if isinstance(raw_entry, dict):
                    payload = raw_entry.copy()
                    payload.setdefault('symbol', symbol)
                    return payload
            elif isinstance(self._raw_tickers, list):
                for entry in self._raw_tickers:
                    if isinstance(entry, dict) and entry.get('symbol') == symbol:
                        return entry
            return None

        return self.tickers_data if isinstance(self.tickers_data, dict) else self._raw_tickers
    
    def get_historical_data(self, symbol=None):
        """
        Получение исторических данных конкретного тикера или всех тикеров
        
        Args:
            symbol (str, optional): Символ тикера. Если None, возвращаются данные всех тикеров.
        
        Returns:
            dict: Исторические данные тикера или словарь исторических данных всех тикеров
        """
        if not self.historical_data:
            self.load_tickers_data()

        if symbol:
            if isinstance(self.historical_data, dict):
                history = self.historical_data.get(symbol)
                if history is not None:
                    return history

            if isinstance(self._raw_historical, dict):
                raw_history = self._raw_historical.get(symbol)
                if isinstance(raw_history, list):
                    return raw_history
                if isinstance(raw_history, dict):
                    klines = raw_history.get('klines') or raw_history.get('data')
                    if isinstance(klines, list):
                        return klines
            elif isinstance(self._raw_historical, list):
                for entry in self._raw_historical:
                    if isinstance(entry, dict) and entry.get('symbol') == symbol:
                        klines = entry.get('klines') or entry.get('data') or entry.get('historical')
                        if isinstance(klines, list):
                            return klines
            return None

        return self.historical_data if isinstance(self.historical_data, dict) else self._raw_historical

    def get_all_symbols(self) -> List[str]:
        """Возвращает объединённый список символов из тикеров и истории."""

        symbols = set()

        if isinstance(self.tickers_data, dict):
            symbols.update(symbol for symbol in self.tickers_data.keys() if isinstance(symbol, str) and symbol)

        if isinstance(self.historical_data, dict):
            symbols.update(symbol for symbol in self.historical_data.keys() if isinstance(symbol, str) and symbol)

        # Резервный путь: если нормализованные структуры пустые, пытаемся извлечь символы напрямую
        if not symbols:
            if isinstance(self._raw_tickers, list):
                for entry in self._raw_tickers:
                    if isinstance(entry, dict):
                        symbol = entry.get('symbol')
                        if isinstance(symbol, str) and symbol:
                            symbols.add(symbol)
            elif isinstance(self._raw_tickers, dict):
                for key in self._raw_tickers.keys():
                    if isinstance(key, str) and key:
                        symbols.add(key)

        return sorted(symbols)
    
    def is_data_fresh(self, max_age_minutes=5):
        """
        Проверка свежести данных
        
        Args:
            max_age_minutes (int): Максимальный возраст данных в минутах
            
        Returns:
            bool: True, если данные свежие, иначе False
        """
        if not self.last_update_timestamp:
            return False
        
        current_time = datetime.datetime.now().timestamp()
        data_age_minutes = (current_time - self.last_update_timestamp) / 60
        
        return data_age_minutes <= max_age_minutes