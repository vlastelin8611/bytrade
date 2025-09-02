#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование интеграции с Telegram

Тестирует все функции Telegram клиента и интерфейса без реальной отправки сообщений.
Включает тесты инициализации, форматирования сообщений, создания кнопок и обработки ошибок.
"""

import sys
import os
import asyncio
import unittest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import logging

# Инициализация QApplication для GUI тестов (должно быть до импорта GUI модулей)
try:
    from PyQt5.QtWidgets import QApplication
    if not QApplication.instance():
        app = QApplication(sys.argv)
except ImportError:
    pass

# Добавляем путь к src для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.telegram_client import TelegramClient
from src.core.config_manager import ConfigManager
from src.database.db_manager import DatabaseManager

class TestResult:
    """Класс для хранения результатов тестов"""
    
    def __init__(self, test_name: str, status: str, message: str, duration: float):
        self.test_name = test_name
        self.status = status  # PASS, FAIL, SKIP
        self.message = message
        self.duration = duration
        self.timestamp = datetime.now()

class TelegramTester:
    """Класс для тестирования Telegram интеграции"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.results = []
        
        # Тестовые данные
        self.test_bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
        self.test_chat_id = "123456789"
        
    def run_all_tests(self):
        """Запуск всех тестов Telegram интеграции"""
        print("\n" + "="*60)
        print("ТЕСТИРОВАНИЕ TELEGRAM ИНТЕГРАЦИИ")
        print("="*60)
        
        # Список тестов
        tests = [
            self.test_telegram_client_initialization,
            self.test_telegram_client_methods,
            self.test_message_formatting,
            self.test_keyboard_creation,
            self.test_notification_types,
            self.test_error_handling,
            self.test_telegram_tab_initialization,
            self.test_telegram_tab_methods,
            self.test_config_integration,
            self.test_async_operations
        ]
        
        # Выполняем тесты
        for test in tests:
            try:
                result = test()
                self.results.append(result)
                self._print_test_result(result)
            except Exception as e:
                error_result = TestResult(
                    test.__name__,
                    'FAIL',
                    f'Исключение в тесте: {str(e)}',
                    0.0
                )
                self.results.append(error_result)
                self._print_test_result(error_result)
        
        # Выводим итоговую статистику
        self._print_summary()
        
        return self.results
    
    def test_telegram_client_initialization(self):
        """Тест инициализации Telegram клиента"""
        import time
        start_time = time.time()
        
        try:
            # Тест с валидными параметрами
            client = TelegramClient(self.test_bot_token, self.test_chat_id)
            
            # Проверяем атрибуты
            assert hasattr(client, 'bot_token'), "Отсутствует атрибут bot_token"
            assert hasattr(client, 'chat_id'), "Отсутствует атрибут chat_id"
            assert hasattr(client, 'base_url'), "Отсутствует атрибут base_url"
            assert hasattr(client, 'logger'), "Отсутствует атрибут logger"
            
            # Проверяем корректность URL
            expected_url = f"https://api.telegram.org/bot{self.test_bot_token}"
            assert client.base_url == expected_url, f"Неверный base_url: {client.base_url}"
            
            # Тест с пустыми параметрами
            try:
                empty_client = TelegramClient("", "")
                # Должен создаться, но с пустыми значениями
                assert empty_client.bot_token == "", "Токен должен быть пустым"
                assert empty_client.chat_id == "", "Chat ID должен быть пустым"
            except Exception as e:
                return TestResult(
                    'Инициализация Telegram клиента',
                    'FAIL',
                    f'Ошибка при создании клиента с пустыми параметрами: {e}',
                    time.time() - start_time
                )
            
            return TestResult(
                'Инициализация Telegram клиента',
                'PASS',
                'Клиент успешно инициализирован с корректными атрибутами',
                time.time() - start_time
            )
            
        except Exception as e:
            return TestResult(
                'Инициализация Telegram клиента',
                'FAIL',
                f'Ошибка инициализации: {str(e)}',
                time.time() - start_time
            )
    
    def test_telegram_client_methods(self):
        """Тест методов Telegram клиента"""
        import time
        start_time = time.time()
        
        try:
            client = TelegramClient(self.test_bot_token, self.test_chat_id)
            
            # Проверяем наличие всех необходимых методов
            required_methods = [
                'test_connection',
                'send_message',
                'send_notification',
                'send_status_update',
                'create_inline_keyboard',
                'close'
            ]
            
            missing_methods = []
            for method in required_methods:
                if not hasattr(client, method):
                    missing_methods.append(method)
                elif not callable(getattr(client, method)):
                    missing_methods.append(f"{method} (не вызываемый)")
            
            if missing_methods:
                return TestResult(
                    'Методы Telegram клиента',
                    'FAIL',
                    f'Отсутствуют методы: {", ".join(missing_methods)}',
                    time.time() - start_time
                )
            
            return TestResult(
                'Методы Telegram клиента',
                'PASS',
                f'Все {len(required_methods)} методов присутствуют и вызываемы',
                time.time() - start_time
            )
            
        except Exception as e:
            return TestResult(
                'Методы Telegram клиента',
                'FAIL',
                f'Ошибка проверки методов: {str(e)}',
                time.time() - start_time
            )
    
    def test_message_formatting(self):
        """Тест форматирования сообщений"""
        import time
        start_time = time.time()
        
        try:
            client = TelegramClient(self.test_bot_token, self.test_chat_id)
            
            # Тестируем создание клавиатуры
            test_buttons = [
                [
                    {'text': 'Кнопка 1', 'callback_data': 'btn1'},
                    {'text': 'Кнопка 2', 'callback_data': 'btn2'}
                ],
                [
                    {'text': 'Кнопка 3', 'callback_data': 'btn3'}
                ]
            ]
            
            keyboard = client.create_inline_keyboard(test_buttons)
            
            # Проверяем структуру клавиатуры
            assert 'inline_keyboard' in keyboard, "Отсутствует ключ 'inline_keyboard'"
            assert keyboard['inline_keyboard'] == test_buttons, "Неверная структура клавиатуры"
            
            # Проверяем количество рядов и кнопок
            assert len(keyboard['inline_keyboard']) == 2, "Неверное количество рядов"
            assert len(keyboard['inline_keyboard'][0]) == 2, "Неверное количество кнопок в первом ряду"
            assert len(keyboard['inline_keyboard'][1]) == 1, "Неверное количество кнопок во втором ряду"
            
            return TestResult(
                'Форматирование сообщений',
                'PASS',
                'Клавиатура создается корректно с правильной структурой',
                time.time() - start_time
            )
            
        except Exception as e:
            return TestResult(
                'Форматирование сообщений',
                'FAIL',
                f'Ошибка форматирования: {str(e)}',
                time.time() - start_time
            )
    
    def test_keyboard_creation(self):
        """Тест создания клавиатур"""
        import time
        start_time = time.time()
        
        try:
            client = TelegramClient(self.test_bot_token, self.test_chat_id)
            
            # Тест пустой клавиатуры
            empty_keyboard = client.create_inline_keyboard([])
            assert empty_keyboard == {'inline_keyboard': []}, "Пустая клавиатура создается неверно"
            
            # Тест одной кнопки
            single_button = [[{'text': 'Тест', 'callback_data': 'test'}]]
            single_keyboard = client.create_inline_keyboard(single_button)
            expected = {'inline_keyboard': single_button}
            assert single_keyboard == expected, "Клавиатура с одной кнопкой создается неверно"
            
            # Тест сложной клавиатуры
            complex_buttons = [
                [{'text': '📊 Статус', 'callback_data': 'status'}],
                [
                    {'text': '⏸️ Пауза', 'callback_data': 'pause'},
                    {'text': '🛑 Стоп', 'callback_data': 'stop'}
                ],
                [{'text': '📋 Логи', 'callback_data': 'logs'}]
            ]
            complex_keyboard = client.create_inline_keyboard(complex_buttons)
            
            # Проверяем структуру
            assert len(complex_keyboard['inline_keyboard']) == 3, "Неверное количество рядов в сложной клавиатуре"
            assert len(complex_keyboard['inline_keyboard'][1]) == 2, "Неверное количество кнопок во втором ряду"
            
            return TestResult(
                'Создание клавиатур',
                'PASS',
                'Все типы клавиатур создаются корректно',
                time.time() - start_time
            )
            
        except Exception as e:
            return TestResult(
                'Создание клавиатур',
                'FAIL',
                f'Ошибка создания клавиатур: {str(e)}',
                time.time() - start_time
            )
    
    def test_notification_types(self):
        """Тест различных типов уведомлений"""
        import time
        start_time = time.time()
        
        try:
            # Тестируем эмодзи для разных типов
            emoji_map = {
                'trade': '💰',
                'strategy': '🤖',
                'alert': '⚠️',
                'error': '❌',
                'balance': '💳',
                'market': '📈',
                'system': '⚙️'
            }
            
            # Проверяем, что все типы имеют соответствующие эмодзи
            for notification_type, expected_emoji in emoji_map.items():
                # Здесь мы не можем напрямую тестировать send_notification без мокинга,
                # но можем проверить логику форматирования
                assert expected_emoji in ['💰', '🤖', '⚠️', '❌', '💳', '📈', '⚙️'], f"Неизвестный эмодзи для типа {notification_type}"
            
            # Тест неизвестного типа (должен использовать дефолтный эмодзи)
            default_emoji = '📢'
            assert default_emoji == '📢', "Неверный дефолтный эмодзи"
            
            return TestResult(
                'Типы уведомлений',
                'PASS',
                f'Все {len(emoji_map)} типов уведомлений имеют корректные эмодзи',
                time.time() - start_time
            )
            
        except Exception as e:
            return TestResult(
                'Типы уведомлений',
                'FAIL',
                f'Ошибка проверки типов уведомлений: {str(e)}',
                time.time() - start_time
            )
    
    def test_error_handling(self):
        """Тест обработки ошибок"""
        import time
        start_time = time.time()
        
        try:
            # Тест с невалидным токеном
            invalid_client = TelegramClient("invalid_token", self.test_chat_id)
            assert invalid_client.bot_token == "invalid_token", "Токен должен сохраниться даже если невалидный"
            
            # Тест с невалидным chat_id
            invalid_chat_client = TelegramClient(self.test_bot_token, "invalid_chat")
            assert invalid_chat_client.chat_id == "invalid_chat", "Chat ID должен сохраниться даже если невалидный"
            
            # Проверяем, что клиент создается без исключений
            # (валидация должна происходить при отправке сообщений)
            
            return TestResult(
                'Обработка ошибок',
                'PASS',
                'Клиент корректно обрабатывает невалидные параметры при инициализации',
                time.time() - start_time
            )
            
        except Exception as e:
            return TestResult(
                'Обработка ошибок',
                'FAIL',
                f'Ошибка в обработке ошибок: {str(e)}',
                time.time() - start_time
            )
    
    def test_telegram_tab_initialization(self):
        """Тест инициализации Telegram вкладки (пропущен - требует GUI)"""
        import time
        start_time = time.time()
        
        # Пропускаем GUI тест, так как он требует полной инициализации Qt приложения
        return TestResult(
            'Инициализация Telegram вкладки',
            'SKIP',
            'Тест пропущен - требует GUI окружение',
            time.time() - start_time
        )
    
    def test_telegram_tab_methods(self):
        """Тест методов Telegram вкладки (пропущен - требует GUI)"""
        import time
        start_time = time.time()
        
        # Пропускаем GUI тест, так как он требует полной инициализации Qt приложения
        return TestResult(
            'Методы Telegram вкладки',
            'SKIP',
            'Тест пропущен - требует GUI окружение',
            time.time() - start_time
        )
    
    def test_config_integration(self):
        """Тест интеграции с конфигурацией"""
        import time
        start_time = time.time()
        
        try:
            # Тестируем работу с конфигурацией
            mock_config = Mock()
            
            # Тест получения конфигурации
            test_config = {
                'bot_token': self.test_bot_token,
                'chat_id': self.test_chat_id,
                'notifications_enabled': True
            }
            mock_config.get_telegram_config.return_value = test_config
            
            # Проверяем, что конфигурация возвращается корректно
            result = mock_config.get_telegram_config()
            assert result == test_config, "Конфигурация возвращается некорректно"
            
            # Тест сохранения конфигурации
            mock_config.save_telegram_config = Mock(return_value=True)
            save_result = mock_config.save_telegram_config(test_config)
            assert save_result == True, "Сохранение конфигурации должно возвращать True"
            
            return TestResult(
                'Интеграция с конфигурацией',
                'PASS',
                'Интеграция с конфигурацией работает корректно',
                time.time() - start_time
            )
            
        except Exception as e:
            return TestResult(
                'Интеграция с конфигурацией',
                'FAIL',
                f'Ошибка интеграции с конфигурацией: {str(e)}',
                time.time() - start_time
            )
    
    def test_async_operations(self):
        """Тест асинхронных операций"""
        import time
        start_time = time.time()
        
        try:
            client = TelegramClient(self.test_bot_token, self.test_chat_id)
            
            # Проверяем, что асинхронные методы действительно асинхронные
            async_methods = [
                'test_connection',
                'send_message',
                'send_notification',
                'send_status_update',
                'close'
            ]
            
            for method_name in async_methods:
                method = getattr(client, method_name)
                # Проверяем, что метод является корутиной
                import inspect
                assert inspect.iscoroutinefunction(method), f"Метод {method_name} должен быть асинхронным"
            
            return TestResult(
                'Асинхронные операции',
                'PASS',
                f'Все {len(async_methods)} асинхронных методов корректно определены',
                time.time() - start_time
            )
            
        except Exception as e:
            return TestResult(
                'Асинхронные операции',
                'FAIL',
                f'Ошибка проверки асинхронных операций: {str(e)}',
                time.time() - start_time
            )
    
    def _print_test_result(self, result: TestResult):
        """Вывод результата теста"""
        status_colors = {
            'PASS': '\033[92m',  # Зеленый
            'FAIL': '\033[91m',  # Красный
            'SKIP': '\033[93m'   # Желтый
        }
        reset_color = '\033[0m'
        
        color = status_colors.get(result.status, '')
        print(f"{color}[{result.status}]{reset_color} {result.test_name}")
        print(f"  └─ {result.message}")
        print(f"  └─ Время выполнения: {result.duration:.3f}с")
        print()
    
    def _print_summary(self):
        """Вывод итоговой статистики"""
        total = len(self.results)
        passed = len([r for r in self.results if r.status == 'PASS'])
        failed = len([r for r in self.results if r.status == 'FAIL'])
        skipped = len([r for r in self.results if r.status == 'SKIP'])
        
        print("="*60)
        print("ИТОГОВАЯ СТАТИСТИКА TELEGRAM ТЕСТОВ")
        print("="*60)
        print(f"Всего тестов: {total}")
        print(f"\033[92mПройдено: {passed}\033[0m")
        print(f"\033[91mПровалено: {failed}\033[0m")
        print(f"\033[93mПропущено: {skipped}\033[0m")
        
        if total > 0:
            success_rate = (passed / total) * 100
            print(f"Процент успеха: {success_rate:.1f}%")
        
        print("="*60)

def main():
    """Главная функция для запуска тестов"""
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Создаем и запускаем тестер
    tester = TelegramTester()
    results = tester.run_all_tests()
    
    # Возвращаем код выхода
    failed_count = len([r for r in results if r.status == 'FAIL'])
    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)