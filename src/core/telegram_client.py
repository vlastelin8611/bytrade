#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram клиент для отправки уведомлений

Использует HTTP API Telegram для отправки сообщений и создания интерактивных кнопок.
Поддерживает асинхронную отправку и обработку ошибок.
"""

import logging
import asyncio
import aiohttp
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime


class TelegramClient:
    """
    Клиент для работы с Telegram Bot API
    """
    
    def __init__(self, bot_token: str, chat_id: str):
        """
        Инициализация клиента
        
        Args:
            bot_token: Токен бота от @BotFather
            chat_id: ID чата для отправки сообщений
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = logging.getLogger(__name__)
        
        # Сессия для HTTP запросов
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """
        Получение HTTP сессии
        """
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session
    
    async def close(self):
        """
        Закрытие HTTP сессии
        """
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def test_connection(self) -> Dict[str, Any]:
        """
        Тестирование подключения к боту
        
        Returns:
            Dict с результатом теста
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/getMe"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        bot_info = data.get('result', {})
                        return {
                            'success': True,
                            'message': f"Подключение успешно. Бот: {bot_info.get('first_name', 'Unknown')}",
                            'bot_info': bot_info
                        }
                    else:
                        return {
                            'success': False,
                            'message': f"Ошибка API: {data.get('description', 'Unknown error')}"
                        }
                else:
                    return {
                        'success': False,
                        'message': f"HTTP ошибка: {response.status}"
                    }
        
        except Exception as e:
            self.logger.error(f"Ошибка тестирования подключения: {e}")
            return {
                'success': False,
                'message': f"Ошибка подключения: {str(e)}"
            }
    
    async def send_message(
        self, 
        text: str, 
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Отправка сообщения
        
        Args:
            text: Текст сообщения
            parse_mode: Режим парсинга (HTML, Markdown)
            reply_markup: Клавиатура с кнопками
            
        Returns:
            Dict с результатом отправки
        """
        try:
            session = await self._get_session()
            url = f"{self.base_url}/sendMessage"
            
            payload = {
                'chat_id': self.chat_id,
                'text': text,
                'parse_mode': parse_mode
            }
            
            if reply_markup:
                payload['reply_markup'] = json.dumps(reply_markup)
            
            async with session.post(url, data=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('ok'):
                        return {
                            'success': True,
                            'message': 'Сообщение отправлено',
                            'message_id': data.get('result', {}).get('message_id')
                        }
                    else:
                        return {
                            'success': False,
                            'message': f"Ошибка API: {data.get('description', 'Unknown error')}"
                        }
                else:
                    return {
                        'success': False,
                        'message': f"HTTP ошибка: {response.status}"
                    }
        
        except Exception as e:
            self.logger.error(f"Ошибка отправки сообщения: {e}")
            return {
                'success': False,
                'message': f"Ошибка отправки: {str(e)}"
            }
    
    def create_inline_keyboard(self, buttons: List[List[Dict[str, str]]]) -> Dict:
        """
        Создание инлайн клавиатуры
        
        Args:
            buttons: Список рядов кнопок, каждая кнопка - dict с 'text' и 'callback_data'
            
        Returns:
            Dict с клавиатурой
        """
        return {
            'inline_keyboard': buttons
        }
    
    async def send_notification(
        self, 
        notification_type: str, 
        message: str, 
        add_buttons: bool = True
    ) -> Dict[str, Any]:
        """
        Отправка уведомления с кнопками
        
        Args:
            notification_type: Тип уведомления (trade, strategy, alert, error, etc.)
            message: Текст уведомления
            add_buttons: Добавлять ли интерактивные кнопки
            
        Returns:
            Dict с результатом отправки
        """
        # Форматируем сообщение
        timestamp = datetime.now().strftime("%H:%M:%S %d.%m.%Y")
        
        # Эмодзи для разных типов уведомлений
        emoji_map = {
            'trade': '💰',
            'strategy': '🤖',
            'alert': '⚠️',
            'error': '❌',
            'balance': '💳',
            'market': '📈',
            'system': '⚙️'
        }
        
        emoji = emoji_map.get(notification_type.lower(), '📢')
        formatted_message = f"{emoji} <b>{notification_type.upper()}</b>\n\n{message}\n\n<i>🕐 {timestamp}</i>"
        
        # Создаем кнопки если нужно
        reply_markup = None
        if add_buttons:
            buttons = [
                [
                    {'text': '📊 Статус', 'callback_data': 'status'},
                    {'text': '⏸️ Пауза', 'callback_data': 'pause'}
                ],
                [
                    {'text': '🛑 Стоп', 'callback_data': 'stop'},
                    {'text': '📋 Логи', 'callback_data': 'logs'}
                ]
            ]
            reply_markup = self.create_inline_keyboard(buttons)
        
        return await self.send_message(formatted_message, reply_markup=reply_markup)
    
    async def send_status_update(self, account_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Отправка обновления статуса аккаунта
        
        Args:
            account_data: Данные аккаунта
            
        Returns:
            Dict с результатом отправки
        """
        try:
            # Форматируем данные аккаунта
            balance = account_data.get('balance', {})
            equity = balance.get('equity', 'N/A')
            available = balance.get('available', 'N/A')
            mode = account_data.get('mode', 'Unknown')
            
            message = f"""📊 <b>СТАТУС АККАУНТА</b>

💰 <b>Баланс:</b>
• Equity: {equity} USDT
• Available: {available} USDT

⚙️ <b>Режим:</b> {mode}

🤖 <b>Активные стратегии:</b>
{account_data.get('active_strategies', 'Нет активных стратегий')}

📈 <b>Последняя активность:</b>
{account_data.get('last_activity', 'Нет данных')}"""
            
            return await self.send_notification('system', message, add_buttons=False)
        
        except Exception as e:
            self.logger.error(f"Ошибка отправки статуса: {e}")
            return {
                'success': False,
                'message': f"Ошибка отправки статуса: {str(e)}"
            }
    
    def __del__(self):
        """
        Деструктор - закрываем сессию
        """
        if hasattr(self, '_session') and self._session and not self._session.closed:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._session.close())
                else:
                    loop.run_until_complete(self._session.close())
            except Exception:
                pass  # Игнорируем ошибки при закрытии