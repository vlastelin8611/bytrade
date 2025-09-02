#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест системы риск-менеджмента
Проверяет соответствие требованиям:
- Не более 20% баланса в день
- Стоп после 3 неудач подряд
- Стоп-лоссы до 40%
"""

import sys
import os
import traceback
import time
from datetime import datetime, timedelta
from typing import Dict, Any

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_risk_manager_creation():
    """Тест создания менеджера рисков"""
    print("\n=== Тест создания менеджера рисков ===")
    
    try:
        from src.core.risk_manager import RiskManager, RiskLevel, RiskMetrics
        
        # Создаем конфигурацию согласно требованиям
        risk_config = {
            'max_daily_loss_pct': 20.0,  # 20% от баланса в день
            'max_consecutive_losses': 3,  # Стоп после 3 неудач
            'max_stop_loss_pct': 40.0,    # Максимальный стоп-лосс 40%
            'max_position_size_pct': 10.0,
            'max_trades_per_day': 10,
            'max_drawdown_pct': 50.0,  # Увеличиваем лимит просадки для тестов
            'min_confidence_threshold': 0.7
        }
        
        print("Создание риск-менеджера...")
        risk_manager = RiskManager(risk_config)
        
        # Проверяем основные параметры
        if risk_manager.max_daily_loss_pct == 20.0:
            print("✓ Лимит дневных потерь: 20%")
        else:
            print(f"✗ Неверный лимит дневных потерь: {risk_manager.max_daily_loss_pct}%")
            return False
            
        if risk_manager.max_consecutive_losses == 3:
            print("✓ Лимит последовательных потерь: 3")
        else:
            print(f"✗ Неверный лимит последовательных потерь: {risk_manager.max_consecutive_losses}")
            return False
            
        if risk_manager.max_stop_loss_pct == 40.0:
            print("✓ Максимальный стоп-лосс: 40%")
        else:
            print(f"✗ Неверный максимальный стоп-лосс: {risk_manager.max_stop_loss_pct}%")
            return False
            
        print("✓ Риск-менеджер создан успешно")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка создания риск-менеджера: {str(e)}")
        traceback.print_exc()
        return False

def test_daily_loss_limit():
    """Тест лимита дневных потерь (20% баланса)"""
    print("\n=== Тест лимита дневных потерь ===")
    
    try:
        from src.core.risk_manager import RiskManager
        
        risk_config = {
            'max_daily_loss_pct': 20.0,
            'max_consecutive_losses': 3,
            'max_stop_loss_pct': 40.0,
            'max_drawdown_pct': 50.0  # Увеличиваем лимит просадки для тестирования
        }
        
        risk_manager = RiskManager(risk_config)
        
        # Симулируем баланс 1000 USDT
        balance = 1000.0
        
        # Тест 1: Позиция в пределах лимита (10% от баланса)
        position_size_pct = 10.0
        stop_loss_pct = 5.0
        signal_confidence = 0.8
        
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=signal_confidence,
            position_size_pct=position_size_pct,
            stop_loss_pct=stop_loss_pct
        )
        
        if can_trade:
            print("✓ Позиция 10% от баланса разрешена")
        else:
            print(f"✗ Позиция 10% от баланса отклонена: {reason}")
            return False
            
        # Тест 2: Симулируем потери 15% (в пределах лимита)
        risk_manager.record_trade({
            'symbol': "BTCUSDT",
            'pnl': -150.0,
            'pnl_pct': -15.0,
            'is_win': False,
            'timestamp': datetime.utcnow(),
            'strategy_name': "test"
        })
        
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=0.8,
            position_size_pct=5.0,
            stop_loss_pct=5.0
        )
        
        if can_trade:
            print("✓ Торговля разрешена при потерях 15%")
        else:
            print(f"✗ Торговля заблокирована при потерях 15%: {reason}")
            return False
            
        # Тест 3: Симулируем потери 25% (превышение лимита)
        # Добавляем еще одну убыточную сделку для достижения лимита
        risk_manager.record_trade({
            'symbol': "BTCUSDT",
            'pnl': -100.0,
            'pnl_pct': -10.0,  # Итого будет -15% + -10% = -25%
            'is_win': False,
            'timestamp': datetime.utcnow(),
            'strategy_name': "test"
        })
        
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=0.8,
            position_size_pct=5.0,
            stop_loss_pct=5.0
        )
        
        if not can_trade and "дневных потерь" in reason:
            print("✓ Торговля заблокирована при превышении лимита 20%")
        else:
            print(f"✗ Торговля не заблокирована при превышении лимита: {reason}")
            return False
            
        print("✓ Тест лимита дневных потерь пройден")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка теста дневных потерь: {str(e)}")
        traceback.print_exc()
        return False

def test_consecutive_losses_limit():
    """Тест лимита последовательных потерь (3 неудачи)"""
    print("\n=== Тест лимита последовательных потерь ===")
    
    try:
        from src.core.risk_manager import RiskManager
        
        risk_config = {
            'max_daily_loss_pct': 20.0,
            'max_consecutive_losses': 3,
            'max_stop_loss_pct': 40.0
        }
        
        risk_manager = RiskManager(risk_config)
        
        # Тест 1: Первая потеря
        risk_manager.record_trade({
            'symbol': "BTCUSDT",
            'pnl': -50.0,
            'pnl_pct': -5.0,
            'is_win': False,
            'timestamp': datetime.utcnow(),
            'strategy_name': "test"
        })
        
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=0.8,
            position_size_pct=5.0,
            stop_loss_pct=5.0
        )
        
        if can_trade:
            print("✓ Торговля разрешена после 1 потери")
        else:
            print(f"✗ Торговля заблокирована после 1 потери: {reason}")
            return False
            
        # Тест 2: Вторая потеря
        risk_manager.record_trade({
            'symbol': "BTCUSDT",
            'pnl': -30.0,
            'pnl_pct': -3.0,
            'is_win': False,
            'timestamp': datetime.utcnow(),
            'strategy_name': "test"
        })
        
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=0.8,
            position_size_pct=5.0,
            stop_loss_pct=5.0
        )
        
        if can_trade:
            print("✓ Торговля разрешена после 2 потерь")
        else:
            print(f"✗ Торговля заблокирована после 2 потерь: {reason}")
            return False
            
        # Тест 3: Третья потеря (должна заблокировать)
        risk_manager.record_trade({
            'symbol': "BTCUSDT",
            'pnl': -40.0,
            'pnl_pct': -4.0,
            'is_win': False,
            'timestamp': datetime.utcnow(),
            'strategy_name': "test"
        })
        
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=0.8,
            position_size_pct=5.0,
            stop_loss_pct=5.0
        )
        
        if not can_trade and "последовательных потерь" in reason:
            print("✓ Торговля заблокирована после 3 последовательных потерь")
        else:
            print(f"✗ Торговля не заблокирована после 3 потерь: {reason}")
            return False
            
        print("✓ Тест лимита последовательных потерь пройден")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка теста последовательных потерь: {str(e)}")
        traceback.print_exc()
        return False

def test_stop_loss_limit():
    """Тест лимита стоп-лосса (максимум 40%)"""
    print("\n=== Тест лимита стоп-лосса ===")
    
    try:
        from src.core.risk_manager import RiskManager
        
        risk_config = {
            'max_daily_loss_pct': 20.0,
            'max_consecutive_losses': 3,
            'max_stop_loss_pct': 40.0
        }
        
        risk_manager = RiskManager(risk_config)
        
        # Тест 1: Стоп-лосс 30% (в пределах лимита)
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=0.8,
            position_size_pct=5.0,
            stop_loss_pct=30.0
        )
        
        if can_trade:
            print("✓ Стоп-лосс 30% разрешен")
        else:
            print(f"✗ Стоп-лосс 30% отклонен: {reason}")
            return False
            
        # Тест 2: Стоп-лосс 40% (на границе лимита)
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=0.8,
            position_size_pct=5.0,
            stop_loss_pct=40.0
        )
        
        if can_trade:
            print("✓ Стоп-лосс 40% разрешен")
        else:
            print(f"✗ Стоп-лосс 40% отклонен: {reason}")
            return False
            
        # Тест 3: Стоп-лосс 45% (превышение лимита)
        can_trade, reason = risk_manager.check_trade_allowed(
            signal_confidence=0.8,
            position_size_pct=5.0,
            stop_loss_pct=45.0
        )
        
        if not can_trade and "стоп-лосс" in reason.lower():
            print("✓ Стоп-лосс 45% отклонен")
        else:
            print(f"✗ Стоп-лосс 45% не отклонен: {reason}")
            return False
            
        print("✓ Тест лимита стоп-лосса пройден")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка теста стоп-лосса: {str(e)}")
        traceback.print_exc()
        return False

def test_risk_assessment():
    """Тест оценки рисков"""
    print("\n=== Тест оценки рисков ===")
    
    try:
        from src.core.risk_manager import RiskManager, RiskLevel
        
        risk_config = {
            'max_daily_loss_pct': 20.0,
            'max_consecutive_losses': 3,
            'max_stop_loss_pct': 40.0
        }
        
        risk_manager = RiskManager(risk_config)
        
        # Получаем начальную оценку рисков
        assessment = risk_manager.get_risk_assessment()
        
        if isinstance(assessment, dict):
            print("✓ Оценка рисков возвращается как словарь")
        else:
            print("✗ Оценка рисков не является словарем")
            return False
            
        required_keys = [
            'risk_level', 'is_blocked', 'daily_loss_pct',
            'consecutive_losses', 'remaining_daily_risk'
        ]
        
        for key in required_keys:
            if key in assessment:
                print(f"✓ Ключ '{key}' присутствует")
            else:
                print(f"✗ Ключ '{key}' отсутствует")
                return False
                
        # Проверяем начальный уровень риска
        if assessment['risk_level'] == 'low':
            print("✓ Начальный уровень риска: LOW")
        else:
            print(f"✗ Неожиданный начальный уровень риска: {assessment['risk_level']}")
            return False
            
        print("✓ Тест оценки рисков пройден")
        return True
        
    except Exception as e:
        print(f"✗ Ошибка теста оценки рисков: {str(e)}")
        traceback.print_exc()
        return False

def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ СИСТЕМЫ РИСК-МЕНЕДЖМЕНТА")
    print("=" * 60)
    
    start_time = time.time()
    
    tests = [
        ("Создание риск-менеджера", test_risk_manager_creation),
        ("Лимит дневных потерь (20%)", test_daily_loss_limit),
        ("Лимит последовательных потерь (3)", test_consecutive_losses_limit),
        ("Лимит стоп-лосса (40%)", test_stop_loss_limit),
        ("Оценка рисков", test_risk_assessment)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n--- {test_name} ---")
        try:
            result = test_func()
            results.append((test_name, "PASS" if result else "FAIL"))
            if result:
                print(f"✓ {test_name}: ПРОЙДЕН")
            else:
                print(f"✗ {test_name}: ПРОВАЛЕН")
        except Exception as e:
            print(f"✗ {test_name}: ОШИБКА - {str(e)}")
            results.append((test_name, "ERROR"))
    
    # Итоговые результаты
    print("\n" + "=" * 60)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("=" * 60)
    
    passed = sum(1 for _, status in results if status == "PASS")
    total = len(results)
    
    for test_name, status in results:
        status_symbol = "✓" if status == "PASS" else "✗"
        print(f"{status_symbol} {test_name:<40} {status}")
    
    print(f"\nВсего тестов: {total}")
    print(f"Пройдено: {passed}")
    print(f"Провалено: {total - passed}")
    print(f"Успешность: {(passed/total)*100:.1f}%")
    print(f"Время выполнения: {time.time() - start_time:.2f}s")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)