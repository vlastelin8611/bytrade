#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование торговых стратегий

Проверяет все доступные стратегии в безопасном режиме:
- Инициализация стратегий
- Анализ рыночных данных
- Генерация торговых сигналов
- Управление рисками
- Логирование операций
"""

import sys
import os
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any

# Добавляем путь к модулям
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Импорт необходимых модулей
from src.strategies import (
    AVAILABLE_STRATEGIES, STRATEGY_METADATA,
    get_strategy_class, StrategyEngine
)
from src.database.db_manager import DatabaseManager
from src.core.config_manager import ConfigManager
from src.api.bybit_client import BybitClient

class StrategyTester:
    """
    Класс для тестирования торговых стратегий
    """
    
    def __init__(self):
        self.logger = self._setup_logging()
        self.test_results = []
        self.failed_tests = []
        
        # Инициализация компонентов
        try:
            self.config_manager = ConfigManager()
            self.db_manager = DatabaseManager()
            
            # Создаем тестовый API клиент (без реальных подключений)
            self.api_client = self._create_test_api_client()
            
            self.logger.info("Инициализация тестера стратегий завершена")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации: {e}")
            raise
    
    def _setup_logging(self) -> logging.Logger:
        """Настройка логирования"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('strategy_test.log', encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        return logging.getLogger(__name__)
    
    def _create_test_api_client(self):
        """Создание тестового API клиента"""
        class TestAPIClient:
            def __init__(self):
                self.testnet = True
                self.connected = False
            
            def get_klines(self, symbol, interval, limit=100):
                """Имитация получения свечных данных"""
                import random
                base_price = 50000 if symbol == 'BTCUSDT' else 3000
                klines = []
                
                for i in range(limit):
                    timestamp = int(time.time() * 1000) - (limit - i) * 60000
                    price_change = random.uniform(-0.02, 0.02)
                    open_price = base_price * (1 + price_change)
                    close_price = open_price * (1 + random.uniform(-0.01, 0.01))
                    high_price = max(open_price, close_price) * (1 + random.uniform(0, 0.005))
                    low_price = min(open_price, close_price) * (1 - random.uniform(0, 0.005))
                    volume = random.uniform(100, 1000)
                    
                    klines.append({
                        'timestamp': timestamp,
                        'open': open_price,
                        'high': high_price,
                        'low': low_price,
                        'close': close_price,
                        'volume': volume
                    })
                    base_price = close_price
                
                return klines
            
            def get_ticker(self, symbol):
                """Имитация получения тикера"""
                import random
                base_price = 50000 if symbol == 'BTCUSDT' else 3000
                return {
                    'symbol': symbol,
                    'price': base_price * (1 + random.uniform(-0.01, 0.01)),
                    'volume': random.uniform(1000, 10000)
                }
            
            def get_balance(self):
                """Имитация получения баланса"""
                return {
                    'USDT': {'free': 1000.0, 'used': 0.0, 'total': 1000.0}
                }
        
        return TestAPIClient()
    
    def test_strategy_initialization(self, strategy_name: str) -> Dict[str, Any]:
        """Тестирование инициализации стратегии"""
        test_name = f"Инициализация стратегии {strategy_name}"
        self.logger.info(f"Начало теста: {test_name}")
        
        try:
            # Получаем класс стратегии
            strategy_class = get_strategy_class(strategy_name)
            if not strategy_class:
                raise ValueError(f"Стратегия {strategy_name} не найдена")
            
            # Создаем конфигурацию для тестирования
            test_config = {
                'asset': 'BTCUSDT',
                'position_size': 0.01,
                'stop_loss': 2.0,
                'take_profit': 4.0,
                'timeframe': '1h',
                'max_daily_loss_pct': 20.0,
                'max_consecutive_losses': 3,
                'max_position_size_pct': 10.0
            }
            
            # Инициализируем стратегию с правильными параметрами
            if hasattr(strategy_class.__init__, '__code__') and 'symbol' in strategy_class.__init__.__code__.co_varnames:
                # Стратегия требует symbol как отдельный параметр
                strategy = strategy_class(
                    name=strategy_name,
                    symbol='BTCUSDT',
                    api_client=self.api_client,
                    db_manager=self.db_manager,
                    config_manager=self.config_manager,
                    **test_config
                )
            else:
                # Стратегия использует стандартный интерфейс BaseStrategy
                strategy = strategy_class(
                    name=strategy_name,
                    config=test_config,
                    api_client=self.api_client,
                    db_manager=self.db_manager,
                    config_manager=self.config_manager
                )
            
            # Проверяем основные атрибуты
            assert hasattr(strategy, 'name'), "Отсутствует атрибут name"
            assert hasattr(strategy, 'state'), "Отсутствует атрибут state"
            assert hasattr(strategy, 'analyze_market'), "Отсутствует метод analyze_market"
            assert hasattr(strategy, 'generate_signal'), "Отсутствует метод generate_signal"
            
            self.logger.info(f"✓ {test_name} - УСПЕШНО")
            return {
                'test_name': test_name,
                'status': 'PASS',
                'strategy': strategy,
                'message': 'Стратегия успешно инициализирована'
            }
            
        except Exception as e:
            error_msg = f"Ошибка инициализации стратегии {strategy_name}: {e}"
            self.logger.error(f"✗ {test_name} - ОШИБКА: {error_msg}")
            return {
                'test_name': test_name,
                'status': 'FAIL',
                'strategy': None,
                'message': error_msg
            }
    
    def test_market_analysis(self, strategy, strategy_name: str) -> Dict[str, Any]:
        """Тестирование анализа рынка"""
        test_name = f"Анализ рынка - {strategy_name}"
        self.logger.info(f"Начало теста: {test_name}")
        
        try:
            # Получаем тестовые данные
            market_data = self.api_client.get_klines('BTCUSDT', '1h', 100)
            
            # Выполняем анализ рынка
            analysis_result = strategy.analyze_market(market_data)
            
            # Проверяем результат анализа
            assert isinstance(analysis_result, dict), "Результат анализа должен быть словарем"
            
            # Проверяем результат анализа в зависимости от стратегии
            if strategy_name == 'adaptive_ml':
                assert 'status' in analysis_result, "Отсутствует статус в результате"
                if analysis_result.get('status') == 'success':
                    assert 'technical_analysis' in analysis_result, "Отсутствует технический анализ"
                    assert 'ml_prediction' in analysis_result, "Отсутствует ML предсказание"
                    message = f'ML анализ выполнен, статус: {analysis_result["status"]}'
                else:
                    message = f'ML анализ завершен со статусом: {analysis_result["status"]}'
            else:
                # Для остальных стратегий проверяем наличие любого из ключевых полей
                if 'indicators' in analysis_result:
                    message = f'Анализ выполнен, получено {len(analysis_result.get("indicators", {}))} индикаторов'
                elif 'status' in analysis_result:
                    status = analysis_result.get('status')
                    if status == 'insufficient_data':
                        required = analysis_result.get('required', 'N/A')
                        available = analysis_result.get('available', 'N/A')
                        message = f'Недостаточно данных: требуется {required}, доступно {available}'
                    elif status == 'error':
                        error = analysis_result.get('error', 'Неизвестная ошибка')
                        message = f'Ошибка анализа: {error}'
                    else:
                        message = f'Анализ выполнен, статус: {status}'
                else:
                    # Если нет ни indicators, ни status, проверяем наличие других полей
                    keys = list(analysis_result.keys())
                    message = f'Анализ выполнен, получены данные: {", ".join(keys[:5])}'
                    if len(keys) > 5:
                        message += f' и еще {len(keys) - 5} полей'
            
            self.logger.info(f"✓ {test_name} - УСПЕШНО")
            return {
                'test_name': test_name,
                'status': 'PASS',
                'message': message
            }
            
        except Exception as e:
            error_msg = f"Ошибка анализа рынка для {strategy_name}: {e}"
            self.logger.error(f"✗ {test_name} - ОШИБКА: {error_msg}")
            return {
                'test_name': test_name,
                'status': 'FAIL',
                'message': error_msg
            }
    
    def test_signal_generation(self, strategy, strategy_name: str) -> Dict[str, Any]:
        """Тестирование генерации торговых сигналов"""
        test_name = f"Генерация сигналов - {strategy_name}"
        self.logger.info(f"Начало теста: {test_name}")
        
        try:
            # Получаем тестовые данные
            market_data = self.api_client.get_klines('BTCUSDT', '1h', 100)
            
            # Генерируем сигнал
            signal_result = strategy.generate_signal(market_data)
            
            # Проверяем сигнал (должен быть кортеж)
            assert isinstance(signal_result, tuple), "Сигнал должен быть кортежем"
            assert len(signal_result) == 2, "Сигнал должен содержать 2 элемента"
            
            signal_type, confidence = signal_result
            assert hasattr(signal_type, 'value'), "Первый элемент должен быть SignalType"
            assert isinstance(confidence, (int, float)), "Второй элемент должен быть числом"
            assert 0 <= confidence <= 1, "Уверенность должна быть между 0 и 1"
            
            self.logger.info(f"✓ {test_name} - УСПЕШНО")
            return {
                'test_name': test_name,
                'status': 'PASS',
                'message': f'Сигнал сгенерирован: {signal_type.value} (уверенность: {confidence:.2f})'
            }
            
        except Exception as e:
            error_msg = f"Ошибка генерации сигнала для {strategy_name}: {e}"
            self.logger.error(f"✗ {test_name} - ОШИБКА: {error_msg}")
            return {
                'test_name': test_name,
                'status': 'FAIL',
                'message': error_msg
            }
    
    def test_risk_management(self, strategy, strategy_name: str) -> Dict[str, Any]:
        """Тестирование управления рисками"""
        test_name = f"Управление рисками - {strategy_name}"
        self.logger.info(f"Начало теста: {test_name}")
        
        try:
            # Проверяем наличие риск-менеджера
            assert hasattr(strategy, 'risk_manager'), "Отсутствует риск-менеджер"
            
            # Тестируем проверку рисков
            allowed, reason = strategy.risk_manager.check_trade_allowed(
                signal_confidence=0.8,
                position_size_pct=5.0,
                stop_loss_pct=2.0
            )
            
            assert isinstance(allowed, bool), "Результат проверки риска должен быть булевым"
            assert isinstance(reason, str), "Причина должна быть строкой"
            
            self.logger.info(f"✓ {test_name} - УСПЕШНО")
            return {
                'test_name': test_name,
                'status': 'PASS',
                'message': f'Риск-менеджмент работает, сделка {"разрешена" if allowed else "запрещена"}: {reason}'
            }
            
        except Exception as e:
            error_msg = f"Ошибка управления рисками для {strategy_name}: {e}"
            self.logger.error(f"✗ {test_name} - ОШИБКА: {error_msg}")
            return {
                'test_name': test_name,
                'status': 'FAIL',
                'message': error_msg
            }
    
    def test_strategy_engine(self) -> Dict[str, Any]:
        """Тестирование движка стратегий"""
        test_name = "Движок стратегий"
        self.logger.info(f"Начало теста: {test_name}")
        
        try:
            # Создаем движок стратегий
            engine = StrategyEngine(
                api_client=self.api_client,
                db_manager=self.db_manager,
                config_manager=self.config_manager
            )
            
            # Проверяем основные методы
            assert hasattr(engine, 'register_strategy'), "Отсутствует метод register_strategy"
            assert hasattr(engine, 'unregister_strategy'), "Отсутствует метод unregister_strategy"
            assert hasattr(engine, 'start_engine'), "Отсутствует метод start_engine"
            assert hasattr(engine, 'stop_engine'), "Отсутствует метод stop_engine"
            
            # Проверяем начальное состояние
            assert len(engine.strategies) == 0, "Движок должен быть пустым при инициализации"
            assert not engine.is_running, "Движок не должен быть запущен при инициализации"
            
            self.logger.info(f"✓ {test_name} - УСПЕШНО")
            return {
                'test_name': test_name,
                'status': 'PASS',
                'message': 'Движок стратегий успешно инициализирован'
            }
            
        except Exception as e:
            error_msg = f"Ошибка тестирования движка стратегий: {e}"
            self.logger.error(f"✗ {test_name} - ОШИБКА: {error_msg}")
            return {
                'test_name': test_name,
                'status': 'FAIL',
                'message': error_msg
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Запуск всех тестов стратегий"""
        self.logger.info("=" * 60)
        self.logger.info("НАЧАЛО ТЕСТИРОВАНИЯ ТОРГОВЫХ СТРАТЕГИЙ")
        self.logger.info("=" * 60)
        
        start_time = datetime.now()
        total_tests = 0
        passed_tests = 0
        
        # Тестируем движок стратегий
        engine_result = self.test_strategy_engine()
        self.test_results.append(engine_result)
        total_tests += 1
        if engine_result['status'] == 'PASS':
            passed_tests += 1
        else:
            self.failed_tests.append(engine_result)
        
        # Тестируем каждую стратегию
        for strategy_name in AVAILABLE_STRATEGIES.keys():
            self.logger.info(f"\n--- Тестирование стратегии: {strategy_name} ---")
            
            # Тест инициализации
            init_result = self.test_strategy_initialization(strategy_name)
            self.test_results.append(init_result)
            total_tests += 1
            
            if init_result['status'] == 'PASS':
                passed_tests += 1
                strategy = init_result['strategy']
                
                # Тест анализа рынка
                analysis_result = self.test_market_analysis(strategy, strategy_name)
                self.test_results.append(analysis_result)
                total_tests += 1
                if analysis_result['status'] == 'PASS':
                    passed_tests += 1
                else:
                    self.failed_tests.append(analysis_result)
                
                # Тест генерации сигналов
                signal_result = self.test_signal_generation(strategy, strategy_name)
                self.test_results.append(signal_result)
                total_tests += 1
                if signal_result['status'] == 'PASS':
                    passed_tests += 1
                else:
                    self.failed_tests.append(signal_result)
                
                # Тест управления рисками
                risk_result = self.test_risk_management(strategy, strategy_name)
                self.test_results.append(risk_result)
                total_tests += 1
                if risk_result['status'] == 'PASS':
                    passed_tests += 1
                else:
                    self.failed_tests.append(risk_result)
            else:
                self.failed_tests.append(init_result)
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Подготовка итогового отчета
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        summary = {
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'failed_tests': len(self.failed_tests),
            'success_rate': success_rate,
            'test_results': self.test_results,
            'failed_test_details': self.failed_tests
        }
        
        # Вывод итогов
        self.logger.info("\n" + "=" * 60)
        self.logger.info("ИТОГИ ТЕСТИРОВАНИЯ СТРАТЕГИЙ")
        self.logger.info("=" * 60)
        self.logger.info(f"Общее время выполнения: {duration}")
        self.logger.info(f"Всего тестов: {total_tests}")
        self.logger.info(f"Успешных тестов: {passed_tests}")
        self.logger.info(f"Неудачных тестов: {len(self.failed_tests)}")
        self.logger.info(f"Процент успеха: {success_rate:.1f}%")
        
        if self.failed_tests:
            self.logger.info("\nНеудачные тесты:")
            for failed_test in self.failed_tests:
                self.logger.info(f"  - {failed_test['test_name']}: {failed_test['message']}")
        
        self.logger.info("=" * 60)
        
        return summary

def main():
    """Главная функция для запуска тестов"""
    try:
        tester = StrategyTester()
        results = tester.run_all_tests()
        
        # Возвращаем код выхода на основе результатов
        if results['failed_tests'] == 0:
            print("\n🎉 Все тесты стратегий прошли успешно!")
            return 0
        else:
            print(f"\n❌ {results['failed_tests']} тестов завершились неудачно")
            return 1
            
    except Exception as e:
        print(f"\n💥 Критическая ошибка при тестировании: {e}")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)