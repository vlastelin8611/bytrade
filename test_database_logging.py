#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест системы логирования в базу данных
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from database.db_manager import DatabaseManager
import tempfile
import logging
from datetime import datetime

def test_database_logging():
    """Тест основного функционала логирования в БД"""
    print("=== ТЕСТ ЛОГИРОВАНИЯ В БАЗУ ДАННЫХ ===")
    
    # Создаем временную базу данных
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        # Инициализируем менеджер БД
        db_manager = DatabaseManager(temp_db_path)
        db_manager.initialize_database()  # Создаем таблицы
        print("✓ DatabaseManager инициализирован")
        
        # Тест записи логов
        test_logs = [
            {
                'level': 'INFO',
                'logger_name': 'test_logger',
                'message': 'Тестовое информационное сообщение',
                'module': 'test_module',
                'function': 'test_function',
                'line_number': 42
            },
            {
                'level': 'ERROR',
                'logger_name': 'error_logger',
                'message': 'Тестовая ошибка',
                'exception': 'TestException: Это тестовое исключение'
            },
            {
                'level': 'WARNING',
                'logger_name': 'warning_logger',
                'message': 'Тестовое предупреждение'
            }
        ]
        
        for log_data in test_logs:
            db_manager.log_entry(log_data)
        print(f"✓ Записано {len(test_logs)} логов в базу данных")
        
        # Тест записи торговых операций
        test_trades = [
            {
                'order_id': 'TEST_001',
                'symbol': 'BTCUSDT',
                'side': 'Buy',
                'order_type': 'Market',
                'quantity': 0.001,
                'price': 50000.0,
                'executed_price': 50000.0,
                'executed_quantity': 0.001,
                'status': 'Filled',
                'strategy_name': 'test_strategy',
                'environment': 'testnet'
            },
            {
                'order_id': 'TEST_002',
                'symbol': 'ETHUSDT',
                'side': 'Sell',
                'order_type': 'Limit',
                'quantity': 0.01,
                'price': 3000.0,
                'status': 'New',
                'strategy_name': 'test_strategy',
                'environment': 'testnet'
            }
        ]
        
        for trade_data in test_trades:
            db_manager.log_trade(trade_data)
        print(f"✓ Записано {len(test_trades)} торговых операций")
        
        # Тест записи действий стратегий
        strategy_actions = [
            {
                'strategy_name': 'adaptive_ml_strategy',
                'symbol': 'BTCUSDT',
                'action': 'signal_generated',
                'technical_details': 'RSI: 30, MACD: bullish_crossover',
                'human_readable': 'Сгенерирован сигнал на покупку BTC',
                'data': {'rsi': 30, 'macd_signal': 'bullish'}
            },
            {
                'strategy_name': 'scalping_strategy',
                'symbol': 'ETHUSDT',
                'action': 'position_opened',
                'technical_details': 'Entry: 3000, SL: 2950, TP: 3050',
                'human_readable': 'Открыта позиция по ETH',
                'data': {'entry_price': 3000, 'stop_loss': 2950, 'take_profit': 3050}
            }
        ]
        
        for action_data in strategy_actions:
            db_manager.log_strategy_action(action_data)
        print(f"✓ Записано {len(strategy_actions)} действий стратегий")
        
        # Тест записи API запросов
        db_manager.log_api_request(
            endpoint='/v5/position/list',
            method='GET',
            params={'category': 'linear'},
            response_code=200,
            success=True,
            response_time=150.5
        )
        print("✓ Записан лог API запроса")
        
        # Проверяем что данные записались
        with db_manager.get_session() as session:
            from database.db_manager import LogEntry, TradeEntry, StrategyLog, APIRequest
            
            log_count = session.query(LogEntry).count()
            trade_count = session.query(TradeEntry).count()
            strategy_count = session.query(StrategyLog).count()
            api_count = session.query(APIRequest).count()
            
            print(f"✓ Проверка записей: логи={log_count}, сделки={trade_count}, стратегии={strategy_count}, API={api_count}")
            
            if log_count >= len(test_logs) and trade_count >= len(test_trades) and strategy_count >= len(strategy_actions) and api_count >= 1:
                print("✓ Все данные успешно записаны в базу данных")
            else:
                raise Exception("Не все данные записались в базу данных")
        
        db_manager.close()
        print("\n=== ВСЕ ТЕСТЫ ЛОГИРОВАНИЯ В БД ПРОЙДЕНЫ ===")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в тесте логирования: {e}")
        return False
    
    finally:
        # Удаляем временную базу данных
        try:
            os.unlink(temp_db_path)
        except:
            pass

def test_database_handler():
    """Тест DatabaseLogHandler для интеграции с logging"""
    print("\n=== ТЕСТ DATABASE LOG HANDLER ===")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
        temp_db_path = temp_db.name
    
    try:
        from core.logger import DatabaseLogHandler
        
        # Создаем менеджер БД и обработчик
        db_manager = DatabaseManager(temp_db_path)
        db_manager.initialize_database()  # Создаем таблицы
        db_handler = DatabaseLogHandler(db_manager)
        
        # Создаем тестовый логгер
        test_logger = logging.getLogger('database_test_logger')
        test_logger.setLevel(logging.DEBUG)
        test_logger.addHandler(db_handler)
        
        # Записываем тестовые логи
        test_logger.info("Тестовое информационное сообщение")
        test_logger.warning("Тестовое предупреждение")
        test_logger.error("Тестовая ошибка")
        
        print("✓ Логи записаны через DatabaseLogHandler")
        
        # Проверяем что логи записались
        with db_manager.get_session() as session:
            from database.db_manager import LogEntry
            log_count = session.query(LogEntry).count()
            
            if log_count >= 3:
                print(f"✓ DatabaseLogHandler работает корректно: записано {log_count} логов")
            else:
                raise Exception(f"Недостаточно логов записано: {log_count}")
        
        db_manager.close()
        print("\n=== ТЕСТ DATABASE LOG HANDLER ПРОЙДЕН ===")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка в тесте DatabaseLogHandler: {e}")
        return False
    
    finally:
        try:
            os.unlink(temp_db_path)
        except:
            pass

if __name__ == "__main__":
    success1 = test_database_logging()
    success2 = test_database_handler()
    
    if success1 and success2:
        print("\n🎉 ВСЕ ТЕСТЫ ЛОГИРОВАНИЯ В БАЗУ ДАННЫХ УСПЕШНО ПРОЙДЕНЫ!")
        sys.exit(0)
    else:
        print("\n❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        sys.exit(1)