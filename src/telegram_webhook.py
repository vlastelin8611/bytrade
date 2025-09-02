import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

class TelegramCommandProcessor:
    """Обработчик команд от кнопок Telegram"""
    
    def __init__(self, db_manager=None):
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
    
    def process_status_command(self, chat_id: str) -> str:
        """Обработка команды 'Status' - возвращает статус аккаунта и стратегий"""
        try:
            if not self.db_manager:
                return "❌ База данных недоступна"
            
            # Получаем информацию об аккаунте
            account_info = self._get_account_status()
            strategies_info = self._get_strategies_status()
            
            status_message = f"📊 **Статус аккаунта**\n\n"
            status_message += account_info + "\n\n"
            status_message += f"🎯 **Активные стратегии**\n\n"
            status_message += strategies_info
            
            return status_message
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении статуса: {e}")
            return "❌ Ошибка при получении статуса"
    
    def process_pause_command(self, chat_id: str) -> str:
        """Обработка команды 'Pause' - приостанавливает все стратегии"""
        try:
            # Здесь должна быть логика приостановки стратегий
            return "⏸️ Все стратегии приостановлены"
        except Exception as e:
            self.logger.error(f"Ошибка при приостановке стратегий: {e}")
            return "❌ Ошибка при приостановке стратегий"
    
    def process_stop_command(self, chat_id: str) -> str:
        """Обработка команды 'Stop' - останавливает все стратегии"""
        try:
            # Здесь должна быть логика остановки стратегий
            return "🛑 Все стратегии остановлены"
        except Exception as e:
            self.logger.error(f"Ошибка при остановке стратегий: {e}")
            return "❌ Ошибка при остановке стратегий"
    
    def process_logs_command(self, chat_id: str) -> str:
        """Обработка команды 'Logs' - возвращает последние логи"""
        try:
            logs = self._get_recent_logs()
            if not logs:
                return "📝 Логи пусты"
            
            logs_message = "📝 **Последние логи:**\n\n"
            for log in logs[-10:]:  # Последние 10 записей
                logs_message += f"{log}\n"
            
            return logs_message
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении логов: {e}")
            return "❌ Ошибка при получении логов"
    
    def _get_account_status(self) -> str:
        """Получает статус аккаунта из базы данных"""
        try:
            if not self.db_manager:
                return "База данных недоступна"
            
            # Здесь должна быть логика получения данных аккаунта
            return "💰 Баланс: Загрузка...\n📈 P&L: Загрузка...\n🔄 Статус: Активен"
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении статуса аккаунта: {e}")
            return "Ошибка загрузки данных аккаунта"
    
    def _get_strategies_status(self) -> str:
        """Получает статус стратегий из базы данных"""
        try:
            if not self.db_manager:
                return "База данных недоступна"
            
            # Здесь должна быть логика получения данных стратегий
            return "🎯 Активных стратегий: 0\n⏸️ Приостановленных: 0\n🛑 Остановленных: 0"
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении статуса стратегий: {e}")
            return "Ошибка загрузки данных стратегий"
    
    def _get_recent_logs(self) -> list:
        """Получает последние логи из базы данных"""
        try:
            if not self.db_manager:
                return []
            
            # Здесь должна быть логика получения логов
            return ["Пример лога 1", "Пример лога 2"]
            
        except Exception as e:
            self.logger.error(f"Ошибка при получении логов: {e}")
            return []


class TelegramWebhookHandler:
    """Обработчик webhook-запросов от Telegram"""
    
    def __init__(self, command_processor: TelegramCommandProcessor):
        self.command_processor = command_processor
        self.logger = logging.getLogger(__name__)
    
    def handle_callback_query(self, update_data: Dict[str, Any]) -> Optional[str]:
        """Обрабатывает callback query от кнопок"""
        try:
            callback_query = update_data.get('callback_query')
            if not callback_query:
                return None
            
            callback_data = callback_query.get('data')
            chat_id = str(callback_query.get('from', {}).get('id', ''))
            
            if not callback_data or not chat_id:
                return None
            
            # Обрабатываем различные команды
            if callback_data == 'status':
                return self.command_processor.process_status_command(chat_id)
            elif callback_data == 'pause':
                return self.command_processor.process_pause_command(chat_id)
            elif callback_data == 'stop':
                return self.command_processor.process_stop_command(chat_id)
            elif callback_data == 'logs':
                return self.command_processor.process_logs_command(chat_id)
            else:
                return f"❓ Неизвестная команда: {callback_data}"
                
        except Exception as e:
            self.logger.error(f"Ошибка при обработке callback query: {e}")
            return "❌ Ошибка при обработке команды"
    
    def handle_webhook_update(self, update_data: Dict[str, Any]) -> Optional[str]:
        """Основной обработчик webhook-обновлений"""
        try:
            # Обрабатываем callback queries от кнопок
            if 'callback_query' in update_data:
                return self.handle_callback_query(update_data)
            
            # Можно добавить обработку других типов обновлений
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка при обработке webhook: {e}")
            return "❌ Ошибка при обработке запроса"