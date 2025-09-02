#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Стратегия моментум-трейдинга

Использует анализ импульса цены, объема и технических индикаторов
для выявления сильных трендовых движений.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import statistics

from .base_strategy import BaseStrategy, SignalType

class MomentumTradingStrategy(BaseStrategy):
    """
    Стратегия моментум-трейдинга
    
    Параметры:
    - momentum_period: Период для расчета моментума (по умолчанию 14)
    - roc_period: Период для Rate of Change (по умолчанию 10)
    - volume_period: Период для анализа объема (по умолчанию 20)
    - momentum_threshold: Порог моментума для генерации сигналов
    - volume_multiplier: Множитель объема для подтверждения
    - use_rsi_filter: Использовать RSI для фильтрации
    - use_macd_confirmation: Использовать MACD для подтверждения
    """
    
    def __init__(self, name: str, symbol: str, api_client, db_manager, config_manager, **kwargs):
        # Создаем config с символом для BaseStrategy
        config = kwargs.copy()
        config['asset'] = symbol
        super().__init__(name, config, api_client, db_manager, config_manager)
        
        # Параметры стратегии
        self.momentum_period = kwargs.get('momentum_period', 14)
        self.roc_period = kwargs.get('roc_period', 10)
        self.volume_period = kwargs.get('volume_period', 20)
        self.momentum_threshold = kwargs.get('momentum_threshold', 2.0)  # %
        self.volume_multiplier = kwargs.get('volume_multiplier', 1.5)
        self.use_rsi_filter = kwargs.get('use_rsi_filter', True)
        self.use_macd_confirmation = kwargs.get('use_macd_confirmation', True)
        
        # Параметры индикаторов
        self.rsi_period = kwargs.get('rsi_period', 14)
        self.macd_fast = kwargs.get('macd_fast', 12)
        self.macd_slow = kwargs.get('macd_slow', 26)
        self.macd_signal = kwargs.get('macd_signal', 9)
        
        # Валидация параметров
        if self.momentum_period < 5:
            raise ValueError("Период моментума должен быть не менее 5")
        
        if self.roc_period < 3:
            raise ValueError("Период ROC должен быть не менее 3")
        
        # Буферы данных
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.high_history: List[float] = []
        self.low_history: List[float] = []
        
        # История индикаторов
        self.momentum_history: List[float] = []
        self.roc_history: List[float] = []
        self.rsi_history: List[float] = []
        self.macd_history: List[Dict[str, float]] = []
        
        # Состояние тренда
        self.current_trend = 'neutral'
        self.trend_strength = 0.0
        self.trend_duration = 0
        
        # Максимальный размер буферов
        self.max_buffer_size = max(self.momentum_period * 3, self.macd_slow * 2, 200)
        
        self.logger.info(f"Инициализирована стратегия Momentum Trading: period={self.momentum_period}, threshold={self.momentum_threshold}%")
    
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
            required_data = max(self.momentum_period, self.roc_period, self.volume_period)
            if self.use_macd_confirmation:
                required_data = max(required_data, self.macd_slow + self.macd_signal)
            
            if len(self.price_history) < required_data:
                return {
                    'status': 'insufficient_data',
                    'required': required_data,
                    'available': len(self.price_history)
                }
            
            # Расчет моментума
            momentum_result = self._calculate_momentum()
            if not momentum_result:
                return {'status': 'error', 'error': 'Ошибка расчета моментума'}
            
            # Расчет Rate of Change
            roc_result = self._calculate_roc()
            
            # Анализ объема
            volume_analysis = self._analyze_volume()
            
            # Анализ тренда
            trend_analysis = self._analyze_trend(momentum_result, roc_result)
            
            # Анализ RSI (если включен)
            rsi_analysis = self._analyze_rsi() if self.use_rsi_filter else {'value': 50, 'zone': 'neutral'}
            
            # Анализ MACD (если включен)
            macd_analysis = self._analyze_macd() if self.use_macd_confirmation else {'signal': 'neutral'}
            
            return {
                'status': 'success',
                'current_price': current_price,
                'momentum': momentum_result,
                'roc': roc_result,
                'volume_analysis': volume_analysis,
                'trend_analysis': trend_analysis,
                'rsi_analysis': rsi_analysis,
                'macd_analysis': macd_analysis,
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
            
            momentum_result = analysis['momentum']
            roc_result = analysis['roc']
            volume_analysis = analysis['volume_analysis']
            trend_analysis = analysis['trend_analysis']
            rsi_analysis = analysis['rsi_analysis']
            macd_analysis = analysis['macd_analysis']
            
            # Основная логика генерации сигналов
            signal_result = self._generate_momentum_signal(
                momentum_result, roc_result, trend_analysis, volume_analysis
            )
            
            if signal_result['signal'] == SignalType.HOLD:
                return (signal_result['signal'], signal_result.get('strength', 0.0))
            
            # Фильтрация по RSI
            if self.use_rsi_filter:
                rsi_filter_result = self._apply_rsi_filter(signal_result['signal'], rsi_analysis)
                if not rsi_filter_result['passed']:
                    return (SignalType.HOLD, 0.0)
            
            # Подтверждение MACD
            if self.use_macd_confirmation:
                macd_confirmation = self._check_macd_confirmation(signal_result['signal'], macd_analysis)
                if not macd_confirmation['confirmed']:
                    return (SignalType.HOLD, 0.0)
            
            # Расчет силы сигнала
            signal_strength = self._calculate_signal_strength(
                momentum_result, roc_result, volume_analysis, trend_analysis,
                rsi_analysis, macd_analysis
            )
            
            return (signal_result['signal'], signal_strength)
            
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
            'type': 'Momentum Trading',
            'description': 'Торговля на основе анализа импульса цены и объема',
            'parameters': {
                'momentum_period': self.momentum_period,
                'roc_period': self.roc_period,
                'volume_period': self.volume_period,
                'momentum_threshold': self.momentum_threshold,
                'volume_multiplier': self.volume_multiplier,
                'use_rsi_filter': self.use_rsi_filter,
                'use_macd_confirmation': self.use_macd_confirmation
            },
            'risk_level': 'High',
            'timeframe': '5m-1h',
            'suitable_for': ['Strong trending markets', 'High volatility periods'],
            'not_suitable_for': ['Sideways markets', 'Low volatility periods']
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
            new_highs = []
            new_lows = []
            
            for kline in klines:
                if isinstance(kline, list) and len(kline) >= 6:
                    high_price = float(kline[2])   # Максимум
                    low_price = float(kline[3])    # Минимум
                    close_price = float(kline[4])  # Закрытие
                    volume = float(kline[5])       # Объем
                    
                    new_highs.append(high_price)
                    new_lows.append(low_price)
                    new_prices.append(close_price)
                    new_volumes.append(volume)
            
            # Обновление буферов
            self.high_history.extend(new_highs)
            self.low_history.extend(new_lows)
            self.price_history.extend(new_prices)
            self.volume_history.extend(new_volumes)
            
            # Ограничение размера буферов
            if len(self.price_history) > self.max_buffer_size:
                self.high_history = self.high_history[-self.max_buffer_size:]
                self.low_history = self.low_history[-self.max_buffer_size:]
                self.price_history = self.price_history[-self.max_buffer_size:]
                self.volume_history = self.volume_history[-self.max_buffer_size:]
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления истории данных: {e}")
    
    def _calculate_momentum(self) -> Optional[Dict[str, float]]:
        """
        Расчет моментума цены
        
        Returns:
            Словарь с данными моментума или None
        """
        try:
            if len(self.price_history) < self.momentum_period + 1:
                return None
            
            current_price = self.price_history[-1]
            past_price = self.price_history[-(self.momentum_period + 1)]
            
            # Абсолютный моментум
            absolute_momentum = current_price - past_price
            
            # Относительный моментум (%)
            relative_momentum = ((current_price - past_price) / past_price) * 100
            
            # Нормализованный моментум (z-score)
            if len(self.momentum_history) >= 20:
                recent_momentum = self.momentum_history[-20:]
                mean_momentum = sum(recent_momentum) / len(recent_momentum)
                std_momentum = (sum((x - mean_momentum) ** 2 for x in recent_momentum) / len(recent_momentum)) ** 0.5
                normalized_momentum = (relative_momentum - mean_momentum) / std_momentum if std_momentum > 0 else 0
            else:
                normalized_momentum = 0
            
            # Обновление истории
            self.momentum_history.append(relative_momentum)
            if len(self.momentum_history) > self.max_buffer_size:
                self.momentum_history = self.momentum_history[-self.max_buffer_size:]
            
            return {
                'value': relative_momentum,
                'absolute': absolute_momentum,
                'normalized': normalized_momentum,
                'direction': 'bullish' if relative_momentum > 0 else 'bearish',
                'strength': abs(relative_momentum)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета моментума: {e}")
            return None
    
    def _calculate_roc(self) -> Optional[Dict[str, float]]:
        """
        Расчет Rate of Change (ROC)
        
        Returns:
            Словарь с данными ROC или None
        """
        try:
            if len(self.price_history) < self.roc_period + 1:
                return None
            
            current_price = self.price_history[-1]
            past_price = self.price_history[-(self.roc_period + 1)]
            
            # ROC в процентах
            roc_value = ((current_price - past_price) / past_price) * 100
            
            # Сглаженный ROC (EMA)
            if len(self.roc_history) > 0:
                alpha = 2 / (self.roc_period + 1)
                smoothed_roc = alpha * roc_value + (1 - alpha) * self.roc_history[-1]
            else:
                smoothed_roc = roc_value
            
            # Обновление истории
            self.roc_history.append(roc_value)
            if len(self.roc_history) > self.max_buffer_size:
                self.roc_history = self.roc_history[-self.max_buffer_size:]
            
            return {
                'value': roc_value,
                'smoothed': smoothed_roc,
                'direction': 'positive' if roc_value > 0 else 'negative',
                'acceleration': self._calculate_roc_acceleration()
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета ROC: {e}")
            return None
    
    def _calculate_roc_acceleration(self) -> float:
        """
        Расчет ускорения ROC (вторая производная)
        
        Returns:
            Значение ускорения ROC
        """
        try:
            if len(self.roc_history) < 3:
                return 0.0
            
            # Ускорение как разность между текущим и предыдущим ROC
            current_roc = self.roc_history[-1]
            prev_roc = self.roc_history[-2]
            
            acceleration = current_roc - prev_roc
            return acceleration
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета ускорения ROC: {e}")
            return 0.0
    
    def _analyze_volume(self) -> Dict[str, Any]:
        """
        Анализ объема для подтверждения моментума
        
        Returns:
            Результат анализа объема
        """
        try:
            if len(self.volume_history) < self.volume_period:
                return {'confirmed': True, 'ratio': 1.0, 'trend': 'neutral'}
            
            current_volume = self.volume_history[-1]
            avg_volume = sum(self.volume_history[-self.volume_period:]) / self.volume_period
            
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Подтверждение при объеме выше среднего
            confirmed = volume_ratio >= self.volume_multiplier
            
            # Тренд объема
            if len(self.volume_history) >= self.volume_period * 2:
                recent_avg = sum(self.volume_history[-self.volume_period:]) / self.volume_period
                older_avg = sum(self.volume_history[-self.volume_period*2:-self.volume_period]) / self.volume_period
                
                if recent_avg > older_avg * 1.1:
                    volume_trend = 'increasing'
                elif recent_avg < older_avg * 0.9:
                    volume_trend = 'decreasing'
                else:
                    volume_trend = 'stable'
            else:
                volume_trend = 'neutral'
            
            return {
                'confirmed': confirmed,
                'ratio': volume_ratio,
                'trend': volume_trend,
                'current_volume': current_volume,
                'avg_volume': avg_volume
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа объема: {e}")
            return {'confirmed': True, 'ratio': 1.0, 'trend': 'neutral'}
    
    def _analyze_trend(self, momentum_result: Dict[str, float], roc_result: Dict[str, float]) -> Dict[str, Any]:
        """
        Анализ тренда на основе моментума и ROC
        
        Args:
            momentum_result: Результат расчета моментума
            roc_result: Результат расчета ROC
            
        Returns:
            Результат анализа тренда
        """
        try:
            momentum_value = momentum_result['value']
            roc_value = roc_result['value']
            roc_acceleration = roc_result['acceleration']
            
            # Определение направления тренда
            if momentum_value > self.momentum_threshold and roc_value > 0:
                direction = 'bullish'
                strength = min((momentum_value / self.momentum_threshold), 3.0)
            elif momentum_value < -self.momentum_threshold and roc_value < 0:
                direction = 'bearish'
                strength = min((abs(momentum_value) / self.momentum_threshold), 3.0)
            else:
                direction = 'neutral'
                strength = 0.0
            
            # Учет ускорения
            if direction == 'bullish' and roc_acceleration > 0:
                strength *= 1.2  # Усиление при положительном ускорении
            elif direction == 'bearish' and roc_acceleration < 0:
                strength *= 1.2  # Усиление при отрицательном ускорении
            elif roc_acceleration != 0:
                strength *= 0.8  # Ослабление при противоположном ускорении
            
            # Обновление состояния тренда
            if direction == self.current_trend:
                self.trend_duration += 1
            else:
                self.current_trend = direction
                self.trend_duration = 1
            
            self.trend_strength = strength
            
            return {
                'direction': direction,
                'strength': min(strength, 3.0),
                'duration': self.trend_duration,
                'acceleration': roc_acceleration,
                'momentum_value': momentum_value,
                'roc_value': roc_value
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа тренда: {e}")
            return {'direction': 'neutral', 'strength': 0.0, 'duration': 0}
    
    def _analyze_rsi(self) -> Dict[str, Any]:
        """
        Анализ RSI для фильтрации сигналов
        
        Returns:
            Результат анализа RSI
        """
        try:
            if len(self.price_history) < self.rsi_period + 1:
                return {'value': 50, 'zone': 'neutral'}
            
            # Расчет RSI
            rsi_value = self._calculate_rsi()
            if rsi_value is None:
                return {'value': 50, 'zone': 'neutral'}
            
            # Определение зоны RSI
            if rsi_value <= 30:
                zone = 'oversold'
            elif rsi_value >= 70:
                zone = 'overbought'
            elif rsi_value < 50:
                zone = 'bearish'
            else:
                zone = 'bullish'
            
            return {
                'value': rsi_value,
                'zone': zone
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа RSI: {e}")
            return {'value': 50, 'zone': 'neutral'}
    
    def _calculate_rsi(self) -> Optional[float]:
        """
        Расчет RSI (Relative Strength Index)
        
        Returns:
            Значение RSI или None
        """
        try:
            if len(self.price_history) < self.rsi_period + 1:
                return None
            
            # Расчет изменений цен
            price_changes = []
            for i in range(1, len(self.price_history)):
                change = self.price_history[i] - self.price_history[i-1]
                price_changes.append(change)
            
            if len(price_changes) < self.rsi_period:
                return None
            
            # Разделение на прибыли и убытки
            gains = [max(change, 0) for change in price_changes[-self.rsi_period:]]
            losses = [abs(min(change, 0)) for change in price_changes[-self.rsi_period:]]
            
            # Расчет средних значений
            avg_gain = sum(gains) / self.rsi_period
            avg_loss = sum(losses) / self.rsi_period
            
            if avg_loss == 0:
                return 100.0
            
            # Расчет RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            # Обновление истории RSI
            self.rsi_history.append(rsi)
            if len(self.rsi_history) > self.max_buffer_size:
                self.rsi_history = self.rsi_history[-self.max_buffer_size:]
            
            return rsi
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета RSI: {e}")
            return None
    
    def _analyze_macd(self) -> Dict[str, Any]:
        """
        Анализ MACD для подтверждения сигналов
        
        Returns:
            Результат анализа MACD
        """
        try:
            if len(self.price_history) < self.macd_slow + self.macd_signal:
                return {'signal': 'neutral', 'histogram': 0, 'crossover': False}
            
            # Расчет MACD
            macd_result = self._calculate_macd()
            if not macd_result:
                return {'signal': 'neutral', 'histogram': 0, 'crossover': False}
            
            macd_line = macd_result['macd']
            signal_line = macd_result['signal']
            histogram = macd_result['histogram']
            
            # Определение сигнала MACD
            if macd_line > signal_line and histogram > 0:
                signal = 'bullish'
            elif macd_line < signal_line and histogram < 0:
                signal = 'bearish'
            else:
                signal = 'neutral'
            
            # Проверка пересечения
            crossover = False
            if len(self.macd_history) >= 2:
                prev_macd = self.macd_history[-2]
                if (prev_macd['macd'] <= prev_macd['signal'] and macd_line > signal_line):
                    crossover = 'bullish'
                elif (prev_macd['macd'] >= prev_macd['signal'] and macd_line < signal_line):
                    crossover = 'bearish'
            
            return {
                'signal': signal,
                'macd': macd_line,
                'signal_line': signal_line,
                'histogram': histogram,
                'crossover': crossover
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа MACD: {e}")
            return {'signal': 'neutral', 'histogram': 0, 'crossover': False}
    
    def _calculate_macd(self) -> Optional[Dict[str, float]]:
        """
        Расчет MACD (Moving Average Convergence Divergence)
        
        Returns:
            Словарь с компонентами MACD или None
        """
        try:
            if len(self.price_history) < self.macd_slow:
                return None
            
            # Расчет EMA
            def calculate_ema(prices, period):
                if len(prices) < period:
                    return None
                
                alpha = 2 / (period + 1)
                ema = prices[0]
                
                for price in prices[1:]:
                    ema = alpha * price + (1 - alpha) * ema
                
                return ema
            
            # EMA для быстрой и медленной линий
            fast_ema = calculate_ema(self.price_history, self.macd_fast)
            slow_ema = calculate_ema(self.price_history, self.macd_slow)
            
            if fast_ema is None or slow_ema is None:
                return None
            
            # MACD линия
            macd_line = fast_ema - slow_ema
            
            # Сигнальная линия (EMA от MACD)
            if len(self.macd_history) >= self.macd_signal:
                macd_values = [entry['macd'] for entry in self.macd_history[-(self.macd_signal-1):]]
                macd_values.append(macd_line)
                signal_line = calculate_ema(macd_values, self.macd_signal)
            else:
                signal_line = macd_line
            
            # Гистограмма
            histogram = macd_line - signal_line
            
            # Обновление истории
            macd_data = {
                'macd': macd_line,
                'signal': signal_line,
                'histogram': histogram
            }
            
            self.macd_history.append(macd_data)
            if len(self.macd_history) > self.max_buffer_size:
                self.macd_history = self.macd_history[-self.max_buffer_size:]
            
            return macd_data
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета MACD: {e}")
            return None
    
    def _generate_momentum_signal(self, momentum_result: Dict[str, float], roc_result: Dict[str, float],
                                 trend_analysis: Dict[str, Any], volume_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерация сигнала на основе анализа моментума
        
        Args:
            momentum_result: Результат расчета моментума
            roc_result: Результат расчета ROC
            trend_analysis: Анализ тренда
            volume_analysis: Анализ объема
            
        Returns:
            Торговый сигнал
        """
        try:
            momentum_value = momentum_result['value']
            roc_value = roc_result['value']
            trend_direction = trend_analysis['direction']
            trend_strength = trend_analysis['strength']
            roc_acceleration = trend_analysis['acceleration']
            
            # Приоритет 1: Сильный моментум с подтверждением объема
            if (trend_direction == 'bullish' and 
                trend_strength >= 1.5 and 
                volume_analysis['confirmed'] and
                roc_acceleration > 0):
                
                return {
                    'signal': SignalType.BUY,
                    'reason': f"Сильный бычий моментум (сила: {trend_strength:.2f}, ускорение: {roc_acceleration:.3f})"
                }
            
            elif (trend_direction == 'bearish' and 
                  trend_strength >= 1.5 and 
                  volume_analysis['confirmed'] and
                  roc_acceleration < 0):
                
                return {
                    'signal': SignalType.SELL,
                    'reason': f"Сильный медвежий моментум (сила: {trend_strength:.2f}, ускорение: {roc_acceleration:.3f})"
                }
            
            # Приоритет 2: Умеренный моментум с хорошим объемом
            if (trend_direction == 'bullish' and 
                trend_strength >= 1.0 and 
                volume_analysis['ratio'] >= self.volume_multiplier * 0.8):
                
                return {
                    'signal': SignalType.BUY,
                    'reason': f"Умеренный бычий моментум (сила: {trend_strength:.2f}, объем: {volume_analysis['ratio']:.2f}x)"
                }
            
            elif (trend_direction == 'bearish' and 
                  trend_strength >= 1.0 and 
                  volume_analysis['ratio'] >= self.volume_multiplier * 0.8):
                
                return {
                    'signal': SignalType.SELL,
                    'reason': f"Умеренный медвежий моментум (сила: {trend_strength:.2f}, объем: {volume_analysis['ratio']:.2f}x)"
                }
            
            # Приоритет 3: Начальный моментум с продолжительностью тренда
            if (trend_direction == 'bullish' and 
                momentum_value > self.momentum_threshold * 0.7 and
                trend_analysis['duration'] <= 3):  # Ранняя стадия тренда
                
                return {
                    'signal': SignalType.BUY,
                    'reason': f"Начальный бычий моментум (значение: {momentum_value:.2f}%, длительность: {trend_analysis['duration']})"
                }
            
            elif (trend_direction == 'bearish' and 
                  abs(momentum_value) > self.momentum_threshold * 0.7 and
                  trend_analysis['duration'] <= 3):  # Ранняя стадия тренда
                
                return {
                    'signal': SignalType.SELL,
                    'reason': f"Начальный медвежий моментум (значение: {momentum_value:.2f}%, длительность: {trend_analysis['duration']})"
                }
            
            # Нет подходящих условий
            return {
                'signal': SignalType.HOLD,
                'reason': f"Недостаточный моментум (значение: {momentum_value:.2f}%, сила тренда: {trend_strength:.2f})"
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации моментум сигнала: {e}")
            return {'signal': SignalType.HOLD, 'reason': 'Ошибка генерации сигнала'}
    
    def _apply_rsi_filter(self, signal: SignalType, rsi_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Применение RSI фильтра к сигналу
        
        Args:
            signal: Торговый сигнал
            rsi_analysis: Анализ RSI
            
        Returns:
            Результат фильтрации
        """
        try:
            rsi_value = rsi_analysis['value']
            rsi_zone = rsi_analysis['zone']
            
            # Фильтрация покупок в зоне перекупленности
            if signal == SignalType.BUY and rsi_zone == 'overbought':
                return {
                    'passed': False,
                    'reason': f"RSI в зоне перекупленности ({rsi_value:.1f})"
                }
            
            # Фильтрация продаж в зоне перепроданности
            if signal == SignalType.SELL and rsi_zone == 'oversold':
                return {
                    'passed': False,
                    'reason': f"RSI в зоне перепроданности ({rsi_value:.1f})"
                }
            
            # Дополнительная фильтрация для экстремальных значений
            if signal == SignalType.BUY and rsi_value > 80:
                return {
                    'passed': False,
                    'reason': f"RSI слишком высокий ({rsi_value:.1f})"
                }
            
            if signal == SignalType.SELL and rsi_value < 20:
                return {
                    'passed': False,
                    'reason': f"RSI слишком низкий ({rsi_value:.1f})"
                }
            
            return {'passed': True, 'reason': f"RSI подходящий ({rsi_value:.1f})"}
            
        except Exception as e:
            self.logger.error(f"Ошибка применения RSI фильтра: {e}")
            return {'passed': True, 'reason': 'Ошибка фильтра'}
    
    def _check_macd_confirmation(self, signal: SignalType, macd_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Проверка подтверждения MACD
        
        Args:
            signal: Торговый сигнал
            macd_analysis: Анализ MACD
            
        Returns:
            Результат проверки подтверждения
        """
        try:
            macd_signal = macd_analysis['signal']
            macd_crossover = macd_analysis.get('crossover', False)
            histogram = macd_analysis['histogram']
            
            # Подтверждение покупки
            if signal == SignalType.BUY:
                if macd_signal == 'bullish' or macd_crossover == 'bullish':
                    return {
                        'confirmed': True,
                        'reason': f"MACD подтверждает покупку (сигнал: {macd_signal})"
                    }
                elif histogram > 0:  # Гистограмма положительная
                    return {
                        'confirmed': True,
                        'reason': f"MACD гистограмма положительная ({histogram:.4f})"
                    }
                else:
                    return {
                        'confirmed': False,
                        'reason': f"MACD не подтверждает покупку (сигнал: {macd_signal})"
                    }
            
            # Подтверждение продажи
            elif signal == SignalType.SELL:
                if macd_signal == 'bearish' or macd_crossover == 'bearish':
                    return {
                        'confirmed': True,
                        'reason': f"MACD подтверждает продажу (сигнал: {macd_signal})"
                    }
                elif histogram < 0:  # Гистограмма отрицательная
                    return {
                        'confirmed': True,
                        'reason': f"MACD гистограмма отрицательная ({histogram:.4f})"
                    }
                else:
                    return {
                        'confirmed': False,
                        'reason': f"MACD не подтверждает продажу (сигнал: {macd_signal})"
                    }
            
            return {'confirmed': True, 'reason': 'Нет сигнала для проверки'}
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки MACD подтверждения: {e}")
            return {'confirmed': True, 'reason': 'Ошибка проверки'}
    
    def _calculate_signal_strength(self, momentum_result: Dict[str, float], roc_result: Dict[str, float],
                                 volume_analysis: Dict[str, Any], trend_analysis: Dict[str, Any],
                                 rsi_analysis: Dict[str, Any], macd_analysis: Dict[str, Any]) -> float:
        """
        Расчет силы сигнала
        
        Args:
            momentum_result: Результат расчета моментума
            roc_result: Результат расчета ROC
            volume_analysis: Анализ объема
            trend_analysis: Анализ тренда
            rsi_analysis: Анализ RSI
            macd_analysis: Анализ MACD
            
        Returns:
            Сила сигнала (0.0 - 1.0)
        """
        try:
            base_strength = 0.3  # Базовая сила
            
            # Бонус за силу тренда
            trend_bonus = min(trend_analysis['strength'] * 0.2, 0.4)
            base_strength += trend_bonus
            
            # Бонус за объем
            volume_ratio = volume_analysis.get('ratio', 1.0)
            volume_bonus = min((volume_ratio - 1.0) * 0.2, 0.3)
            base_strength += volume_bonus
            
            # Бонус за ускорение ROC
            roc_acceleration = abs(trend_analysis.get('acceleration', 0))
            acceleration_bonus = min(roc_acceleration * 0.1, 0.2)
            base_strength += acceleration_bonus
            
            # Корректировка на RSI (если используется)
            if self.use_rsi_filter:
                rsi_value = rsi_analysis['value']
                if 30 <= rsi_value <= 70:  # Нейтральная зона
                    rsi_bonus = 0.1
                    base_strength += rsi_bonus
            
            # Корректировка на MACD (если используется)
            if self.use_macd_confirmation:
                histogram = abs(macd_analysis.get('histogram', 0))
                macd_bonus = min(histogram * 10, 0.15)  # Масштабирование гистограммы
                base_strength += macd_bonus
            
            # Бонус за продолжительность тренда (но не слишком долгого)
            duration = trend_analysis['duration']
            if 2 <= duration <= 5:
                duration_bonus = 0.1
                base_strength += duration_bonus
            elif duration > 10:  # Штраф за слишком долгий тренд
                base_strength *= 0.8
            
            return min(base_strength, 1.0)
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы сигнала: {e}")
            return 0.0