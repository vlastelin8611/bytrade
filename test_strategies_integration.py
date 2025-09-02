#!/usr/bin/env python3
"""
Тест интеграции стратегий
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.strategies import (
    AVAILABLE_STRATEGIES, 
    STRATEGY_METADATA,
    get_strategy_class,
    get_strategy_metadata,
    list_available_strategies
)

def test_strategies_integration():
    print("=== Тест интеграции стратегий ===")
    
    # Проверяем доступные стратегии
    print(f"\nДоступные стратегии: {list(AVAILABLE_STRATEGIES.keys())}")
    
    # Проверяем метаданные
    print("\nМетаданные стратегий:")
    for strategy_key in AVAILABLE_STRATEGIES.keys():
        metadata = get_strategy_metadata(strategy_key)
        print(f"  {strategy_key}: {metadata['name']} (Risk: {metadata['risk_level']})")
    
    # Проверяем создание экземпляров стратегий
    print("\nТест создания экземпляров стратегий:")
    for strategy_key in AVAILABLE_STRATEGIES.keys():
        try:
            strategy_class = get_strategy_class(strategy_key)
            print(f"  ✓ {strategy_key}: {strategy_class.__name__} - OK")
        except Exception as e:
            print(f"  ✗ {strategy_key}: Ошибка - {e}")
    
    # Проверяем функцию list_available_strategies
    print("\nСписок доступных стратегий:")
    strategies_list = list_available_strategies()
    for strategy in strategies_list:
        print(f"  - {strategy}")
    
    print("\n=== Тест завершен ===")

if __name__ == "__main__":
    test_strategies_integration()