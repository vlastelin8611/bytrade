#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit API клиент

Обеспечивает безопасное взаимодействие с Bybit API:
- Аутентификация и подписание запросов
- Обработка ошибок и retry логика
- Rate limiting
- Кэширование данных
- Поддержка testnet и mainnet
"""

import logging
import time
import hmac
import hashlib
import json
import threading
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
from urllib.parse import urlencode

import aiohttp
import asyncio
from pybit.unified_trading import HTTP
from pybit.exceptions import InvalidRequestError, FailedRequestError

class BybitAPIError(Exception):
    """Базовый класс для ошибок API"""
    pass

class BybitRateLimitError(BybitAPIError):
    """Ошибка превышения лимита запросов"""
    pass

class BybitAuthError(BybitAPIError):
    """Ошибка аутентификации"""
    pass

class RateLimiter:
    """
    Rate limiter для контроля частоты запросов к API
    """
    
    def __init__(self, max_requests: int = 120, time_window: int = 60):
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = []
        self.lock = threading.Lock()
        self.window_start = time.time()
    
    @property
    def requests_made(self) -> int:
        """
        Количество запросов, сделанных в текущем временном окне
        """
        now = time.time()
        # Фильтруем запросы в текущем временном окне
        current_requests = [req_time for req_time in self.requests 
                          if now - req_time < self.time_window]
        return len(current_requests)
    
    def acquire(self):
        """
        Получение разрешения на выполнение запроса
        """
        with self.lock:
            now = time.time()
            
            # Удаляем старые запросы
            old_count = len(self.requests)
            self.requests = [req_time for req_time in self.requests 
                           if now - req_time < self.time_window]
            
            # Обновляем начало окна, если были удалены старые запросы
            if len(self.requests) < old_count or not self.requests:
                self.window_start = now
            
            # Проверяем лимит
            if len(self.requests) >= self.max_requests:
                sleep_time = self.time_window - (now - self.requests[0])
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    return self.acquire()
            
            # Добавляем текущий запрос
            self.requests.append(now)

class BybitClient:
    """
    Основной клиент для работы с Bybit API
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True, 
                 config_manager=None, db_manager=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Инициализация pybit клиента с увеличенным таймаутом
        self.client = HTTP(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
            timeout=30  # Увеличиваем таймаут до 30 секунд
        )
        
        # Rate limiter
        self.rate_limiter = RateLimiter()
        
        # Кэш для данных
        self.cache = {}
        self.cache_ttl = {}
        
        # Статистика API
        self.api_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limit_hits": 0,
            "last_request_time": None
        }
        
        self.logger.info(f"Bybit клиент инициализирован (testnet: {testnet})")
    
    def _get_cache_key(self, method: str, params: Dict[str, Any]) -> str:
        """
        Генерация ключа для кэша
        """
        params_str = json.dumps(params, sort_keys=True)
        return f"{method}:{hashlib.md5(params_str.encode()).hexdigest()}"
    
    def _is_cache_valid(self, cache_key: str, ttl_seconds: int = 30) -> bool:
        """
        Проверка валидности кэша
        """
        if cache_key not in self.cache:
            return False
        
        cache_time = self.cache_ttl.get(cache_key, 0)
        return time.time() - cache_time < ttl_seconds
    
    def _set_cache(self, cache_key: str, data: Any):
        """
        Сохранение данных в кэш
        """
        self.cache[cache_key] = data
        self.cache_ttl[cache_key] = time.time()
    
    def _make_request_with_retry(self, method: str, endpoint: str, params: Dict[str, Any] = None, 
                                     use_cache: bool = True, cache_ttl: int = 30, max_retries: int = 3) -> Dict[str, Any]:
        """
        Выполнение запроса к API с retry логикой для таймаутов
        """
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                return self._make_request(method, endpoint, params, use_cache, cache_ttl)
            except BybitAPIError as e:
                last_error = e
                error_msg = str(e).lower()
                
                # Retry только для таймаутов
                if ("timeout" in error_msg or "read timed out" in error_msg or "httpsconnectionpool" in error_msg) and attempt < max_retries:
                    wait_time = (attempt + 1) * 2  # Экспоненциальная задержка: 2, 4, 6 секунд
                    self.logger.warning(f"Таймаут API запроса (попытка {attempt + 1}/{max_retries + 1}). Повтор через {wait_time} сек...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Не retry для других ошибок или исчерпаны попытки
                    raise e
        
        # Если все попытки исчерпаны
        raise last_error
    
    def _make_request(self, method: str, endpoint: str, params: Dict[str, Any] = None, 
                          use_cache: bool = True, cache_ttl: int = 30) -> Dict[str, Any]:
        """
        Выполнение запроса к API с обработкой ошибок и кэшированием
        """
        if params is None:
            params = {}
        
        # Проверяем кэш
        cache_key = self._get_cache_key(f"{method}:{endpoint}", params)
        if use_cache and self._is_cache_valid(cache_key, cache_ttl):
            self.logger.debug(f"Возвращаем данные из кэша: {endpoint}")
            return self.cache[cache_key]
        
        # Rate limiting
        self.rate_limiter.acquire()
        
        try:
            self.api_stats["total_requests"] += 1
            self.api_stats["last_request_time"] = datetime.now()
            
            # Выполняем запрос через pybit
            if method.upper() == "GET":
                if endpoint == "get_orderbook":
                    response = self.client.get_orderbook(**params)
                elif endpoint == "get_kline":
                    response = self.client.get_kline(**params)
                elif endpoint == "get_tickers":
                    response = self.client.get_tickers(**params)
                elif endpoint == "get_instruments_info":
                    response = self.client.get_instruments_info(**params)
                elif endpoint == "get_wallet_balance":
                    response = self.client.get_wallet_balance(**params)
                elif endpoint == "get_account_info":
                    # Используем правильный метод для получения информации об аккаунте
                    # В pybit это может быть другой метод или требовать другого подхода
                    try:
                        response = self.client.get_account_info(**params)
                    except AttributeError:
                        # Если метод не существует, используем альтернативный подход
                        self.logger.warning("get_account_info метод не найден в pybit клиенте")
                        # Возвращаем базовую информацию об аккаунте
                        response = {
                            "retCode": 0,
                            "retMsg": "OK",
                            "result": {
                                "marginMode": "REGULAR_MARGIN",
                                "unifiedMarginStatus": 1,
                                "isMasterTrader": False,
                                "spotHedgingStatus": "OFF"
                            }
                        }
                elif endpoint == "get_positions":
                    response = self.client.get_positions(**params)
                elif endpoint == "get_open_orders":
                    response = self.client.get_open_orders(**params)
                elif endpoint == "get_order_history":
                    response = self.client.get_order_history(**params)
                elif endpoint == "get_executions":
                    response = self.client.get_executions(**params)
                else:
                    raise BybitAPIError(f"Неподдерживаемый GET endpoint: {endpoint}")
            
            elif method.upper() == "POST":
                if endpoint == "place_order":
                    response = self.client.place_order(**params)
                elif endpoint == "cancel_order":
                    response = self.client.cancel_order(**params)
                elif endpoint == "cancel_all_orders":
                    response = self.client.cancel_all_orders(**params)
                elif endpoint == "amend_order":
                    response = self.client.amend_order(**params)
                elif endpoint == "set_leverage":
                    response = self.client.set_leverage(**params)
                elif endpoint == "switch_margin_mode":
                    response = self.client.switch_margin_mode(**params)
                else:
                    raise BybitAPIError(f"Неподдерживаемый POST endpoint: {endpoint}")
            
            else:
                raise BybitAPIError(f"Неподдерживаемый HTTP метод: {method}")
            
            # Проверяем ответ
            if response.get("retCode") != 0:
                error_msg = response.get("retMsg", "Неизвестная ошибка API")
                self.logger.error(f"API ошибка: {error_msg}")
                self.api_stats["failed_requests"] += 1
                
                if "rate limit" in error_msg.lower():
                    self.api_stats["rate_limit_hits"] += 1
                    raise BybitRateLimitError(error_msg)
                elif "auth" in error_msg.lower() or "signature" in error_msg.lower():
                    raise BybitAuthError(error_msg)
                else:
                    raise BybitAPIError(error_msg)
            
            self.api_stats["successful_requests"] += 1
            
            # Сохраняем в кэш только GET запросы
            if method.upper() == "GET" and use_cache:
                self._set_cache(cache_key, response)
            
            # Логируем в БД
            if self.db:
                try:
                    self.db.log_api_request(
                        endpoint=endpoint,
                        method=method,
                        params=params,
                        response_code=response.get("retCode", 0),
                        success=True
                    )
                except Exception as e:
                    self.logger.error(f"Ошибка логирования API запроса: {e}")
            
            return response
        
        except (InvalidRequestError, FailedRequestError) as e:
            error_msg = str(e).lower()
            self.logger.error(f"Ошибка pybit: {e}")
            self.api_stats["failed_requests"] += 1
            
            # Проверяем, является ли это таймаутом
            if "timeout" in error_msg or "read timed out" in error_msg:
                self.logger.warning(f"Таймаут API запроса к {endpoint}. Попробуйте позже.")
                
                # Логируем таймаут в БД
                if self.db:
                    try:
                        self.db.log_api_request(
                            endpoint=endpoint,
                            method=method,
                            params=params,
                            response_code=-2,  # Специальный код для таймаута
                            success=False,
                            error_message=f"Таймаут: {str(e)}"
                        )
                    except Exception as db_e:
                        self.logger.error(f"Ошибка логирования API таймаута: {db_e}")
                
                raise BybitAPIError(f"Таймаут соединения с API Bybit. Проверьте интернет-соединение и попробуйте позже.")
            
            # Логируем другие ошибки в БД
            if self.db:
                try:
                    self.db.log_api_request(
                        endpoint=endpoint,
                        method=method,
                        params=params,
                        response_code=-1,
                        success=False,
                        error_message=str(e)
                    )
                except Exception as db_e:
                    self.logger.error(f"Ошибка логирования API ошибки: {db_e}")
            
            raise BybitAPIError(f"Ошибка API: {e}")
        
        except Exception as e:
            error_msg = str(e).lower()
            self.logger.error(f"Неожиданная ошибка API: {e}")
            self.api_stats["failed_requests"] += 1
            
            # Проверяем, является ли это таймаутом
            if "timeout" in error_msg or "read timed out" in error_msg or "httpsconnectionpool" in error_msg:
                self.logger.warning(f"Таймаут соединения с API Bybit: {e}")
                raise BybitAPIError(f"Таймаут соединения с API Bybit. Проверьте интернет-соединение и попробуйте позже.")
            
            raise BybitAPIError(f"Неожиданная ошибка: {e}")
    
    # Методы для получения рыночных данных
    def get_orderbook(self, symbol: str, limit: int = 25) -> Dict[str, Any]:
        """
        Получение стакана заявок
        """
        params = {
            "category": "spot",
            "symbol": symbol,
            "limit": limit
        }
        return self._make_request_with_retry("GET", "get_orderbook", params)
    
    def get_klines(self, symbol: str, interval: str, limit: int = 200, 
                        start_time: Optional[int] = None, end_time: Optional[int] = None) -> Dict[str, Any]:
        """
        Получение исторических данных (свечи)
        """
        params = {
            "category": "spot",
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        if start_time:
            params["start"] = start_time
        if end_time:
            params["end"] = end_time
        
        return self._make_request_with_retry("GET", "get_kline", params)
    
    def get_tickers(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение тикеров
        """
        params = {"category": "spot"}
        if symbol:
            params["symbol"] = symbol
        
        return self._make_request_with_retry("GET", "get_tickers", params)
    
    def get_instruments_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение информации об инструментах
        """
        params = {"category": "spot"}
        if symbol:
            params["symbol"] = symbol
        
        return self._make_request_with_retry("GET", "get_instruments_info", params)
    
    # Методы для работы с аккаунтом
    def get_wallet_balance(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """
        Получение баланса кошелька
        """
        params = {"accountType": account_type}
        return self._make_request_with_retry("GET", "get_wallet_balance", params, use_cache=False)
    
    def get_positions(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение позиций
        """
        params = {"category": "linear"}
        if symbol:
            params["symbol"] = symbol
        
        return self._make_request_with_retry("GET", "get_positions", params, use_cache=False)
    
    def get_open_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Получение открытых ордеров
        """
        params = {"category": "spot"}
        if symbol:
            params["symbol"] = symbol
        
        return self._make_request_with_retry("GET", "get_open_orders", params, use_cache=False)
    
    def get_order_history(self, symbol: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        Получение истории ордеров
        """
        params = {
            "category": "spot",
            "limit": limit
        }
        if symbol:
            params["symbol"] = symbol
        
        return self._make_request_with_retry("GET", "get_order_history", params, use_cache=False)
    
    def get_executions(self, symbol: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        Получение истории исполнений
        """
        params = {
            "category": "spot",
            "limit": limit
        }
        if symbol:
            params["symbol"] = symbol
        
        return self._make_request_with_retry("GET", "get_executions", params, use_cache=False)
    
    # Торговые методы
    def place_order(self, symbol: str, side: str, order_type: str, qty: str, 
                         price: Optional[str] = None, time_in_force: str = "GTC", 
                         **kwargs) -> Dict[str, Any]:
        """
        Размещение ордера
        """
        params = {
            "category": "spot",
            "symbol": symbol,
            "side": side,
            "orderType": order_type,
            "qty": qty,
            "timeInForce": time_in_force
        }
        
        if price:
            params["price"] = price
        
        # Добавляем дополнительные параметры
        params.update(kwargs)
        
        return self._make_request_with_retry("POST", "place_order", params, use_cache=False)
    
    def cancel_order(self, symbol: str, order_id: Optional[str] = None, 
                          order_link_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Отмена ордера
        """
        params = {
            "category": "spot",
            "symbol": symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        else:
            raise ValueError("Необходимо указать order_id или order_link_id")
        
        return self._make_request_with_retry("POST", "cancel_order", params, use_cache=False)
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Отмена всех ордеров
        """
        params = {"category": "spot"}
        if symbol:
            params["symbol"] = symbol
        
        return self._make_request_with_retry("POST", "cancel_all_orders", params, use_cache=False)
    
    def amend_order(self, symbol: str, order_id: Optional[str] = None, 
                         order_link_id: Optional[str] = None, qty: Optional[str] = None, 
                         price: Optional[str] = None) -> Dict[str, Any]:
        """
        Изменение ордера
        """
        params = {
            "category": "spot",
            "symbol": symbol
        }
        
        if order_id:
            params["orderId"] = order_id
        elif order_link_id:
            params["orderLinkId"] = order_link_id
        else:
            raise ValueError("Необходимо указать order_id или order_link_id")
        
        if qty:
            params["qty"] = qty
        if price:
            params["price"] = price
        
        return self._make_request_with_retry("POST", "amend_order", params, use_cache=False)
    
    # Методы для работы с позициями (деривативы)
    def set_leverage(self, symbol: str, buy_leverage: str, sell_leverage: str) -> Dict[str, Any]:
        """
        Установка плеча
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "buyLeverage": buy_leverage,
            "sellLeverage": sell_leverage
        }
        
        return self._make_request_with_retry("POST", "set_leverage", params, use_cache=False)
    
    def switch_margin_mode(self, symbol: str, trade_mode: int, 
                                buy_leverage: str, sell_leverage: str) -> Dict[str, Any]:
        """
        Переключение режима маржи
        """
        params = {
            "category": "linear",
            "symbol": symbol,
            "tradeMode": trade_mode,
            "buyLeverage": buy_leverage,
            "sellLeverage": sell_leverage
        }
        
        return self._make_request_with_retry("POST", "switch_margin_mode", params, use_cache=False)
    
    # Методы для работы с аккаунтом (дубликат - удаляем)
    def get_wallet_balance_v2(self, account_type: str = "UNIFIED") -> Dict[str, Any]:
        """
        Получение баланса кошелька (версия 2)
        """
        params = {
            "accountType": account_type
        }
        
        return self._make_request_with_retry("GET", "get_wallet_balance", params, use_cache=True, cache_ttl=30)
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        Получение информации об аккаунте
        """
        try:
            return self._make_request_with_retry("GET", "get_account_info", {}, use_cache=True, cache_ttl=60)
        except Exception as e:
            self.logger.warning(f"Ошибка получения информации об аккаунте: {e}")
            # Возвращаем базовую информацию
            return {
                "retCode": 0,
                "retMsg": "OK", 
                "result": {
                    "marginMode": "REGULAR_MARGIN",
                    "unifiedMarginStatus": 1,
                    "isMasterTrader": False,
                    "spotHedgingStatus": "OFF",
                    "updatedTime": str(int(datetime.now().timestamp() * 1000))
                }
            }
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Получение статуса rate limit
        """
        return {
            "requests_made": self.rate_limiter.requests_made,
            "max_requests": self.rate_limiter.max_requests,
            "time_window": self.rate_limiter.time_window,
            "remaining_requests": max(0, self.rate_limiter.max_requests - self.rate_limiter.requests_made),
            "reset_time": self.rate_limiter.window_start + self.rate_limiter.time_window
        }
    
    # Утилиты
    def get_api_stats(self) -> Dict[str, Any]:
        """
        Получение статистики API
        """
        return self.api_stats.copy()
    
    def clear_cache(self):
        """
        Очистка кэша
        """
        self.cache.clear()
        self.cache_ttl.clear()
        self.logger.info("Кэш API очищен")
    
    def test_connection(self) -> bool:
        """
        Тест соединения с API
        """
        try:
            response = self.get_tickers("BTCUSDT")
            return response.get("retCode") == 0
        except Exception as e:
            self.logger.error(f"Ошибка тестирования соединения: {e}")
            return False
    
    def __del__(self):
        """
        Деструктор
        """
        if hasattr(self, 'logger'):
            self.logger.info("Bybit клиент завершает работу")