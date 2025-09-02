#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Стратегия торговли на основе скользящих средних

Использует пересечения быстрой и медленной скользящих средних
для генерации торговых сигналов.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .base_strategy import BaseStrategy, SignalType

class MovingAveragesStrategy(BaseStrategy):
    """
    Стратегия торговли на скользящих средних
    
    Параметры:
    - fast_period: Период быстрой MA (по умолчанию 10)
    - slow_period: Период медленной MA (по умолчанию 30)
    - ma_type: Тип скользящей средней ('sma', 'ema', 'wma')
    - min_price_change: Минимальное изменение цены для сигнала (%)
    - volume_filter: Использовать фильтр по объему
    - min_volume_ratio: Минимальное отношение текущего объема к среднему
    """
    
    def __init__(self, name: str, symbol: str, api_client, db_manager, config_manager, **kwargs):
        # Создаем config с символом для BaseStrategy
        config = kwargs.copy()
        config['asset'] = symbol
        super().__init__(name, config, api_client, db_manager, config_manager)
        
        # Параметры стратегии
        self.fast_period = kwargs.get('fast_period', 10)
        self.slow_period = kwargs.get('slow_period', 30)
        self.ma_type = kwargs.get('ma_type', 'sma').lower()
        self.min_price_change = kwargs.get('min_price_change', 0.1)  # %
        self.volume_filter = kwargs.get('volume_filter', True)
        self.min_volume_ratio = kwargs.get('min_volume_ratio', 1.2)
        
        # Валидация параметров
        if self.fast_period >= self.slow_period:
            raise ValueError("Период быстрой MA должен быть меньше периода медленной MA")
        
        if self.ma_type not in ['sma', 'ema', 'wma']:
            raise ValueError("Тип MA должен быть 'sma', 'ema' или 'wma'")
        
        # Буферы данных
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.fast_ma_history: List[float] = []
        self.slow_ma_history: List[float] = []
        
        # Состояние стратегии
        self.last_signal = None
        self.last_cross_direction = None  # 'up' или 'down'
        self.signal_strength = 0.0
        
        # Максимальный размер буферов
        self.max_buffer_size = max(self.slow_period * 2, 200)
        
        self.logger.info(f"Инициализирована стратегия MA: fast={self.fast_period}, slow={self.slow_period}, type={self.ma_type}")
    
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
            
            # Обновление истории цен
            self._update_price_history(klines)
            
            # Проверка достаточности данных
            if len(self.price_history) < self.slow_period:
                return {
                    'status': 'insufficient_data',
                    'required': self.slow_period,
                    'available': len(self.price_history)
                }
            
            # Расчет скользящих средних
            fast_ma = self._calculate_ma(self.price_history, self.fast_period, self.ma_type)
            slow_ma = self._calculate_ma(self.price_history, self.slow_period, self.ma_type)
            
            if fast_ma is None or slow_ma is None:
                return {'status': 'error', 'error': 'Ошибка расчета MA'}
            
            # Обновление истории MA
            self.fast_ma_history.append(fast_ma)
            self.slow_ma_history.append(slow_ma)
            
            # Ограничение размера буферов
            if len(self.fast_ma_history) > self.max_buffer_size:
                self.fast_ma_history = self.fast_ma_history[-self.max_buffer_size:]
                self.slow_ma_history = self.slow_ma_history[-self.max_buffer_size:]
            
            # Анализ пересечений
            cross_analysis = self._analyze_crossover()
            
            # Анализ тренда
            trend_analysis = self._analyze_trend()
            
            # Анализ объема (если включен)
            volume_analysis = self._analyze_volume(market_data) if self.volume_filter else {'valid': True}
            
            # Расчет силы сигнала
            signal_strength = self._calculate_signal_strength(fast_ma, slow_ma, current_price)
            
            return {
                'status': 'success',
                'current_price': current_price,
                'fast_ma': fast_ma,
                'slow_ma': slow_ma,
                'cross_analysis': cross_analysis,
                'trend_analysis': trend_analysis,
                'volume_analysis': volume_analysis,
                'signal_strength': signal_strength,
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
            
            cross_analysis = analysis['cross_analysis']
            trend_analysis = analysis['trend_analysis']
            volume_analysis = analysis['volume_analysis']
            signal_strength = analysis['signal_strength']
            
            # Проверка условий для сигнала
            if not cross_analysis['has_cross']:
                return (SignalType.HOLD, 0.0)
            
            # Проверка объема
            if not volume_analysis['valid']:
                return (SignalType.HOLD, 0.0)
            
            # Проверка минимального изменения цены
            if abs(signal_strength) < self.min_price_change / 100:
                return (SignalType.HOLD, 0.0)
            
            # Определение типа сигнала
            if cross_analysis['direction'] == 'bullish':
                signal_type = SignalType.BUY
                reason = f"Бычье пересечение MA, тренд: {trend_analysis['direction']}"
            elif cross_analysis['direction'] == 'bearish':
                signal_type = SignalType.SELL
                reason = f"Медвежье пересечение MA, тренд: {trend_analysis['direction']}"
            else:
                signal_type = SignalType.HOLD
                reason = "Неопределенное пересечение"
            
            # Корректировка силы сигнала на основе тренда
            adjusted_strength = abs(signal_strength)
            if trend_analysis['direction'] == 'up' and signal_type == SignalType.BUY:
                adjusted_strength *= 1.2
            elif trend_analysis['direction'] == 'down' and signal_type == SignalType.SELL:
                adjusted_strength *= 1.2
            elif trend_analysis['direction'] == 'sideways':
                adjusted_strength *= 0.8
            
            # Ограничение силы сигнала
            adjusted_strength = min(adjusted_strength, 1.0)
            
            # Сохранение последнего сигнала
            self.last_signal = signal_type
            self.signal_strength = adjusted_strength
            
            return (signal_type, adjusted_strength)
            
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
            'type': 'Moving Averages',
            'description': 'Торговля на основе пересечений скользящих средних',
            'parameters': {
                'fast_period': self.fast_period,
                'slow_period': self.slow_period,
                'ma_type': self.ma_type,
                'min_price_change': self.min_price_change,
                'volume_filter': self.volume_filter,
                'min_volume_ratio': self.min_volume_ratio
            },
            'risk_level': 'Medium',
            'timeframe': '1m-1h',
            'suitable_for': ['Trending markets', 'Medium volatility'],
            'not_suitable_for': ['High volatility', 'Sideways markets']
        }
    
    def _update_price_history(self, klines: List[Dict]):
        """
        Обновление истории цен
        
        Args:
            klines: Данные свечей
        """
        try:
            # Извлечение цен закрытия
            new_prices = []
            new_volumes = []
            
            for kline in klines:
                if isinstance(kline, list) and len(kline) >= 6:
                    close_price = float(kline[4])  # Цена закрытия
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
            self.logger.error(f"Ошибка обновления истории цен: {e}")
    
    def _calculate_ma(self, prices: List[float], period: int, ma_type: str) -> Optional[float]:
        """
        Расчет скользящей средней
        
        Args:
            prices: Список цен
            period: Период MA
            ma_type: Тип MA
            
        Returns:
            Значение MA или None
        """
        try:
            if len(prices) < period:
                return None
            
            recent_prices = prices[-period:]
            
            if ma_type == 'sma':
                return sum(recent_prices) / period
            
            elif ma_type == 'ema':
                multiplier = 2 / (period + 1)
                ema = recent_prices[0]
                for price in recent_prices[1:]:
                    ema = (price * multiplier) + (ema * (1 - multiplier))
                return ema
            
            elif ma_type == 'wma':
                weights = list(range(1, period + 1))
                weighted_sum = sum(price * weight for price, weight in zip(recent_prices, weights))
                return weighted_sum / sum(weights)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета MA: {e}")
            return None
    
    def _analyze_crossover(self) -> Dict[str, Any]:
        """
        Анализ пересечений MA
        
        Returns:
            Результат анализа пересечений
        """
        try:
            if len(self.fast_ma_history) < 2 or len(self.slow_ma_history) < 2:
                return {'has_cross': False, 'direction': None}
            
            # Текущие и предыдущие значения
            fast_current = self.fast_ma_history[-1]
            fast_previous = self.fast_ma_history[-2]
            slow_current = self.slow_ma_history[-1]
            slow_previous = self.slow_ma_history[-2]
            
            # Проверка пересечения
            cross_up = (fast_previous <= slow_previous and fast_current > slow_current)
            cross_down = (fast_previous >= slow_previous and fast_current < slow_current)
            
            if cross_up:
                direction = 'bullish'
                self.last_cross_direction = 'up'
            elif cross_down:
                direction = 'bearish'
                self.last_cross_direction = 'down'
            else:
                direction = None
            
            return {
                'has_cross': cross_up or cross_down,
                'direction': direction,
                'fast_ma': fast_current,
                'slow_ma': slow_current,
                'separation': abs(fast_current - slow_current) / slow_current * 100
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа пересечений: {e}")
            return {'has_cross': False, 'direction': None}
    
    def _analyze_trend(self) -> Dict[str, Any]:
        """
        Анализ тренда
        
        Returns:
            Результат анализа тренда
        """
        try:
            if len(self.slow_ma_history) < 5:
                return {'direction': 'unknown', 'strength': 0.0}
            
            # Анализ последних 5 значений медленной MA
            recent_ma = self.slow_ma_history[-5:]
            
            # Подсчет направления изменений
            up_moves = 0
            down_moves = 0
            
            for i in range(1, len(recent_ma)):
                if recent_ma[i] > recent_ma[i-1]:
                    up_moves += 1
                elif recent_ma[i] < recent_ma[i-1]:
                    down_moves += 1
            
            # Определение направления тренда
            if up_moves >= 3:
                direction = 'up'
                strength = up_moves / 4
            elif down_moves >= 3:
                direction = 'down'
                strength = down_moves / 4
            else:
                direction = 'sideways'
                strength = 0.5
            
            return {
                'direction': direction,
                'strength': strength,
                'up_moves': up_moves,
                'down_moves': down_moves
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа тренда: {e}")
            return {'direction': 'unknown', 'strength': 0.0}
    
    def _analyze_volume(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализ объема
        
        Args:
            market_data: Рыночные данные
            
        Returns:
            Результат анализа объема
        """
        try:
            if not self.volume_filter or len(self.volume_history) < 10:
                return {'valid': True, 'ratio': 1.0}
            
            # Текущий объем
            current_volume = self.volume_history[-1]
            
            # Средний объем за последние 10 периодов
            avg_volume = sum(self.volume_history[-10:]) / 10
            
            # Отношение текущего объема к среднему
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            # Проверка минимального отношения
            is_valid = volume_ratio >= self.min_volume_ratio
            
            return {
                'valid': is_valid,
                'ratio': volume_ratio,
                'current_volume': current_volume,
                'avg_volume': avg_volume
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа объема: {e}")
            return {'valid': True, 'ratio': 1.0}
    
    def _calculate_signal_strength(self, fast_ma: float, slow_ma: float, current_price: float) -> float:
        """
        Расчет силы сигнала
        
        Args:
            fast_ma: Быстрая MA
            slow_ma: Медленная MA
            current_price: Текущая цена
            
        Returns:
            Сила сигнала (-1.0 до 1.0)
        """
        try:
            # Разность между MA в процентах
            ma_diff = (fast_ma - slow_ma) / slow_ma
            
            # Отклонение цены от медленной MA
            price_deviation = (current_price - slow_ma) / slow_ma
            
            # Комбинированная сила сигнала
            signal_strength = (ma_diff + price_deviation) / 2
            
            # Ограничение в диапазоне [-1, 1]
            return max(-1.0, min(1.0, signal_strength))
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы сигнала: {e}")
            return 0.0