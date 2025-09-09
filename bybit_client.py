#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Клиент для работы с API биржи Bybit

Основные функции:
- Подключение к API Bybit
- Выполнение торговых операций
- Получение рыночных данных
- Управление ордерами и позициями
"""

import logging
import time
import hmac
import hashlib
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import requests
from urllib.parse import urlencode

class BybitClient:
    """
    Клиент для работы с API биржи Bybit
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Инициализация клиента API Bybit
        
        Args:
            api_key: API ключ
            api_secret: API секрет
            testnet: Использовать тестовую сеть (True) или основную (False)
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        
        # Базовые URL для API
        if testnet:
            self.base_url = "https://api-testnet.bybit.com"
        else:
            self.base_url = "https://api.bybit.com"
        
        # Логгер
        self.logger = logging.getLogger("BybitClient")
        
        # Ограничение запросов (rate limiting)
        self.last_request_time = 0
        self.min_request_interval = 0.05  # 50 мс между запросами
        
        # Кэширование данных
        self.cache = {}
        self.cache_ttl = 5  # Время жизни кэша в секундах
        
        self.logger.info(f"BybitClient инициализирован (testnet={testnet})")
    
    def _generate_signature(self, params: Dict[str, Any], timestamp: int) -> str:
        """
        Генерация подписи для API запроса
        
        Args:
            params: Параметры запроса
            timestamp: Временная метка в миллисекундах
            
        Returns:
            str: Подпись запроса
        """
        # Добавление временной метки и API ключа
        params['api_key'] = self.api_key
        params['timestamp'] = timestamp
        
        # Сортировка параметров по ключу
        sorted_params = sorted(params.items())
        query_string = urlencode(sorted_params)
        
        # Создание подписи
        signature = hmac.new(
            bytes(self.api_secret, 'utf-8'),
            bytes(query_string, 'utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _handle_rate_limiting(self) -> None:
        """
        Обработка ограничения запросов (rate limiting)
        """
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _request(self, method: str, endpoint: str, params: Dict[str, Any] = None, 
                signed: bool = True, use_cache: bool = False) -> Dict[str, Any]:
        """
        Выполнение запроса к API
        
        Args:
            method: HTTP метод (GET, POST, DELETE)
            endpoint: Конечная точка API
            params: Параметры запроса
            signed: Требуется ли подпись запроса
            use_cache: Использовать кэширование для GET запросов
            
        Returns:
            Dict[str, Any]: Ответ API в формате JSON
        """
        # Проверка кэша для GET запросов
        cache_key = None
        if method == 'GET' and use_cache:
            cache_key = f"{endpoint}:{json.dumps(params or {})}"
            cached_data = self.cache.get(cache_key)
            if cached_data:
                cache_time, data = cached_data
                if time.time() - cache_time < self.cache_ttl:
                    return data
        
        # Обработка ограничения запросов
        self._handle_rate_limiting()
        
        # Формирование URL
        url = f"{self.base_url}{endpoint}"
        
        # Подготовка заголовков и параметров
        headers = {}
        request_params = params or {}
        
        if signed:
            timestamp = int(time.time() * 1000)
            signature = self._generate_signature(request_params, timestamp)
            request_params['sign'] = signature
            headers['X-BAPI-API-KEY'] = self.api_key
            headers['X-BAPI-SIGN'] = signature
            headers['X-BAPI-SIGN-TYPE'] = '2'
            headers['X-BAPI-TIMESTAMP'] = str(timestamp)
            headers['X-BAPI-RECV-WINDOW'] = '5000'
        
        # Выполнение запроса
        try:
            if method == 'GET':
                response = requests.get(url, params=request_params, headers=headers)
            elif method == 'POST':
                headers['Content-Type'] = 'application/json'
                response = requests.post(url, json=request_params, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, params=request_params, headers=headers)
            else:
                raise ValueError(f"Неподдерживаемый HTTP метод: {method}")
            
            # Проверка статуса ответа
            response.raise_for_status()
            
            # Парсинг JSON ответа
            result = response.json()
            
            # Кэширование результата для GET запросов
            if method == 'GET' and use_cache and cache_key:
                self.cache[cache_key] = (time.time(), result)
            
            return result
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Ошибка API запроса: {e}")
            return {'ret_code': -1, 'ret_msg': str(e), 'result': None}
    
    def test_connectivity(self) -> bool:
        """
        Проверка соединения с API
        
        Returns:
            bool: True, если соединение установлено, иначе False
        """
        try:
            response = self._request('GET', '/v5/market/time', signed=False)
            return response.get('ret_code') == 0
        except Exception as e:
            self.logger.error(f"Ошибка проверки соединения: {e}")
            return False
    
    def get_server_time(self) -> int:
        """
        Получение серверного времени
        
        Returns:
            int: Серверное время в миллисекундах
        """
        response = self._request('GET', '/v5/market/time', signed=False)
        if response.get('ret_code') == 0 and 'result' in response:
            return int(response['result']['timeNano'] // 1000000)
        return int(time.time() * 1000)
    
    def get_wallet_balance(self, accountType: str = "UNIFIED") -> Dict[str, Any]:
        """
        Получение баланса кошелька
        
        Args:
            accountType: Тип аккаунта (UNIFIED, CONTRACT, SPOT)
            
        Returns:
            Dict[str, Any]: Информация о балансе
        """
        params = {'accountType': accountType}
        return self._request('GET', '/v5/account/wallet-balance', params=params)
    
    def get_positions(self, category: str = "linear", symbol: str = None) -> Dict[str, Any]:
        """
        Получение информации о позициях
        
        Args:
            category: Категория (linear, inverse, spot)
            symbol: Символ торговой пары (опционально)
            
        Returns:
            Dict[str, Any]: Информация о позициях
        """
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        return self._request('GET', '/v5/position/list', params=params)
    
    def get_klines(self, category: str, symbol: str, interval: str, 
                  start: int = None, end: int = None, limit: int = 200) -> Dict[str, Any]:
        """
        Получение исторических данных (свечей)
        
        Args:
            category: Категория (spot, linear, inverse)
            symbol: Символ торговой пары
            interval: Интервал (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w, 1M)
            start: Начальное время в миллисекундах
            end: Конечное время в миллисекундах
            limit: Количество записей (макс. 1000)
            
        Returns:
            Dict[str, Any]: Исторические данные
        """
        params = {
            'category': category,
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if start:
            params['start'] = start
        if end:
            params['end'] = end
        
        return self._request('GET', '/v5/market/kline', params=params, use_cache=True)
    
    def get_orderbook(self, category: str, symbol: str, limit: int = 50) -> Dict[str, Any]:
        """
        Получение книги ордеров
        
        Args:
            category: Категория (spot, linear, inverse)
            symbol: Символ торговой пары
            limit: Глубина книги ордеров (1-200)
            
        Returns:
            Dict[str, Any]: Книга ордеров
        """
        params = {
            'category': category,
            'symbol': symbol,
            'limit': limit
        }
        return self._request('GET', '/v5/market/orderbook', params=params, use_cache=True)
    
    def get_tickers(self, category: str, symbol: str = None) -> Dict[str, Any]:
        """
        Получение тикеров
        
        Args:
            category: Категория (spot, linear, inverse)
            symbol: Символ торговой пары (опционально)
            
        Returns:
            Dict[str, Any]: Информация о тикерах
        """
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        return self._request('GET', '/v5/market/tickers', params=params, use_cache=True)
    
    def place_order(self, category: str, symbol: str, side: str, orderType: str, 
                   qty: str, price: str = None, **kwargs) -> Dict[str, Any]:
        """
        Размещение ордера
        
        Args:
            category: Категория (spot, linear, inverse)
            symbol: Символ торговой пары
            side: Сторона (Buy, Sell)
            orderType: Тип ордера (Limit, Market)
            qty: Количество
            price: Цена (для лимитных ордеров)
            **kwargs: Дополнительные параметры
            
        Returns:
            Dict[str, Any]: Результат размещения ордера
        """
        params = {
            'category': category,
            'symbol': symbol,
            'side': side,
            'orderType': orderType,
            'qty': qty
        }
        
        if price and orderType.lower() == 'limit':
            params['price'] = price
        
        # Добавление дополнительных параметров
        params.update(kwargs)
        
        return self._request('POST', '/v5/order/create', params=params)
    
    def cancel_order(self, category: str, symbol: str, orderId: str = None, 
                    orderLinkId: str = None) -> Dict[str, Any]:
        """
        Отмена ордера
        
        Args:
            category: Категория (spot, linear, inverse)
            symbol: Символ торговой пары
            orderId: ID ордера (опционально)
            orderLinkId: Пользовательский ID ордера (опционально)
            
        Returns:
            Dict[str, Any]: Результат отмены ордера
        """
        params = {
            'category': category,
            'symbol': symbol
        }
        
        if orderId:
            params['orderId'] = orderId
        elif orderLinkId:
            params['orderLinkId'] = orderLinkId
        else:
            raise ValueError("Необходимо указать orderId или orderLinkId")
        
        return self._request('POST', '/v5/order/cancel', params=params)
    
    def get_orders(self, category: str, symbol: str = None, orderId: str = None, 
                 orderLinkId: str = None, orderStatus: str = None, 
                 limit: int = 50) -> Dict[str, Any]:
        """
        Получение информации об ордерах
        
        Args:
            category: Категория (spot, linear, inverse)
            symbol: Символ торговой пары (опционально)
            orderId: ID ордера (опционально)
            orderLinkId: Пользовательский ID ордера (опционально)
            orderStatus: Статус ордера (опционально)
            limit: Количество записей (макс. 50)
            
        Returns:
            Dict[str, Any]: Информация об ордерах
        """
        params = {'category': category, 'limit': limit}
        
        if symbol:
            params['symbol'] = symbol
        if orderId:
            params['orderId'] = orderId
        if orderLinkId:
            params['orderLinkId'] = orderLinkId
        if orderStatus:
            params['orderStatus'] = orderStatus
        
        return self._request('GET', '/v5/order/history', params=params)
    
    def set_trading_stop(self, category: str, symbol: str, positionIdx: int, 
                        stopLoss: str = None, takeProfit: str = None, **kwargs) -> Dict[str, Any]:
        """
        Установка стоп-лосса и тейк-профита для позиции
        
        Args:
            category: Категория (linear, inverse)
            symbol: Символ торговой пары
            positionIdx: Индекс позиции (0: одностороннее, 1: Buy, 2: Sell)
            stopLoss: Цена стоп-лосса (опционально)
            takeProfit: Цена тейк-профита (опционально)
            **kwargs: Дополнительные параметры
            
        Returns:
            Dict[str, Any]: Результат установки стоп-лосса и тейк-профита
        """
        params = {
            'category': category,
            'symbol': symbol,
            'positionIdx': positionIdx
        }
        
        if stopLoss:
            params['stopLoss'] = stopLoss
        if takeProfit:
            params['takeProfit'] = takeProfit
        
        # Добавление дополнительных параметров
        params.update(kwargs)
        
        return self._request('POST', '/v5/position/trading-stop', params=params)
    
    def get_instruments_info(self, category: str, symbol: str = None) -> Dict[str, Any]:
        """
        Получение информации об инструментах
        
        Args:
            category: Категория (spot, linear, inverse, option)
            symbol: Символ торговой пары (опционально)
            
        Returns:
            Dict[str, Any]: Информация об инструментах
        """
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        return self._request('GET', '/v5/market/instruments-info', params=params, use_cache=True)
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Получение информации об аккаунте
        
        Returns:
            Dict[str, Any]: Информация об аккаунте
        """
        return self._request('GET', '/v5/account/info')
    
    def get_transaction_log(self, category: str, accountType: str = "UNIFIED", 
                          symbol: str = None, limit: int = 50) -> Dict[str, Any]:
        """
        Получение истории транзакций
        
        Args:
            category: Категория (spot, linear, inverse, option)
            accountType: Тип аккаунта (UNIFIED, CONTRACT, SPOT)
            symbol: Символ торговой пары (опционально)
            limit: Количество записей (макс. 50)
            
        Returns:
            Dict[str, Any]: История транзакций
        """
        params = {
            'category': category,
            'accountType': accountType,
            'limit': limit
        }
        if symbol:
            params['symbol'] = symbol
        return self._request('GET', '/v5/account/transaction-log', params=params)
    
    def clear_cache(self) -> None:
        """
        Очистка кэша
        """
        self.cache = {}
        self.logger.info("Кэш очищен")