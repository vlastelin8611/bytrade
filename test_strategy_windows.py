#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест системы окон стратегий
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from gui.strategy_window_manager import StrategyWindowManager
from gui.strategy_window import StrategyWindow
import tempfile
import time

def test_strategy_window_creation():
    """Тест создания окон стратегий"""
    print("=== ТЕСТ СОЗДАНИЯ ОКОН СТРАТЕГИЙ ===")
    
    try:
        # Создаем менеджер окон
        window_manager = StrategyWindowManager()
        print("✓ StrategyWindowManager создан")
        
        # Тестируем создание окна стратегии
        strategy_name = "test_strategy_1"
        window = window_manager.create_strategy_window(strategy_name)
        
        if window is not None:
            print(f"✓ Окно стратегии '{strategy_name}' создано")
        else:
            raise Exception("Не удалось создать окно стратегии")
        
        # Проверяем, что окно зарегистрировано в менеджере
        if window_manager.is_strategy_window_open(strategy_name):
            print("✓ Окно зарегистрировано в менеджере")
        else:
            raise Exception("Окно не зарегистрировано в менеджере")
        
        # Проверяем количество окон
        window_count = window_manager.get_window_count()
        if window_count == 1:
            print(f"✓ Количество окон корректно: {window_count}")
        else:
            raise Exception(f"Неверное количество окон: {window_count}")
        
        # Тестируем получение существующего окна
        existing_window = window_manager.get_strategy_window(strategy_name)
        if existing_window == window:
            print("✓ Получение существующего окна работает")
        else:
            raise Exception("Ошибка получения существующего окна")
        
        # Закрываем окно
        window_manager.close_strategy_window(strategy_name)
        
        # Проверяем, что окно закрыто
        if not window_manager.is_strategy_window_open(strategy_name):
            print("✓ Окно успешно закрыто")
        else:
            raise Exception("Окно не закрылось")
        
        print("\n=== ТЕСТ СОЗДАНИЯ ОКОН СТРАТЕГИЙ ПРОЙДЕН ===")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в тесте создания окон: {e}")
        return False

def test_multiple_strategy_windows():
    """Тест создания нескольких окон стратегий"""
    print("\n=== ТЕСТ МНОЖЕСТВЕННЫХ ОКОН СТРАТЕГИЙ ===")
    
    try:
        window_manager = StrategyWindowManager()
        
        # Создаем несколько окон
        strategy_names = ["strategy_1", "strategy_2", "strategy_3"]
        windows = {}
        
        for name in strategy_names:
            window = window_manager.create_strategy_window(name)
            windows[name] = window
            print(f"✓ Создано окно для стратегии '{name}'")
        
        # Проверяем количество окон
        window_count = window_manager.get_window_count()
        if window_count == len(strategy_names):
            print(f"✓ Создано {window_count} окон")
        else:
            raise Exception(f"Неверное количество окон: {window_count}, ожидалось: {len(strategy_names)}")
        
        # Проверяем, что все окна зарегистрированы
        for name in strategy_names:
            if not window_manager.is_strategy_window_open(name):
                raise Exception(f"Окно '{name}' не зарегистрировано")
        print("✓ Все окна зарегистрированы")
        
        # Получаем информацию об активных стратегиях
        active_strategies = window_manager.get_active_strategies()
        if len(active_strategies) == len(strategy_names):
            print(f"✓ Получена информация о {len(active_strategies)} активных стратегиях")
        else:
            raise Exception(f"Неверное количество активных стратегий: {len(active_strategies)}")
        
        # Закрываем все окна
        window_manager.close_all_windows()
        
        # Проверяем, что все окна закрыты
        final_count = window_manager.get_window_count()
        if final_count == 0:
            print("✓ Все окна успешно закрыты")
        else:
            raise Exception(f"Не все окна закрыты: осталось {final_count}")
        
        print("\n=== ТЕСТ МНОЖЕСТВЕННЫХ ОКОН СТРАТЕГИЙ ПРОЙДЕН ===")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в тесте множественных окон: {e}")
        return False

