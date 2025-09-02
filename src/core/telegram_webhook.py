#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Webhook обработчик для интерактивных кнопок

Обрабатывает callback-запросы от кнопок в Telegram уведомлениях.
Поддерживает команды: статус, пауза, стоп, логи.
"""

import logging
import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime
from aiohttp import web
from aiohttp.web import Request, Response


class TelegramWebhookHandler:
    """
    Обработчик webhook-запросов от Telegram
    """
    
    def __init__(self, bot_token: str, webhook_port: int = 8443):
        """
        Инициализация обработчика
        
        Args:
            bot_token: Токен бота
            webhook_port: Порт для webhook сервера
        """
        self.bot_token = bot_token
        self.webhook_port = webhook_port
        self.logger = logging.getLogger(__name__)
        
        # Обработчики команд
        self.command_handlers: Dict[str, Callable] = {}
        
        # Веб-приложение
        self.app = web.Application()
        self.app.router.add_post(f'/webhook/{bot_token}', self.handle_webhook)
        
        # Сервер
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None
        
    def register_command_handler(self, command: str, handler: Callable):
        """
        Регистрация обработчика команды
        
        Args:
            command: Команда (status, pause, stop, logs)
            handler: Функция-обработчик
        """
        self.command_handlers[command] = handler
        self.logger.info(f"Зарегистрирован обработчик для команды: {command}")
    
    async def handle_webhook(self, request: Request) -> Response:
        """
        Обработка webhook запроса от Telegram
        
        Args:
            request: HTTP запрос
            
        Returns:
            HTTP ответ
        """
        try:
            # Получаем данные запроса
            data = await request.json()
            
            # Проверяем, что это callback query
            if 'callback_query' in data:
                await self._handle_callback_query(data['callback_query'])
            
            return web.Response(text='OK')
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки webhook: {e}")
            return web.Response(text='Error', status=500)
    
    async def _handle_callback_query(self, callback_query: Dict[str, Any]):
        """
        Обработка callback query от кнопки
        
        Args:
            callback_query: Данные callback query
        """
        try:
            callback_data = callback_query.get('data')
            user_id = callback_query.get('from', {}).get('id')
            message_id = callback_query.get('message', {}).get('message_id')
            chat_id = callback_query.get('message', {}).get('chat', {}).get('id')
            
            self.logger.info(f"Получен callback: {callback_data} от пользователя {user_id}")
            
            # Отвечаем на callback query
            await self._answer_callback_query(callback_query['id'])
            
            # Обрабатываем команду
            if callback_data in self.command_handlers:
                handler = self.command_handlers[callback_data]
                try:
                    # Вызываем обработчик команды
                    if asyncio.iscoroutinefunction(handler):
                        result = await handler({
                            'user_id': user_id,
                            'chat_id': chat_id,
                            'message_id': message_id,
                            'command': callback_data
                        })
                    else:
                        result = handler({
                            'user_id': user_id,
                            'chat_id': chat_id,
                            'message_id': message_id,
                            'command': callback_data
                        })
                    
                    self.logger.info(f"Команда {callback_data} выполнена успешно")
                    
                except Exception as e:
                    self.logger.error(f"Ошибка выполнения команды {callback_data}: {e}")
            else:
                self.logger.warning(f"Неизвестная команда: {callback_data}")
                
        except Exception as e:
            self.logger.error(f"Ошибка обработки callback query: {e}")
    
    async def _answer_callback_query(self, callback_query_id: str, text: str = None):
        """
        Ответ на callback query
        
        Args:
            callback_query_id: ID callback query
            text: Текст ответа (опционально)
        """
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
            
            payload = {
                'callback_query_id': callback_query_id
            }
            
            if text:
                payload['text'] = text
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    if response.status != 200:
                        self.logger.warning(f"Ошибка ответа на callback query: {response.status}")
                        
        except Exception as e:
            self.logger.error(f"Ошибка отправки ответа на callback query: {e}")
    
    async def start_server(self):
        """
        Запуск webhook сервера
        """
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, 'localhost', self.webhook_port)
            await self.site.start()
            
            self.logger.info(f"Webhook сервер запущен на порту {self.webhook_port}")
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска webhook сервера: {e}")
            raise
    
    async def stop_server(self):
        """
        Остановка webhook сервера
        """
        try:
            if self.site:
                await self.site.stop()
                self.site = None
            
            if self.runner:
                await self.runner.cleanup()
                self.runner = None
            
            self.logger.info("Webhook сервер остановлен")
            
        except Exception as e:
            self.logger.error(f"Ошибка остановки webhook сервера: {e}")
    
    async def set_webhook(self, webhook_url: str):
        """
        Установка webhook URL в Telegram
        
        Args:
            webhook_url: URL для webhook
        """
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/setWebhook"
            
            payload = {
                'url': f"{webhook_url}/webhook/{self.bot_token}"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok'):
                            self.logger.info(f"Webhook установлен: {webhook_url}")
                            return True
                        else:
                            self.logger.error(f"Ошибка установки webhook: {data.get('description')}")
                            return False
                    else:
                        self.logger.error(f"HTTP ошибка установки webhook: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Ошибка установки webhook: {e}")
            return False
    
    async def delete_webhook(self):
        """
        Удаление webhook
        """
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/deleteWebhook"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok'):
                            self.logger.info("Webhook удален")
                            return True
                        else:
                            self.logger.error(f"Ошибка удаления webhook: {data.get('description')}")
                            return False
                    else:
                        self.logger.error(f"HTTP ошибка удаления webhook: {response.status}")
                        return False
                        
        except Exception as e:
            self.logger.error(f"Ошибка удаления webhook: {e}")
            return False


class TelegramCommandProcessor:
    """
    Процессор команд от Telegram кнопок
    """
    
    def __init__(self, config_manager, db_manager, strategy_engine):
        """
        Инициализация процессора
        
        Args:
            config_manager: Менеджер конфигурации
            db_manager: Менеджер базы данных
            strategy_engine: Движок стратегий
        """
        self.config = config_manager
        self.db = db_manager
        self.strategy_engine = strategy_engine
        self.logger = logging.getLogger(__name__)
        
        # Telegram клиент для ответов
        self.telegram_client = None
    
    def set_telegram_client(self, telegram_client):
        """
        Установка Telegram клиента для отправки ответов
        
        Args:
            telegram_client: Экземпляр TelegramClient
        """
        self.telegram_client = telegram_client
    
    async def handle_status_command(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка команды "Статус"
        
        Args:
            callback_data: Данные callback
            
        Returns:
            Результат выполнения команды
        """
        try:
            self.logger.info("Обработка команды статус")
            
            # Получаем данные аккаунта
            account_data = await self._get_account_status()
            
            # Отправляем статус через Telegram клиент
            if self.telegram_client:
                result = await self.telegram_client.send_status_update(account_data)
                return {
                    'success': True,
                    'message': 'Статус отправлен',
                    'data': result
                }
            else:
                return {
                    'success': False,
                    'message': 'Telegram клиент не настроен'
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка обработки команды статус: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    async def handle_pause_command(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка команды "Пауза"
        
        Args:
            callback_data: Данные callback
            
        Returns:
            Результат выполнения команды
        """
        try:
            self.logger.info("Обработка команды пауза")
            
            # Приостанавливаем все стратегии
            paused_strategies = []
            if hasattr(self.strategy_engine, 'pause_all_strategies'):
                paused_strategies = await self.strategy_engine.pause_all_strategies()
            
            # Отправляем уведомление
            if self.telegram_client:
                message = f"🔄 Все стратегии приостановлены\n\nПриостановлено стратегий: {len(paused_strategies)}"
                await self.telegram_client.send_notification('system', message, add_buttons=False)
            
            return {
                'success': True,
                'message': f'Приостановлено {len(paused_strategies)} стратегий',
                'paused_strategies': paused_strategies
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки команды пауза: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    async def handle_stop_command(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка команды "Стоп"
        
        Args:
            callback_data: Данные callback
            
        Returns:
            Результат выполнения команды
        """
        try:
            self.logger.info("Обработка команды стоп")
            
            # Останавливаем все стратегии
            stopped_strategies = []
            if hasattr(self.strategy_engine, 'stop_all_strategies'):
                stopped_strategies = await self.strategy_engine.stop_all_strategies()
            
            # Отправляем уведомление
            if self.telegram_client:
                message = f"🛑 Все стратегии остановлены\n\nОстановлено стратегий: {len(stopped_strategies)}"
                await self.telegram_client.send_notification('system', message, add_buttons=False)
            
            return {
                'success': True,
                'message': f'Остановлено {len(stopped_strategies)} стратегий',
                'stopped_strategies': stopped_strategies
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки команды стоп: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    async def handle_logs_command(self, callback_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка команды "Логи"
        
        Args:
            callback_data: Данные callback
            
        Returns:
            Результат выполнения команды
        """
        try:
            self.logger.info("Обработка команды логи")
            
            # Получаем последние логи
            logs = await self._get_recent_logs()
            
            # Отправляем логи через Telegram
            if self.telegram_client and logs:
                log_message = "📋 **ПОСЛЕДНИЕ ЛОГИ**\n\n"
                for log in logs[-10:]:  # Последние 10 записей
                    timestamp = log.get('timestamp', 'N/A')
                    level = log.get('level', 'INFO')
                    message = log.get('message', '')[:100]  # Обрезаем длинные сообщения
                    log_message += f"`{timestamp}` [{level}] {message}\n"
                
                await self.telegram_client.send_notification('system', log_message, add_buttons=False)
            
            return {
                'success': True,
                'message': f'Отправлено {len(logs)} записей логов',
                'logs_count': len(logs)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки команды логи: {e}")
            return {
                'success': False,
                'message': f'Ошибка: {str(e)}'
            }
    
    async def _get_account_status(self) -> Dict[str, Any]:
        """
        Получение статуса аккаунта
        
        Returns:
            Данные статуса аккаунта
        """
        try:
            # Здесь должна быть логика получения реальных данных аккаунта
            # Пока возвращаем заглушку
            return {
                'balance': {
                    'equity': '0.00',
                    'available': '0.00'
                },
                'mode': 'Testnet' if self.config.is_testnet() else 'Mainnet',
                'active_strategies': 'Нет активных стратегий',
                'last_activity': datetime.now().strftime('%H:%M:%S %d.%m.%Y')
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка получения статуса аккаунта: {e}")
            return {
                'balance': {'equity': 'N/A', 'available': 'N/A'},
                'mode': 'Unknown',
                'active_strategies': 'Ошибка получения данных',
                'last_activity': 'N/A'
            }
    
    async def _get_recent_logs(self) -> List[Dict[str, Any]]:
        """
        Получение последних логов
        
        Returns:
            Список записей логов
        """
        try:
            # Здесь должна быть логика получения логов из БД
            # Пока возвращаем заглушку
            return [
                {
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'level': 'INFO',
                    'message': 'Система работает нормально'
                },
                {
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'level': 'DEBUG',
                    'message': 'Обновление данных рынка'
                }
            ]
            
        except Exception as e:
            self.logger.error(f"Ошибка получения логов: {e}")
            return []