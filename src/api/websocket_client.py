#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bybit WebSocket клиент

Обеспечивает получение данных в реальном времени:
- Подписка на рыночные данные
- Подписка на данные аккаунта
- Автоматическое переподключение
- Обработка ошибок
- Буферизация данных
"""

import logging
import json
import asyncio
import time
from typing import Dict, List, Any, Optional, Callable, Set
from datetime import datetime
from collections import defaultdict, deque

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatusCode

class WebSocketError(Exception):
    """Базовый класс для ошибок WebSocket"""
    pass

class WebSocketConnectionError(WebSocketError):
    """Ошибка подключения WebSocket"""
    pass

class WebSocketSubscriptionError(WebSocketError):
    """Ошибка подписки WebSocket"""
    pass

class BybitWebSocketClient:
    """
    WebSocket клиент для Bybit
    """
    
    def __init__(self, api_key: str = None, api_secret: str = None, testnet: bool = True, 
                 config_manager=None, db_manager=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # WebSocket URLs
        if testnet:
            self.public_url = "wss://stream-testnet.bybit.com/v5/public/spot"
            self.private_url = "wss://stream-testnet.bybit.com/v5/private"
        else:
            self.public_url = "wss://stream.bybit.com/v5/public/spot"
            self.private_url = "wss://stream.bybit.com/v5/private"
        
        # Соединения
        self.public_ws = None
        self.private_ws = None
        
        # Состояние подключений
        self.public_connected = False
        self.private_connected = False
        
        # Подписки
        self.public_subscriptions: Set[str] = set()
        self.private_subscriptions: Set[str] = set()
        
        # Обработчики данных
        self.data_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # Буферы данных
        self.data_buffers: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        
        # Статистика
        self.stats = {
            "messages_received": 0,
            "messages_processed": 0,
            "connection_errors": 0,
            "reconnections": 0,
            "last_message_time": None
        }
        
        # Флаги управления
        self.running = False
        self.auto_reconnect = True
        self.reconnect_delay = 5
        
        # Задачи asyncio
        self.tasks: List[asyncio.Task] = []
        
        self.logger.info(f"WebSocket клиент инициализирован (testnet: {testnet})")
    
    def add_data_handler(self, topic: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Добавление обработчика данных для определенного топика
        """
        self.data_handlers[topic].append(handler)
        self.logger.debug(f"Добавлен обработчик для топика: {topic}")
    
    def remove_data_handler(self, topic: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Удаление обработчика данных
        """
        if handler in self.data_handlers[topic]:
            self.data_handlers[topic].remove(handler)
            self.logger.debug(f"Удален обработчик для топика: {topic}")
    
    async def _authenticate_private_ws(self, ws):
        """
        Аутентификация для приватного WebSocket
        """
        if not self.api_key or not self.api_secret:
            raise WebSocketError("API ключи не предоставлены для приватного WebSocket")
        
        import hmac
        import hashlib
        
        expires = int((time.time() + 10) * 1000)
        signature_payload = f"GET/realtime{expires}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        auth_message = {
            "op": "auth",
            "args": [self.api_key, expires, signature]
        }
        
        await ws.send(json.dumps(auth_message))
        
        # Ждем подтверждения аутентификации
        response = await ws.recv()
        auth_response = json.loads(response)
        
        if not auth_response.get("success"):
            raise WebSocketError(f"Ошибка аутентификации: {auth_response}")
        
        self.logger.info("Аутентификация WebSocket успешна")
    
    async def _handle_message(self, message: str, ws_type: str):
        """
        Обработка входящего сообщения
        """
        try:
            data = json.loads(message)
            self.stats["messages_received"] += 1
            self.stats["last_message_time"] = datetime.now()
            
            # Обработка системных сообщений
            if "op" in data:
                if data["op"] == "pong":
                    self.logger.debug("Получен pong")
                    return
                elif data["op"] == "auth":
                    if data.get("success"):
                        self.logger.info("Аутентификация успешна")
                    else:
                        self.logger.error(f"Ошибка аутентификации: {data}")
                    return
                elif data["op"] == "subscribe":
                    if data.get("success"):
                        self.logger.info(f"Подписка успешна: {data.get('args', [])}")
                    else:
                        self.logger.error(f"Ошибка подписки: {data}")
                    return
            
            # Обработка данных
            if "topic" in data:
                topic = data["topic"]
                
                # Сохраняем в буфер
                self.data_buffers[topic].append({
                    "timestamp": datetime.now(),
                    "data": data
                })
                
                # Вызываем обработчики
                for handler in self.data_handlers[topic]:
                    try:
                        handler(data)
                        self.stats["messages_processed"] += 1
                    except Exception as e:
                        self.logger.error(f"Ошибка в обработчике {handler}: {e}")
                
                # Логируем в БД
                if self.db:
                    try:
                        self.db.log_market_data(
                            symbol=self._extract_symbol_from_topic(topic),
                            data_type=self._extract_data_type_from_topic(topic),
                            data=data,
                            source="websocket"
                        )
                    except Exception as e:
                        self.logger.error(f"Ошибка логирования WebSocket данных: {e}")
        
        except json.JSONDecodeError as e:
            self.logger.error(f"Ошибка парсинга JSON: {e}")
        except Exception as e:
            self.logger.error(f"Ошибка обработки сообщения: {e}")
    
    def _extract_symbol_from_topic(self, topic: str) -> str:
        """
        Извлечение символа из топика
        """
        # Примеры топиков:
        # orderbook.1.BTCUSDT
        # publicTrade.BTCUSDT
        # kline.1.BTCUSDT
        parts = topic.split('.')
        if len(parts) >= 2:
            return parts[-1]  # Последняя часть обычно символ
        return "UNKNOWN"
    
    def _extract_data_type_from_topic(self, topic: str) -> str:
        """
        Извлечение типа данных из топика
        """
        if topic.startswith("orderbook"):
            return "orderbook"
        elif topic.startswith("publicTrade"):
            return "trade"
        elif topic.startswith("kline"):
            return "kline"
        elif topic.startswith("tickers"):
            return "ticker"
        else:
            return "unknown"
    
    async def _websocket_handler(self, ws, ws_type: str):
        """
        Основной обработчик WebSocket соединения
        """
        try:
            # Аутентификация для приватного WS
            if ws_type == "private":
                await self._authenticate_private_ws(ws)
            
            # Восстанавливаем подписки
            if ws_type == "public" and self.public_subscriptions:
                await self._resubscribe_public(ws)
            elif ws_type == "private" and self.private_subscriptions:
                await self._resubscribe_private(ws)
            
            # Основной цикл получения сообщений
            async for message in ws:
                await self._handle_message(message, ws_type)
        
        except ConnectionClosed:
            self.logger.warning(f"WebSocket {ws_type} соединение закрыто")
        except Exception as e:
            self.logger.error(f"Ошибка в WebSocket {ws_type} обработчике: {e}")
            self.stats["connection_errors"] += 1
    
    async def _resubscribe_public(self, ws):
        """
        Восстановление публичных подписок
        """
        if self.public_subscriptions:
            subscribe_message = {
                "op": "subscribe",
                "args": list(self.public_subscriptions)
            }
            await ws.send(json.dumps(subscribe_message))
            self.logger.info(f"Восстановлены публичные подписки: {self.public_subscriptions}")
    
    async def _resubscribe_private(self, ws):
        """
        Восстановление приватных подписок
        """
        if self.private_subscriptions:
            subscribe_message = {
                "op": "subscribe",
                "args": list(self.private_subscriptions)
            }
            await ws.send(json.dumps(subscribe_message))
            self.logger.info(f"Восстановлены приватные подписки: {self.private_subscriptions}")
    
    async def _maintain_connection(self, ws_type: str):
        """
        Поддержание соединения с автоматическим переподключением
        """
        url = self.public_url if ws_type == "public" else self.private_url
        
        while self.running:
            try:
                self.logger.info(f"Подключение к WebSocket {ws_type}: {url}")
                
                async with websockets.connect(
                    url,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=10
                ) as ws:
                    
                    if ws_type == "public":
                        self.public_ws = ws
                        self.public_connected = True
                    else:
                        self.private_ws = ws
                        self.private_connected = True
                    
                    self.logger.info(f"WebSocket {ws_type} подключен")
                    
                    await self._websocket_handler(ws, ws_type)
            
            except (ConnectionClosed, InvalidStatusCode, OSError) as e:
                self.logger.error(f"Ошибка WebSocket {ws_type} соединения: {e}")
                self.stats["connection_errors"] += 1
            
            except Exception as e:
                self.logger.error(f"Неожиданная ошибка WebSocket {ws_type}: {e}")
                self.stats["connection_errors"] += 1
            
            finally:
                if ws_type == "public":
                    self.public_connected = False
                    self.public_ws = None
                else:
                    self.private_connected = False
                    self.private_ws = None
            
            if self.running and self.auto_reconnect:
                self.logger.info(f"Переподключение WebSocket {ws_type} через {self.reconnect_delay} сек")
                self.stats["reconnections"] += 1
                await asyncio.sleep(self.reconnect_delay)
            else:
                break
    
    async def start(self):
        """
        Запуск WebSocket клиента
        """
        if self.running:
            self.logger.warning("WebSocket клиент уже запущен")
            return
        
        self.running = True
        self.logger.info("Запуск WebSocket клиента")
        
        # Создаем задачи для публичного и приватного WebSocket
        public_task = asyncio.create_task(self._maintain_connection("public"))
        self.tasks.append(public_task)
        
        if self.api_key and self.api_secret:
            private_task = asyncio.create_task(self._maintain_connection("private"))
            self.tasks.append(private_task)
        
        # Ждем установления соединений
        await asyncio.sleep(2)
    
    async def stop(self):
        """
        Остановка WebSocket клиента
        """
        self.logger.info("Остановка WebSocket клиента")
        self.running = False
        
        # Закрываем соединения
        if self.public_ws:
            await self.public_ws.close()
        if self.private_ws:
            await self.private_ws.close()
        
        # Отменяем задачи
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Ждем завершения задач
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        self.logger.info("WebSocket клиент остановлен")
    
    # Методы подписки на публичные данные
    async def subscribe_orderbook(self, symbol: str, depth: int = 1):
        """
        Подписка на стакан заявок
        """
        topic = f"orderbook.{depth}.{symbol}"
        await self._subscribe_public(topic)
    
    async def subscribe_trades(self, symbol: str):
        """
        Подписка на сделки
        """
        topic = f"publicTrade.{symbol}"
        await self._subscribe_public(topic)
    
    async def subscribe_klines(self, symbol: str, interval: str):
        """
        Подписка на свечи
        """
        topic = f"kline.{interval}.{symbol}"
        await self._subscribe_public(topic)
    
    async def subscribe_tickers(self, symbol: str):
        """
        Подписка на тикеры
        """
        topic = f"tickers.{symbol}"
        await self._subscribe_public(topic)
    
    async def _subscribe_public(self, topic: str):
        """
        Подписка на публичный топик
        """
        self.public_subscriptions.add(topic)
        
        if self.public_connected and self.public_ws:
            subscribe_message = {
                "op": "subscribe",
                "args": [topic]
            }
            await self.public_ws.send(json.dumps(subscribe_message))
            self.logger.info(f"Подписка на публичный топик: {topic}")
    
    # Методы подписки на приватные данные
    async def subscribe_orders(self):
        """
        Подписка на ордера
        """
        topic = "order"
        await self._subscribe_private(topic)
    
    async def subscribe_executions(self):
        """
        Подписка на исполнения
        """
        topic = "execution"
        await self._subscribe_private(topic)
    
    async def subscribe_positions(self):
        """
        Подписка на позиции
        """
        topic = "position"
        await self._subscribe_private(topic)
    
    async def subscribe_wallet(self):
        """
        Подписка на кошелек
        """
        topic = "wallet"
        await self._subscribe_private(topic)
    
    async def _subscribe_private(self, topic: str):
        """
        Подписка на приватный топик
        """
        if not self.api_key or not self.api_secret:
            raise WebSocketError("API ключи не предоставлены для приватных подписок")
        
        self.private_subscriptions.add(topic)
        
        if self.private_connected and self.private_ws:
            subscribe_message = {
                "op": "subscribe",
                "args": [topic]
            }
            await self.private_ws.send(json.dumps(subscribe_message))
            self.logger.info(f"Подписка на приватный топик: {topic}")
    
    # Методы отписки
    async def unsubscribe_public(self, topic: str):
        """
        Отписка от публичного топика
        """
        self.public_subscriptions.discard(topic)
        
        if self.public_connected and self.public_ws:
            unsubscribe_message = {
                "op": "unsubscribe",
                "args": [topic]
            }
            await self.public_ws.send(json.dumps(unsubscribe_message))
            self.logger.info(f"Отписка от публичного топика: {topic}")
    
    async def unsubscribe_private(self, topic: str):
        """
        Отписка от приватного топика
        """
        self.private_subscriptions.discard(topic)
        
        if self.private_connected and self.private_ws:
            unsubscribe_message = {
                "op": "unsubscribe",
                "args": [topic]
            }
            await self.private_ws.send(json.dumps(unsubscribe_message))
            self.logger.info(f"Отписка от приватного топика: {topic}")
    
    # Утилиты
    def get_stats(self) -> Dict[str, Any]:
        """
        Получение статистики WebSocket
        """
        return {
            **self.stats,
            "public_connected": self.public_connected,
            "private_connected": self.private_connected,
            "public_subscriptions": list(self.public_subscriptions),
            "private_subscriptions": list(self.private_subscriptions),
            "buffer_sizes": {topic: len(buffer) for topic, buffer in self.data_buffers.items()}
        }
    
    def get_latest_data(self, topic: str, count: int = 1) -> List[Dict[str, Any]]:
        """
        Получение последних данных из буфера
        """
        if topic not in self.data_buffers:
            return []
        
        buffer = self.data_buffers[topic]
        return list(buffer)[-count:] if len(buffer) >= count else list(buffer)
    
    def clear_buffers(self):
        """
        Очистка буферов данных
        """
        self.data_buffers.clear()
        self.logger.info("Буферы WebSocket очищены")
    
    def is_connected(self) -> bool:
        """
        Проверка состояния подключения
        """
        return self.public_connected or self.private_connected
    
    def __del__(self):
        """
        Деструктор
        """
        if hasattr(self, 'logger'):
            self.logger.info("WebSocket клиент завершает работу")