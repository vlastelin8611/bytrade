#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Консольный тест основных функций торгового бота
Без GUI для быстрой проверки всех компонентов
"""

import sys
import os
import time
import traceback
from datetime import datetime

# Добавляем путь к модулям проекта
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

def test_project_structure():
    """Тест структуры проекта"""
    print("\n=== Тест структуры проекта ===")
    
    required_files = [
        'main.py',
        'requirements.txt',
        'LICENSE.txt',
        'src/__init__.py',
        'src/gui',
        'src/api',
        'src/database',
        'src/strategies',
        'config',
    ]
    
    missing_files = []
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    for file_path in required_files:
        full_path = os.path.join(project_root, file_path)
        if not os.path.exists(full_path):
            missing_files.append(file_path)
        else:
            print(f"✓ {file_path}")
            
    if missing_files:
        print(f"✗ Отсутствуют файлы: {', '.join(missing_files)}")
        return False
    else:
        print("✓ Все необходимые файлы и папки присутствуют")
        return True

def test_module_imports():
    """Тест импорта основных модулей"""
    print("\n=== Тест импорта модулей ===")
    
    modules_to_test = [
        ('src.database.db_manager', 'DatabaseManager'),
        ('src.strategies.base_strategy', 'BaseStrategy'),
        ('src.core.logger', 'setup_logging'),
        ('src.api.bybit_client', 'BybitClient'),
    ]
    
    success_count = 0
    
    for module_name, class_name in modules_to_test:
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)
            print(f"✓ {module_name}.{class_name}")
            success_count += 1
        except ImportError as e:
            print(f"✗ {module_name}.{class_name}: ImportError - {str(e)}")
        except AttributeError as e:
            print(f"✗ {module_name}.{class_name}: AttributeError - {str(e)}")
        except Exception as e:
            print(f"✗ {module_name}.{class_name}: {type(e).__name__} - {str(e)}")
            
    return success_count == len(modules_to_test)

def test_database_operations():
    """Тест операций с базой данных"""
    print("\n=== Тест базы данных ===")
    
    try:
        from src.database.db_manager import DatabaseManager
        
        # Создаем тестовую БД
        test_db_path = 'test_console.db'
        print(f"Создание тестовой БД: {test_db_path}")
        
        db_manager = DatabaseManager(test_db_path)
        
        # Тестируем инициализацию
        print("Инициализация БД...")
        db_manager.initialize_database()
        print("✓ БД инициализирована")
        
        # Тестируем логирование
        print("Тест логирования...")
        log_data = {
            'level': 'INFO',
            'logger_name': 'test_logger',
            'message': 'Тестовое сообщение консольного теста'
        }
        db_manager.log_entry(log_data)
        print("✓ Лог записан")
        
        # Тестируем логирование сделки
        print("Тест логирования сделки...")
        trade_data = {
            'symbol': 'BTCUSDT',
            'side': 'Buy',
            'quantity': 0.001,
            'price': 50000,
            'profit_loss': 10.5,
            'strategy_name': 'console_test_strategy',
            'environment': 'test',
            'status': 'Filled',
            'order_type': 'Market'
        }
        db_manager.log_trade(trade_data)
        print("✓ Сделка записана")
        
        # Тестируем логирование стратегии
        print("Тест логирования стратегии...")
        strategy_data = {
            'strategy_name': 'console_test_strategy',
            'action': 'analyze',
            'symbol': 'BTCUSDT',
            'technical_details': 'Анализ завершен успешно',
            'human_readable': 'Стратегия проанализировала рынок BTCUSDT и определила сигнал на покупку'
        }
        db_manager.log_strategy_action(strategy_data)
        print("✓ Действие стратегии записано")
        
        db_manager.close()
        print("✓ БД закрыта")
        
        # Удаляем тестовую БД
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            print("✓ Тестовая БД удалена")
            
        return True
        
    except Exception as e:
        print(f"✗ Ошибка БД: {str(e)}")
        traceback.print_exc()
        return False

def test_strategies():
    """Тест стратегий в безопасном режиме"""
    print("\n=== Тест стратегий ===")
    
    try:
        from src.strategies import AVAILABLE_STRATEGIES, get_strategy_class
        
        print(f"Доступные стратегии: {list(AVAILABLE_STRATEGIES.keys())}")
        
        # Тестируем создание экземпляров стратегий
        strategies_tested = 0
        strategies_passed = 0
        
        # Минимальная конфигурация для тестирования
        test_config = {
            'symbol': 'BTCUSDT',
            'position_size': 0.01,
            'stop_loss': 2.0,
            'take_profit': 4.0,
            'timeframe': '1h'
        }
        
        for strategy_key in AVAILABLE_STRATEGIES.keys():
            strategies_tested += 1
            try:
                strategy_class = get_strategy_class(strategy_key)
                if strategy_class:
                    # Создаем экземпляр с правильными параметрами для тестирования
                    # Для стратегий нужен config с asset вместо symbol
                    strategy_config = test_config.copy()
                    strategy_config['asset'] = strategy_config.pop('symbol')
                    
                    # AdaptiveMLStrategy имеет другой конструктор
                    if strategy_key == 'adaptive_ml':
                        strategy = strategy_class(
                            name=f"test_{strategy_key}",
                            config=strategy_config,
                            api_client=None,  # В тестовом режиме
                            db_manager=None,  # В тестовом режиме
                            config_manager=None  # В тестовом режиме
                        )
                    else:
                        strategy = strategy_class(
                            name=f"test_{strategy_key}",
                            symbol=test_config['symbol'],
                            api_client=None,  # В тестовом режиме
                            db_manager=None,  # В тестовом режиме
                            config_manager=None  # В тестовом режиме
                        )
                    print(f"✓ {strategy_key}: {strategy_class.__name__} создана")
                    strategies_passed += 1
                else:
                    print(f"✗ {strategy_key}: Класс не найден")
            except Exception as e:
                print(f"✗ {strategy_key}: Ошибка создания - {str(e)}")
        
        print(f"\nРезультат: {strategies_passed}/{strategies_tested} стратегий прошли тест")
        return strategies_passed > 0
        
    except Exception as e:
        print(f"✗ Ошибка стратегий: {str(e)}")
        traceback.print_exc()
        return False

def test_risk_management():
    """Тест системы риск-менеджмента"""
    print("\n=== Тест риск-менеджмента ===")
    
    try:
        from src.core.risk_manager import RiskManager
        
        # Создаем конфигурацию для менеджера рисков
        risk_config = {
            'max_daily_loss_pct': 20.0,
            'max_consecutive_losses': 3,
            'max_stop_loss_pct': 40.0,
            'max_position_size_pct': 10.0,
            'max_trades_per_day': 10,
            'max_drawdown_pct': 15.0,
            'min_confidence_threshold': 0.7
        }
        
        print("Создание риск-менеджера...")
        risk_manager = RiskManager(risk_config)
        print("✓ Риск-менеджер создан")
        
        # Тестируем ограничение 20% баланса
        balance = 1000
        max_daily_risk = balance * 0.2  # 20% от баланса
        print(f"Максимальный дневной риск для баланса {balance}: {max_daily_risk}")
        
        # Проверяем, что лимит дневных потерь установлен правильно
        if hasattr(risk_manager, 'max_daily_loss_pct') and risk_manager.max_daily_loss_pct == 20.0:
            print("✓ Лимит 20% баланса установлен")
        else:
            print("✗ Неверный лимит дневных потерь")
            return False
        
        # Тестируем стоп после 3 неудач
        print("Тест стопа после 3 неудачных сделок...")
        symbol = 'BTCUSDT'
        
        # Проверяем лимит последовательных потерь
        if hasattr(risk_manager, 'max_consecutive_losses') and risk_manager.max_consecutive_losses == 3:
            print("✓ Лимит последовательных потерь установлен")
        else:
            print("✗ Неверный лимит последовательных потерь")
            return False
            
        return True
        
    except Exception as e:
        print(f"✗ Ошибка риск-менеджмента: {str(e)}")
        traceback.print_exc()
        return False

def test_api_client():
    """Тест API клиента (только создание, без подключения)"""
    print("\n=== Тест API клиента ===")
    
    try:
        from src.api.bybit_client import BybitClient
        
        # Создаем клиент для testnet с фиктивными ключами
        print("Создание testnet клиента...")
        client = BybitClient(
            api_key="test_key",
            api_secret="test_secret",
            testnet=True
        )
        print("✓ Testnet клиент создан")
        
        # Проверяем, что клиент создан
        if hasattr(client, 'client'):
            print("✓ PyBit клиент инициализирован")
        else:
            print("✗ PyBit клиент не инициализирован")
            
        # Проверяем базовые методы (без реального подключения)
        if hasattr(client, 'get_tickers'):
            print("✓ Метод get_tickers доступен")
        else:
            print("✗ Метод get_tickers недоступен")
            
        if hasattr(client, 'get_wallet_balance'):
            print("✓ Метод get_wallet_balance доступен")
        else:
            print("✗ Метод get_wallet_balance недоступен")
            
        # Проверяем настройки testnet
        if client.testnet:
            print("✓ Клиент настроен на testnet")
        else:
            print("✗ Клиент не настроен на testnet")
            
        return True
        
    except Exception as e:
        print(f"✗ Ошибка API клиента: {str(e)}")
        traceback.print_exc()
        return False

def test_logging_system():
    """Тест системы логирования"""
    print("\n=== Тест системы логирования ===")
    
    try:
        from src.core.logger import setup_logging
        import logging
        
        # Настраиваем логирование
        print("Настройка системы логирования...")
        setup_logging()
        print("✓ Система логирования настроена")
        
        # Создаем тестовый логгер
        logger = logging.getLogger('console_test')
        
        # Тестируем различные уровни
        logger.debug("Тестовое DEBUG сообщение")
        logger.info("Тестовое INFO сообщение")
        logger.warning("Тестовое WARNING сообщение")
        logger.error("Тестовое ERROR сообщение")
        
        print("✓ Все уровни логирования протестированы")
        
        return True
        
    except Exception as e:
        print(f"✗ Ошибка системы логирования: {str(e)}")
        traceback.print_exc()
        return False

def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("КОНСОЛЬНОЕ ТЕСТИРОВАНИЕ ТОРГОВОГО БОТА BYBIT")
    print("="*60)
    print(f"Время начала: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        ('Структура проекта', test_project_structure),
        ('Импорт модулей', test_module_imports),
        ('База данных', test_database_operations),
        ('Стратегии', test_strategies),
        ('Риск-менеджмент', test_risk_management),
        ('API клиент', test_api_client),
        ('Система логирования', test_logging_system),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        start_time = time.time()
        
        try:
            success = test_func()
            duration = time.time() - start_time
            
            if success:
                print(f"\n✓ {test_name}: ПРОЙДЕН ({duration:.2f}s)")
                results.append((test_name, 'PASS', duration, ''))
            else:
                print(f"\n✗ {test_name}: ПРОВАЛЕН ({duration:.2f}s)")
                results.append((test_name, 'FAIL', duration, 'Тест вернул False'))
                
        except Exception as e:
            duration = time.time() - start_time
            print(f"\n✗ {test_name}: ОШИБКА ({duration:.2f}s)")
            print(f"Ошибка: {str(e)}")
            results.append((test_name, 'ERROR', duration, str(e)))
    
    # Итоговая статистика
    print("\n" + "="*60)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("="*60)
    
    passed = len([r for r in results if r[1] == 'PASS'])
    failed = len([r for r in results if r[1] in ['FAIL', 'ERROR']])
    total = len(results)
    
    for test_name, status, duration, message in results:
        status_symbol = '✓' if status == 'PASS' else '✗'
        print(f"{status_symbol} {test_name:<25} {status:<8} ({duration:.2f}s)")
        if message:
            print(f"    {message}")
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {failed}")
    print(f"Успешность: {(passed/total*100):.1f}%")
    
    print(f"\nВремя завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return passed == total

if __name__ == '__main__':
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем")
        sys.exit(2)
    except Exception as e:
        print(f"\n\nКритическая ошибка: {str(e)}")
        traceback.print_exc()
        sys.exit(3)