def test_strategy_window_logging():
    """Тест логирования в окнах стратегий"""
    print("\n=== ТЕСТ ЛОГИРОВАНИЯ В ОКНАХ СТРАТЕГИЙ ===")
    
    try:
        window_manager = StrategyWindowManager()
        
        # Создаем окно стратегии
        strategy_name = "logging_test_strategy"
        window = window_manager.create_strategy_window(strategy_name)
        print(f"✓ Создано окно для стратегии '{strategy_name}'")
        
        # Тестируем добавление технических логов
        test_logs = [
            "[INFO] Стратегия инициализирована",
            "[DEBUG] Получены рыночные данные",
            "[WARNING] Высокая волатильность",
            "[ERROR] Ошибка подключения к API"
        ]
        
        for log_message in test_logs:
            window_manager.add_log_to_strategy(strategy_name, log_message)
        print(f"✓ Добавлено {len(test_logs)} технических логов")
        
        # Тестируем добавление человеческих объяснений
        human_messages = [
            "Стратегия успешно запущена и готова к работе",
            "Анализируем текущую рыночную ситуацию",
            "Обнаружена повышенная волатильность на рынке",
            "Временные проблемы с подключением, переподключаемся"
        ]
        
        for human_message in human_messages:
            window_manager.add_human_message_to_strategy(strategy_name, human_message)
        print(f"✓ Добавлено {len(human_messages)} человеческих объяснений")
        
        # Проверяем статус стратегии
        status = window.get_strategy_status()
        if status['name'] == strategy_name and status['window_open']:
            print("✓ Статус стратегии получен корректно")
        else:
            raise Exception("Неверный статус стратегии")
        
        # Закрываем окно
        window_manager.close_strategy_window(strategy_name)
        print("✓ Окно закрыто")
        
        print("\n=== ТЕСТ ЛОГИРОВАНИЯ В ОКНАХ СТРАТЕГИЙ ПРОЙДЕН ===")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в тесте логирования: {e}")
        return False

def test_strategy_window_duplicate_creation():
    """Тест создания дублирующихся окон"""
    print("\n=== ТЕСТ ДУБЛИРУЮЩИХСЯ ОКОН ===")
    
    try:
        window_manager = StrategyWindowManager()
        
        strategy_name = "duplicate_test_strategy"
        
        # Создаем первое окно
        window1 = window_manager.create_strategy_window(strategy_name)
        print(f"✓ Создано первое окно для '{strategy_name}'")
        
        # Пытаемся создать второе окно с тем же именем
        window2 = window_manager.create_strategy_window(strategy_name)
        print(f"✓ Попытка создания второго окна для '{strategy_name}'")
        
        # Проверяем, что возвращается то же окно
        if window1 == window2:
            print("✓ Возвращено существующее окно (дублирование предотвращено)")
        else:
            raise Exception("Создано дублирующееся окно")
        
        # Проверяем, что количество окон = 1
        window_count = window_manager.get_window_count()
        if window_count == 1:
            print("✓ Количество окон корректно (1)")
        else:
            raise Exception(f"Неверное количество окон: {window_count}")
        
        # Закрываем окно
        window_manager.close_strategy_window(strategy_name)
        
        print("\n=== ТЕСТ ДУБЛИРУЮЩИХСЯ ОКОН ПРОЙДЕН ===")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в тесте дублирующихся окон: {e}")
        return False

def run_all_tests():
    """Запуск всех тестов окон стратегий"""
    print("🚀 ЗАПУСК ТЕСТОВ СИСТЕМЫ ОКОН СТРАТЕГИЙ\n")
    
    # Создаем QApplication для GUI тестов
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    tests = [
        test_strategy_window_creation,
        test_multiple_strategy_windows,
        test_strategy_window_logging,
        test_strategy_window_duplicate_creation
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"✗ Критическая ошибка в тесте {test_func.__name__}: {e}")
    
    print(f"\n📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"Всего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    print(f"Успешность: {(passed/total)*100:.1f}%")
    
    if passed == total:
        print("\n🎉 ВСЕ ТЕСТЫ СИСТЕМЫ ОКОН СТРАТЕГИЙ УСПЕШНО ПРОЙДЕНЫ!")
        return True
    else:
        print("\n❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)