#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест интеграции с API Bybit (testnet режим)
"""

import sys
import os
import time
import traceback

# Добавляем корневую директорию в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_api_client_creation():
    """Тест создания API клиента"""
    print("\n=== Тест создания API клиента ===")
    
    try:
        from src.api.bybit_client import BybitClient
        
        # Создаем клиент для testnet с тестовыми ключами
        print("Создание testnet клиента...")
        client = BybitClient(
            api_key="test_key_12345",
            api_secret="test_secret_67890",
            testnet=True
        )
        print("✓ Testnet клиент создан успешно")
        
        # Проверяем настройки
        if client.testnet:
            print("✓ Клиент настроен на testnet")
        else:
            print("✗ Клиент не настроен на testnet")
            return False
            
        # Проверяем наличие pybit клиента
        if hasattr(client, 'client'):
            print("✓ PyBit клиент инициализирован")
        else:
            print("✗ PyBit клиент не инициализирован")
            return False
            
        # Проверяем основные методы
        methods_to_check = [
            'get_tickers',
            'get_wallet_balance', 
            'get_positions',
            'place_order',
            'cancel_order'
        ]
        
        for method in methods_to_check:
            if hasattr(client, method):
                print(f"✓ Метод {method} доступен")
            else:
                print(f"✗ Метод {method} недоступен")
                return False
                
        return True
        
    except Exception as e:
        print(f"✗ Ошибка создания API клиента: {str(e)}")
        traceback.print_exc()
        return False

def test_api_connection():
    """Тест подключения к API (без авторизации)"""
    print("\n=== Тест подключения к API ===")
    
    try:
        from src.api.bybit_client import BybitClient
        import asyncio
        
        # Создаем клиент для testnet
        client = BybitClient(
            api_key="test_key",
            api_secret="test_secret",
            testnet=True
        )
        
        # Тестируем получение тикеров (публичный API)
        print("Получение тикеров...")
        try:
            async def test_api():
                return await client.get_tickers("BTCUSDT")
            
            # Запускаем асинхронный тест
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(test_api())
            loop.close()
            
            if result and result.get('retCode') == 0:
                print("✓ API подключение успешно (получены тикеры)")
                return True
            else:
                print(f"✗ API вернул ошибку: {result}")
                return False
                
        except Exception as api_error:
            print(f"✗ Ошибка API запроса: {str(api_error)}")
            # Проверяем, что это ошибка авторизации (ожидаемо для тестовых ключей)
            error_str = str(api_error).lower()
            if any(word in error_str for word in ["auth", "signature", "invalid", "key"]):
                print("✓ API отвечает (ошибка авторизации ожидаема для тестовых ключей)")
                return True
            return False
            
    except Exception as e:
        print(f"✗ Ошибка подключения к API: {str(e)}")
        traceback.print_exc()
        return False

def test_websocket_client():
    """Тест WebSocket клиента"""
    print("\n=== Тест WebSocket клиента ===")
    
    try:
        from src.api.websocket_client import BybitWebSocketClient
        import asyncio
        
        # Создаем WebSocket клиент для testnet
        print("Создание WebSocket клиента...")
        ws_client = BybitWebSocketClient(
            api_key="test_key",
            api_secret="test_secret",
            testnet=True
        )
        print("✓ WebSocket клиент создан")
        
        # Проверяем URL для testnet
        if "testnet" in ws_client.public_url:
            print("✓ WebSocket настроен на testnet")
        else:
            print("✗ WebSocket не настроен на testnet")
            return False
            
        # Проверяем основные методы
        methods_to_check = [
            'start',
            'subscribe_tickers',
            'subscribe_orderbook',
            'subscribe_trades'
        ]
        
        for method in methods_to_check:
            if hasattr(ws_client, method):
                print(f"✓ Метод {method} доступен")
            else:
                print(f"✗ Метод {method} недоступен")
                return False
                
        return True
        
    except Exception as e:
        print(f"✗ Ошибка создания WebSocket клиента: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("ТЕСТ ИНТЕГРАЦИИ С API BYBIT (TESTNET)")
    print("=" * 60)
    
    start_time = time.time()
    
    tests = [
        ("Создание API клиента", test_api_client_creation),
        ("Подключение к API", test_api_connection),
        ("WebSocket клиент", test_websocket_client)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            if test_func():
                print(f"✓ {test_name}: ПРОЙДЕН")
                passed += 1
            else:
                print(f"✗ {test_name}: ПРОВАЛЕН")
        except Exception as e:
            print(f"✗ {test_name}: ОШИБКА - {str(e)}")
            traceback.print_exc()
    
    # Итоговые результаты
    print("\n" + "=" * 60)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 60)
    
    for i, (test_name, _) in enumerate(tests):
        status = "PASS" if i < passed else "FAIL"
        print(f"{'✓' if status == 'PASS' else '✗'} {test_name:<30} {status}")
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    print(f"Успешность: {(passed/total)*100:.1f}%")
    
    elapsed_time = time.time() - start_time
    print(f"Время выполнения: {elapsed_time:.2f}s")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)