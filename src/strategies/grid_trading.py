#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Стратегия сеточной торговли (Grid Trading)

Использует сетку ордеров для торговли в боковом тренде,
размещая ордера на покупку и продажу на разных уровнях цены.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import statistics

from .base_strategy import BaseStrategy, SignalType

class GridTradingStrategy(BaseStrategy):
    """
    Стратегия сеточной торговли
    
    Параметры:
    - grid_size: Количество уровней в сетке (по умолчанию 10)
    - grid_spacing: Расстояние между уровнями сетки в % (по умолчанию 1.0%)
    - base_order_size: Базовый размер ордера
    - martingale_multiplier: Множитель для увеличения размера ордеров
    - take_profit_pct: Процент тейк-профита (по умолчанию 0.5%)
    - max_open_orders: Максимальное количество открытых ордеров
    - rebalance_threshold: Порог для ребалансировки сетки
    - use_dynamic_spacing: Использовать динамическое расстояние на основе волатильности
    """
    
    def __init__(self, name: str, symbol: str, api_client, db_manager, config_manager, **kwargs):
        # Создаем config с символом для BaseStrategy
        config = kwargs.copy()
        config['asset'] = symbol
        super().__init__(name, config, api_client, db_manager, config_manager)
        
        # Параметры стратегии
        self.grid_size = kwargs.get('grid_size', 10)
        self.grid_spacing = kwargs.get('grid_spacing', 1.0)  # %
        self.base_order_size = kwargs.get('base_order_size', 0.01)  # BTC
        self.martingale_multiplier = kwargs.get('martingale_multiplier', 1.2)
        self.take_profit_pct = kwargs.get('take_profit_pct', 0.5)  # %
        self.max_open_orders = kwargs.get('max_open_orders', 20)
        self.rebalance_threshold = kwargs.get('rebalance_threshold', 5.0)  # %
        self.use_dynamic_spacing = kwargs.get('use_dynamic_spacing', True)
        
        # Параметры для динамического расстояния
        self.volatility_period = kwargs.get('volatility_period', 24)
        self.volatility_multiplier = kwargs.get('volatility_multiplier', 2.0)
        
        # Валидация параметров
        if self.grid_size < 3:
            raise ValueError("Размер сетки должен быть не менее 3")
        
        if self.grid_spacing <= 0:
            raise ValueError("Расстояние между уровнями должно быть положительным")
        
        # Состояние сетки
        self.grid_levels: List[Dict[str, Any]] = []
        self.active_orders: Dict[str, Dict[str, Any]] = {}
        self.filled_orders: List[Dict[str, Any]] = []
        self.grid_center_price: Optional[float] = None
        self.last_rebalance_price: Optional[float] = None
        
        # Буферы данных
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.volatility_history: List[float] = []
        
        # Статистика
        self.total_profit = 0.0
        self.completed_cycles = 0
        self.grid_efficiency = 0.0
        
        # Максимальный размер буферов
        self.max_buffer_size = max(self.volatility_period * 2, 200)
        
        self.logger.info(f"Инициализирована стратегия Grid Trading: размер={self.grid_size}, расстояние={self.grid_spacing}%")
    
    def analyze_market(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализ рыночных данных
        
        Args:
            market_data: Рыночные данные
            
        Returns:
            Результат анализа
        """
        try:
            # Извлечение данных о цене
            current_price = market_data.get('price', 0)
            if current_price <= 0:
                return {'status': 'error', 'error': 'Некорректная цена'}
            
            # Извлечение данных о свечах
            klines = market_data.get('klines', {}).get('list', [])
            if not klines:
                return {'status': 'error', 'error': 'Нет данных о свечах'}
            
            # Обновление истории данных
            self._update_market_history(klines)
            
            # Проверка достаточности данных
            if len(self.price_history) < self.volatility_period:
                return {
                    'status': 'insufficient_data',
                    'required': self.volatility_period,
                    'available': len(self.price_history)
                }
            
            # Анализ волатильности
            volatility_analysis = self._analyze_volatility()
            
            # Анализ состояния сетки
            grid_analysis = self._analyze_grid_state(current_price)
            
            # Анализ рыночных условий
            market_conditions = self._analyze_market_conditions()
            
            # Анализ эффективности сетки
            efficiency_analysis = self._analyze_grid_efficiency()
            
            return {
                'status': 'success',
                'current_price': current_price,
                'volatility_analysis': volatility_analysis,
                'grid_analysis': grid_analysis,
                'market_conditions': market_conditions,
                'efficiency_analysis': efficiency_analysis,
                'data_points': len(self.price_history)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа рынка: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def generate_signal(self, analysis: Dict[str, Any]) -> Tuple[SignalType, float]:
        """
        Генерация торгового сигнала
        
        Args:
            analysis: Результат анализа рынка
            
        Returns:
            Кортеж (тип сигнала, уверенность 0-1)
        """
        try:
            if analysis.get('status') != 'success':
                return (SignalType.HOLD, 0.0)
            
            current_price = analysis['current_price']
            volatility_analysis = analysis['volatility_analysis']
            grid_analysis = analysis['grid_analysis']
            market_conditions = analysis['market_conditions']
            efficiency_analysis = analysis['efficiency_analysis']
            
            # Проверка необходимости инициализации сетки
            if not self.grid_levels or grid_analysis['needs_rebalance']:
                self._initialize_grid(current_price, volatility_analysis)
                return (SignalType.HOLD, 0.0)
            
            # Проверка рыночных условий
            if not market_conditions['suitable_for_grid']:
                return (SignalType.HOLD, 0.0)
            
            # Генерация сигналов сетки
            grid_signals = self._generate_grid_signals(current_price, grid_analysis)
            
            if not grid_signals:
                return (SignalType.HOLD, 0.0)
            
            # Выбор лучшего сигнала
            best_signal = self._select_best_grid_signal(grid_signals, efficiency_analysis)
            
            # Расчет силы сигнала
            signal_strength = self._calculate_signal_strength(
                best_signal, volatility_analysis, market_conditions, efficiency_analysis
            )
            
            return (best_signal['signal'], signal_strength)
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации сигнала: {e}")
            return (SignalType.HOLD, 0.0)
    
    def get_strategy_description(self) -> Dict[str, Any]:
        """
        Получение описания стратегии
        
        Returns:
            Описание стратегии
        """
        return {
            'name': self.name,
            'type': 'Grid Trading',
            'description': 'Сеточная торговля с размещением ордеров на разных уровнях цены',
            'parameters': {
                'grid_size': self.grid_size,
                'grid_spacing': self.grid_spacing,
                'base_order_size': self.base_order_size,
                'martingale_multiplier': self.martingale_multiplier,
                'take_profit_pct': self.take_profit_pct,
                'use_dynamic_spacing': self.use_dynamic_spacing
            },
            'risk_level': 'Medium-High',
            'timeframe': '1m-15m',
            'suitable_for': ['Sideways markets', 'Range-bound trading', 'High liquidity assets'],
            'not_suitable_for': ['Strong trending markets', 'Low liquidity assets']
        }
    
    def _update_market_history(self, klines: List[Dict]):
        """
        Обновление истории рыночных данных
        
        Args:
            klines: Данные свечей
        """
        try:
            new_prices = []
            new_volumes = []
            
            for kline in klines:
                if isinstance(kline, list) and len(kline) >= 6:
                    close_price = float(kline[4])  # Закрытие
                    volume = float(kline[5])       # Объем
                    
                    new_prices.append(close_price)
                    new_volumes.append(volume)
            
            # Обновление буферов
            self.price_history.extend(new_prices)
            self.volume_history.extend(new_volumes)
            
            # Ограничение размера буферов
            if len(self.price_history) > self.max_buffer_size:
                self.price_history = self.price_history[-self.max_buffer_size:]
                self.volume_history = self.volume_history[-self.max_buffer_size:]
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления истории данных: {e}")
    
    def _analyze_volatility(self) -> Dict[str, Any]:
        """
        Анализ волатильности для динамического расстояния сетки
        
        Returns:
            Результат анализа волатильности
        """
        try:
            if len(self.price_history) < self.volatility_period:
                return {'volatility': 1.0, 'dynamic_spacing': self.grid_spacing}
            
            # Расчет волатильности (стандартное отклонение доходностей)
            recent_prices = self.price_history[-self.volatility_period:]
            returns = []
            
            for i in range(1, len(recent_prices)):
                return_pct = (recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] * 100
                returns.append(return_pct)
            
            if not returns:
                return {'volatility': 1.0, 'dynamic_spacing': self.grid_spacing}
            
            volatility = statistics.stdev(returns) if len(returns) > 1 else abs(returns[0])
            
            # Динамическое расстояние сетки
            if self.use_dynamic_spacing:
                dynamic_spacing = max(
                    self.grid_spacing * 0.5,  # Минимальное расстояние
                    min(
                        volatility * self.volatility_multiplier,
                        self.grid_spacing * 3.0  # Максимальное расстояние
                    )
                )
            else:
                dynamic_spacing = self.grid_spacing
            
            # Обновление истории волатильности
            self.volatility_history.append(volatility)
            if len(self.volatility_history) > self.max_buffer_size:
                self.volatility_history = self.volatility_history[-self.max_buffer_size:]
            
            # Классификация волатильности
            if volatility < 0.5:
                volatility_level = 'low'
            elif volatility < 2.0:
                volatility_level = 'medium'
            elif volatility < 5.0:
                volatility_level = 'high'
            else:
                volatility_level = 'extreme'
            
            return {
                'volatility': volatility,
                'level': volatility_level,
                'dynamic_spacing': dynamic_spacing,
                'avg_volatility': sum(self.volatility_history[-10:]) / min(len(self.volatility_history), 10)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа волатильности: {e}")
            return {'volatility': 1.0, 'dynamic_spacing': self.grid_spacing}
    
    def _analyze_grid_state(self, current_price: float) -> Dict[str, Any]:
        """
        Анализ текущего состояния сетки
        
        Args:
            current_price: Текущая цена
            
        Returns:
            Результат анализа состояния сетки
        """
        try:
            if not self.grid_levels:
                return {
                    'initialized': False,
                    'needs_rebalance': True,
                    'active_levels': 0,
                    'price_deviation': 0.0
                }
            
            # Проверка отклонения от центра сетки
            price_deviation = 0.0
            needs_rebalance = False
            
            if self.grid_center_price:
                price_deviation = abs(current_price - self.grid_center_price) / self.grid_center_price * 100
                needs_rebalance = price_deviation > self.rebalance_threshold
            
            # Подсчет активных уровней
            active_buy_levels = sum(1 for level in self.grid_levels if level['type'] == 'buy' and level['active'])
            active_sell_levels = sum(1 for level in self.grid_levels if level['type'] == 'sell' and level['active'])
            
            # Ближайшие уровни
            buy_levels_below = [level for level in self.grid_levels 
                              if level['type'] == 'buy' and level['price'] < current_price and level['active']]
            sell_levels_above = [level for level in self.grid_levels 
                               if level['type'] == 'sell' and level['price'] > current_price and level['active']]
            
            # Сортировка по близости к текущей цене
            buy_levels_below.sort(key=lambda x: current_price - x['price'])
            sell_levels_above.sort(key=lambda x: x['price'] - current_price)
            
            return {
                'initialized': True,
                'needs_rebalance': needs_rebalance,
                'price_deviation': price_deviation,
                'active_levels': len([level for level in self.grid_levels if level['active']]),
                'active_buy_levels': active_buy_levels,
                'active_sell_levels': active_sell_levels,
                'nearest_buy_level': buy_levels_below[0] if buy_levels_below else None,
                'nearest_sell_level': sell_levels_above[0] if sell_levels_above else None,
                'grid_center': self.grid_center_price,
                'total_levels': len(self.grid_levels)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа состояния сетки: {e}")
            return {'initialized': False, 'needs_rebalance': True}
    
    def _analyze_market_conditions(self) -> Dict[str, Any]:
        """
        Анализ рыночных условий для определения пригодности сеточной торговли
        
        Returns:
            Результат анализа рыночных условий
        """
        try:
            if len(self.price_history) < 50:
                return {
                    'suitable_for_grid': True,
                    'suitability_score': 0.5,
                    'reason': 'Недостаточно данных для анализа'
                }
            
            recent_prices = self.price_history[-50:]
            
            # Анализ тренда
            trend_strength = self._calculate_trend_strength(recent_prices)
            
            # Анализ диапазона (range)
            price_range = (max(recent_prices) - min(recent_prices)) / min(recent_prices) * 100
            
            # Анализ стабильности
            price_stability = self._calculate_price_stability(recent_prices)
            
            # Оценка пригодности
            suitability_score = 0.0
            reasons = []
            
            # Слабый тренд - хорошо для сетки
            if abs(trend_strength) < 2.0:
                suitability_score += 0.4
                reasons.append(f"Слабый тренд ({trend_strength:.2f}%)")
            elif abs(trend_strength) > 5.0:
                suitability_score -= 0.3
                reasons.append(f"Сильный тренд ({trend_strength:.2f}%)")
            
            # Умеренный диапазон - хорошо для сетки
            if 3.0 <= price_range <= 15.0:
                suitability_score += 0.3
                reasons.append(f"Подходящий диапазон ({price_range:.1f}%)")
            elif price_range < 1.0:
                suitability_score -= 0.2
                reasons.append(f"Слишком узкий диапазон ({price_range:.1f}%)")
            elif price_range > 20.0:
                suitability_score -= 0.2
                reasons.append(f"Слишком широкий диапазон ({price_range:.1f}%)")
            
            # Стабильность цены
            if price_stability > 0.7:
                suitability_score += 0.3
                reasons.append(f"Хорошая стабильность ({price_stability:.2f})")
            elif price_stability < 0.3:
                suitability_score -= 0.2
                reasons.append(f"Низкая стабильность ({price_stability:.2f})")
            
            # Нормализация оценки
            suitability_score = max(0.0, min(1.0, suitability_score + 0.5))
            
            suitable_for_grid = suitability_score >= 0.4
            
            return {
                'suitable_for_grid': suitable_for_grid,
                'suitability_score': suitability_score,
                'trend_strength': trend_strength,
                'price_range': price_range,
                'price_stability': price_stability,
                'reason': '; '.join(reasons) if reasons else 'Анализ завершен'
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа рыночных условий: {e}")
            return {'suitable_for_grid': True, 'suitability_score': 0.5, 'reason': 'Ошибка анализа'}
    
    def _calculate_trend_strength(self, prices: List[float]) -> float:
        """
        Расчет силы тренда
        
        Args:
            prices: Список цен
            
        Returns:
            Сила тренда в процентах
        """
        try:
            if len(prices) < 10:
                return 0.0
            
            # Линейная регрессия для определения тренда
            x = list(range(len(prices)))
            n = len(prices)
            
            sum_x = sum(x)
            sum_y = sum(prices)
            sum_xy = sum(x[i] * prices[i] for i in range(n))
            sum_x2 = sum(xi ** 2 for xi in x)
            
            # Коэффициент наклона
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
            
            # Преобразование в процентное изменение
            trend_strength = (slope * len(prices)) / prices[0] * 100
            
            return trend_strength
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы тренда: {e}")
            return 0.0
    
    def _calculate_price_stability(self, prices: List[float]) -> float:
        """
        Расчет стабильности цены
        
        Args:
            prices: Список цен
            
        Returns:
            Коэффициент стабильности (0-1)
        """
        try:
            if len(prices) < 5:
                return 0.5
            
            # Коэффициент вариации
            mean_price = sum(prices) / len(prices)
            variance = sum((price - mean_price) ** 2 for price in prices) / len(prices)
            std_dev = variance ** 0.5
            
            cv = std_dev / mean_price if mean_price > 0 else 1.0
            
            # Преобразование в коэффициент стабильности (обратная зависимость)
            stability = max(0.0, min(1.0, 1.0 - cv * 10))
            
            return stability
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета стабильности цены: {e}")
            return 0.5
    
    def _analyze_grid_efficiency(self) -> Dict[str, Any]:
        """
        Анализ эффективности сетки
        
        Returns:
            Результат анализа эффективности
        """
        try:
            if not self.filled_orders:
                return {
                    'efficiency': 0.5,
                    'completed_cycles': 0,
                    'total_profit': 0.0,
                    'avg_profit_per_cycle': 0.0,
                    'fill_rate': 0.0
                }
            
            # Расчет коэффициента заполнения
            total_orders = len(self.active_orders) + len(self.filled_orders)
            fill_rate = len(self.filled_orders) / total_orders if total_orders > 0 else 0.0
            
            # Средняя прибыль за цикл
            avg_profit_per_cycle = self.total_profit / max(self.completed_cycles, 1)
            
            # Эффективность на основе различных факторов
            efficiency_factors = []
            
            # Фактор заполнения ордеров
            efficiency_factors.append(min(fill_rate * 2, 1.0))
            
            # Фактор прибыльности
            if avg_profit_per_cycle > 0:
                profit_factor = min(avg_profit_per_cycle / (self.base_order_size * 0.01), 1.0)
                efficiency_factors.append(profit_factor)
            else:
                efficiency_factors.append(0.0)
            
            # Фактор частоты циклов
            if self.completed_cycles > 0:
                cycle_factor = min(self.completed_cycles / 10, 1.0)
                efficiency_factors.append(cycle_factor)
            else:
                efficiency_factors.append(0.0)
            
            # Общая эффективность
            self.grid_efficiency = sum(efficiency_factors) / len(efficiency_factors) if efficiency_factors else 0.5
            
            return {
                'efficiency': self.grid_efficiency,
                'completed_cycles': self.completed_cycles,
                'total_profit': self.total_profit,
                'avg_profit_per_cycle': avg_profit_per_cycle,
                'fill_rate': fill_rate,
                'active_orders': len(self.active_orders),
                'filled_orders': len(self.filled_orders)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа эффективности сетки: {e}")
            return {'efficiency': 0.5, 'completed_cycles': 0, 'total_profit': 0.0}
    
    def _initialize_grid(self, current_price: float, volatility_analysis: Dict[str, Any]):
        """
        Инициализация сетки ордеров
        
        Args:
            current_price: Текущая цена
            volatility_analysis: Анализ волатильности
        """
        try:
            self.grid_levels.clear()
            self.grid_center_price = current_price
            self.last_rebalance_price = current_price
            
            spacing = volatility_analysis['dynamic_spacing']
            
            # Создание уровней покупки (ниже текущей цены)
            buy_levels = self.grid_size // 2
            for i in range(1, buy_levels + 1):
                level_price = current_price * (1 - (spacing * i) / 100)
                order_size = self.base_order_size * (self.martingale_multiplier ** (i - 1))
                
                self.grid_levels.append({
                    'type': 'buy',
                    'level': i,
                    'price': level_price,
                    'order_size': order_size,
                    'active': True,
                    'created_at': datetime.now()
                })
            
            # Создание уровней продажи (выше текущей цены)
            sell_levels = self.grid_size - buy_levels
            for i in range(1, sell_levels + 1):
                level_price = current_price * (1 + (spacing * i) / 100)
                order_size = self.base_order_size * (self.martingale_multiplier ** (i - 1))
                
                self.grid_levels.append({
                    'type': 'sell',
                    'level': i,
                    'price': level_price,
                    'order_size': order_size,
                    'active': True,
                    'created_at': datetime.now()
                })
            
            self.logger.info(f"Инициализирована сетка: {len(self.grid_levels)} уровней, центр: {current_price:.2f}, расстояние: {spacing:.2f}%")
            
        except Exception as e:
            self.logger.error(f"Ошибка инициализации сетки: {e}")
    
    def _generate_grid_signals(self, current_price: float, grid_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Генерация сигналов на основе уровней сетки
        
        Args:
            current_price: Текущая цена
            grid_analysis: Анализ состояния сетки
            
        Returns:
            Список сигналов сетки
        """
        try:
            signals = []
            
            # Проверка ближайших уровней
            nearest_buy = grid_analysis.get('nearest_buy_level')
            nearest_sell = grid_analysis.get('nearest_sell_level')
            
            # Сигнал покупки при достижении уровня покупки
            if nearest_buy and current_price <= nearest_buy['price'] * 1.001:  # 0.1% толерантность
                signals.append({
                    'signal': SignalType.BUY,
                    'level': nearest_buy['level'],
                    'target_price': nearest_buy['price'],
                    'order_size': nearest_buy['order_size'],
                    'take_profit_price': nearest_buy['price'] * (1 + self.take_profit_pct / 100),
                    'reason': f"Достижение уровня покупки #{nearest_buy['level']} ({nearest_buy['price']:.2f})",
                    'priority': self._calculate_level_priority(nearest_buy, current_price)
                })
            
            # Сигнал продажи при достижении уровня продажи
            if nearest_sell and current_price >= nearest_sell['price'] * 0.999:  # 0.1% толерантность
                signals.append({
                    'signal': SignalType.SELL,
                    'level': nearest_sell['level'],
                    'target_price': nearest_sell['price'],
                    'order_size': nearest_sell['order_size'],
                    'take_profit_price': nearest_sell['price'] * (1 - self.take_profit_pct / 100),
                    'reason': f"Достижение уровня продажи #{nearest_sell['level']} ({nearest_sell['price']:.2f})",
                    'priority': self._calculate_level_priority(nearest_sell, current_price)
                })
            
            return signals
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации сигналов сетки: {e}")
            return []
    
    def _calculate_level_priority(self, level: Dict[str, Any], current_price: float) -> float:
        """
        Расчет приоритета уровня сетки
        
        Args:
            level: Уровень сетки
            current_price: Текущая цена
            
        Returns:
            Приоритет уровня (0.0 - 1.0)
        """
        try:
            # Базовый приоритет
            base_priority = 0.5
            
            # Близость к цене (чем ближе, тем выше приоритет)
            price_distance = abs(current_price - level['price']) / current_price
            proximity_bonus = max(0, 0.3 - price_distance * 10)
            
            # Размер ордера (большие ордера имеют меньший приоритет для управления риском)
            size_penalty = min(level['order_size'] / self.base_order_size * 0.1, 0.2)
            
            # Время создания уровня (старые уровни имеют выше приоритет)
            age_bonus = min((datetime.now() - level['created_at']).total_seconds() / 3600 * 0.1, 0.2)
            
            priority = base_priority + proximity_bonus - size_penalty + age_bonus
            return max(0.0, min(1.0, priority))
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета приоритета уровня: {e}")
            return 0.5
    
    def _select_best_grid_signal(self, signals: List[Dict[str, Any]], efficiency_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выбор лучшего сигнала из доступных
        
        Args:
            signals: Список сигналов
            efficiency_analysis: Анализ эффективности
            
        Returns:
            Лучший сигнал
        """
        try:
            if not signals:
                return {
                    'signal': SignalType.HOLD,
                    'reason': 'Нет доступных сигналов'
                }
            
            # Сортировка по приоритету
            signals.sort(key=lambda x: x.get('priority', 0), reverse=True)
            
            # Проверка лимита открытых ордеров
            if len(self.active_orders) >= self.max_open_orders:
                return {
                    'signal': SignalType.HOLD,
                    'reason': f'Достигнут лимит открытых ордеров ({self.max_open_orders})'
                }
            
            # Выбор сигнала с учетом эффективности
            best_signal = signals[0]
            
            # Корректировка размера ордера на основе эффективности
            efficiency = efficiency_analysis['efficiency']
            if efficiency < 0.3:
                best_signal['order_size'] *= 0.5  # Уменьшение размера при низкой эффективности
            elif efficiency > 0.8:
                best_signal['order_size'] *= 1.2  # Увеличение размера при высокой эффективности
            
            return best_signal
            
        except Exception as e:
            self.logger.error(f"Ошибка выбора лучшего сигнала: {e}")
            return {'signal': SignalType.HOLD, 'reason': 'Ошибка выбора сигнала'}
    
    def _calculate_signal_strength(self, signal_data: Dict[str, Any], volatility_analysis: Dict[str, Any],
                                 market_conditions: Dict[str, Any], efficiency_analysis: Dict[str, Any]) -> float:
        """
        Расчет силы сигнала
        
        Args:
            signal_data: Данные сигнала
            volatility_analysis: Анализ волатильности
            market_conditions: Рыночные условия
            efficiency_analysis: Анализ эффективности
            
        Returns:
            Сила сигнала (0.0 - 1.0)
        """
        try:
            base_strength = 0.4  # Базовая сила для сеточной торговли
            
            # Бонус за приоритет уровня
            priority_bonus = signal_data.get('priority', 0.5) * 0.2
            base_strength += priority_bonus
            
            # Корректировка на волатильность
            volatility_level = volatility_analysis['level']
            if volatility_level == 'medium':
                volatility_bonus = 0.2
            elif volatility_level == 'low':
                volatility_bonus = 0.1
            else:
                volatility_bonus = -0.1  # Штраф за высокую волатильность
            
            base_strength += volatility_bonus
            
            # Корректировка на рыночные условия
            market_bonus = market_conditions['suitability_score'] * 0.2
            base_strength += market_bonus
            
            # Корректировка на эффективность сетки
            efficiency_bonus = efficiency_analysis['efficiency'] * 0.2
            base_strength += efficiency_bonus
            
            return min(base_strength, 1.0)
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы сигнала: {e}")
            return 0.0