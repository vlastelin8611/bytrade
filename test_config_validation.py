#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест валидации конфигурации
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.config_manager import ConfigManager
import tempfile
import json
from pathlib import Path

def test_config_validation():
    """Тест валидации конфигурации"""
    print("=== ТЕСТ ВАЛИДАЦИИ КОНФИГУРАЦИИ ===")
    
    # Создаем временную директорию для тестов
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            # Инициализируем ConfigManager
            config_manager = ConfigManager(temp_dir)
            print("✓ ConfigManager инициализирован")
            
            # Тест загрузки конфигурации
            config = config_manager.config
            print(f"✓ Конфигурация загружена: {len(config)} разделов")
            
            # Тест получения значений
            testnet_mode = config_manager.get('trading.testnet', True)
            print(f"✓ Testnet режим: {testnet_mode}")
            
            # Тест установки значений
            config_manager.set('test.value', 'test_data')
            retrieved_value = config_manager.get('test.value')
            assert retrieved_value == 'test_data'
            print("✓ Установка и получение значений работает")
            
            # Тест валидации
            validation_errors = config_manager.validate_configuration()
            print(f"✓ Валидация выполнена: {len(validation_errors)} ошибок")
            
            # Тест сохранения
            config_manager.save()
            config_file = Path(temp_dir) / "config.json"
            assert config_file.exists()
            print("✓ Сохранение конфигурации работает")
            
            # Тест загрузки сохраненной конфигурации
            config_manager2 = ConfigManager(temp_dir)
            test_value = config_manager2.get('test.value')
            assert test_value == 'test_data'
            print("✓ Загрузка сохраненной конфигурации работает")
            
            print("\n=== ВСЕ ТЕСТЫ КОНФИГУРАЦИИ ПРОЙДЕНЫ ===")
            return True
            
        except Exception as e:
            print(f"✗ Ошибка в тесте конфигурации: {e}")
            return False

def test_risk_management_config():
    """Тест конфигурации риск-менеджмента"""
    print("\n=== ТЕСТ КОНФИГУРАЦИИ РИСК-МЕНЕДЖМЕНТА ===")
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_manager = ConfigManager(temp_dir)
            
            # Получаем настройки риск-менеджмента
            risk_limits = config_manager.get_risk_limits()
            print(f"✓ Лимиты риска получены: {risk_limits}")
            
            # Проверяем значения по умолчанию
            assert 0 < risk_limits['max_daily_balance_usage'] <= 1
            assert 0 < risk_limits['max_stop_loss_percent'] <= 1
            print("✓ Значения риск-менеджмента в допустимых пределах")
            
            # Тест изменения настроек
            config_manager.set('trading.max_daily_balance_usage', 0.15)
            updated_limits = config_manager.get_risk_limits()
            assert updated_limits['max_daily_balance_usage'] == 0.15
            print("✓ Обновление настроек риск-менеджмента работает")
            
            print("\n=== ТЕСТЫ РИСК-МЕНЕДЖМЕНТА ПРОЙДЕНЫ ===")
            return True
            
    except Exception as e:
        print(f"✗ Ошибка в тесте риск-менеджмента: {e}")
        return False

if __name__ == "__main__":
    success1 = test_config_validation()
    success2 = test_risk_management_config()
    
    if success1 and success2:
        print("\n🎉 ВСЕ ТЕСТЫ УПРАВЛЕНИЯ КОНФИГУРАЦИЕЙ УСПЕШНО ПРОЙДЕНЫ!")
        sys.exit(0)
    else:
        print("\n❌ НЕКОТОРЫЕ ТЕСТЫ НЕ ПРОЙДЕНЫ")
        sys.exit(1)