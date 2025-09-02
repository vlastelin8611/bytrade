#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Стратегия торговли на основе полос Боллинджера

Использует полосы Боллинджера для определения уровней
перекупленности/перепроданности и генерации торговых сигналов.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import statistics

from .base_strategy import BaseStrategy, SignalType

class BollingerBandsStrategy(BaseStrategy):
    """
    Стратегия торговли на полосах Боллинджера
    
    Параметры:
    - period: Период для расчета средней линии (по умолчанию 20)
    - std_dev: Количество стандартных отклонений (по умолчанию 2.0)
    - squeeze_threshold: Порог для определения сжатия полос (%)
    - breakout_confirmation: Требовать подтверждение пробоя
    - volume_filter: Использовать фильтр по объему
    - rsi_filter: Использовать RSI для фильтрации сигналов
    """
    
    def __init__(self, name: str, symbol: str, api_client, db_manager, config_manager, **kwargs):
        # Создаем config с символом для BaseStrategy
        config = kwargs.copy()
        config['asset'] = symbol
        super().__init__(name, config, api_client, db_manager, config_manager)
        
        # Параметры стратегии
        self.period = kwargs.get('period', 20)
        self.std_dev = kwargs.get('std_dev', 2.0)
        self.squeeze_threshold = kwargs.get('squeeze_threshold', 5.0)  # %
        self.breakout_confirmation = kwargs.get('breakout_confirmation', True)
        self.volume_filter = kwargs.get('volume_filter', True)
        self.rsi_filter = kwargs.get('rsi_filter', True)
        self.rsi_period = kwargs.get('rsi_period', 14)
        
        # Валидация параметров
        if self.period < 5:
            raise ValueError("Период должен быть не менее 5")
        
        if self.std_dev <= 0:
            raise ValueError("Стандартное отклонение должно быть положительным")
        
        # Буферы данных
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.high_history: List[float] = []
        self.low_history: List[float] = []
        
        # История полос Боллинджера
        self.upper_band_history: List[float] = []
        self.middle_band_history: List[float] = []
        self.lower_band_history: List[float] = []
        self.bandwidth_history: List[float] = []
        self.bb_percent_history: List[float] = []
        
        # История RSI (если используется)
        self.rsi_history: List[float] = []
        
        # Состояние стратегии
        self.last_squeeze_state = False
        self.last_breakout_direction = None
        self.squeeze_duration = 0
        
        # Максимальный размер буферов
        self.max_buffer_size = max(self.period * 3, 200)
        
        self.logger.info(f"Инициализирована стратегия Bollinger Bands: period={self.period}, std_dev={self.std_dev}")
    
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
            if len(self.price_history) < self.period:
                return {
                    'status': 'insufficient_data',
                    'required': self.period,
                    'available': len(self.price_history)
                }
            
            # Расчет полос Боллинджера
            bb_result = self._calculate_bollinger_bands()
            if not bb_result:
                return {'status': 'error', 'error': 'Ошибка расчета полос Боллинджера'}
            
            # Анализ положения цены относительно полос
            position_analysis = self._analyze_price_position(current_price, bb_result)
            
            # Анализ сжатия полос
            squeeze_analysis = self._analyze_squeeze(bb_result)
            
            # Анализ пробоев
            breakout_analysis = self._analyze_breakouts(current_price, bb_result)
            
            # Анализ объема (если включен)
            volume_analysis = self._analyze_volume() if self.volume_filter else {'confirmed': True}
            
            # Анализ RSI (если включен)
            rsi_analysis = self._analyze_rsi() if self.rsi_filter else {'value': 50, 'zone': 'neutral'}
            
            return {
                'status': 'success',
                'current_price': current_price,
                'bollinger_bands': bb_result,
                'position_analysis': position_analysis,
                'squeeze_analysis': squeeze_analysis,
                'breakout_analysis': breakout_analysis,
                'volume_analysis': volume_analysis,
                'rsi_analysis': rsi_analysis,
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
            
            position_analysis = analysis['position_analysis']
            squeeze_analysis = analysis['squeeze_analysis']
            breakout_analysis = analysis['breakout_analysis']
            volume_analysis = analysis['volume_analysis']
            rsi_analysis = analysis['rsi_analysis']
            
            # Проверка объема
            if self.volume_filter and not volume_analysis['confirmed']:
                return (SignalType.HOLD, 0.0)
            
            # Логика генерации сигналов
            signal_result = self._generate_bb_signal(
                position_analysis, squeeze_analysis, breakout_analysis, rsi_analysis
            )
            
            if signal_result['signal'] == SignalType.HOLD:
                return (signal_result['signal'], signal_result.get('strength', 0.0))
            
            # Расчет силы сигнала
            signal_strength = self._calculate_signal_strength(
                position_analysis, squeeze_analysis, breakout_analysis, 
                volume_analysis, rsi_analysis
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
            'type': 'Bollinger Bands',
            'description': 'Торговля на основе полос Боллинджера с анализом сжатий и пробоев',
            'parameters': {
                'period': self.period,
                'std_dev': self.std_dev,
                'squeeze_threshold': self.squeeze_threshold,
                'breakout_confirmation': self.breakout_confirmation,
                'volume_filter': self.volume_filter,
                'rsi_filter': self.rsi_filter
            },
            'risk_level': 'Medium',
            'timeframe': '15m-4h',
            'suitable_for': ['Range-bound markets', 'Volatility breakouts'],
            'not_suitable_for': ['Strong trending markets', 'Very low volatility']
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
    
    def _calculate_bollinger_bands(self) -> Optional[Dict[str, float]]:
        """
        Расчет полос Боллинджера
        
        Returns:
            Словарь с компонентами полос Боллинджера или None
        """
        try:
            if len(self.price_history) < self.period:
                return None
            
            # Получение последних цен для расчета
            recent_prices = self.price_history[-self.period:]
            
            # Средняя линия (SMA)
            middle_band = sum(recent_prices) / self.period
            
            # Стандартное отклонение
            variance = sum((price - middle_band) ** 2 for price in recent_prices) / self.period
            std_deviation = variance ** 0.5
            
            # Верхняя и нижняя полосы
            upper_band = middle_band + (self.std_dev * std_deviation)
            lower_band = middle_band - (self.std_dev * std_deviation)
            
            # Ширина полос (Bandwidth)
            bandwidth = ((upper_band - lower_band) / middle_band) * 100
            
            # %B (положение цены относительно полос)
            current_price = self.price_history[-1]
            bb_percent = ((current_price - lower_band) / (upper_band - lower_band)) * 100
            
            # Обновление истории
            self.upper_band_history.append(upper_band)
            self.middle_band_history.append(middle_band)
            self.lower_band_history.append(lower_band)
            self.bandwidth_history.append(bandwidth)
            self.bb_percent_history.append(bb_percent)
            
            # Ограничение размера буферов
            if len(self.upper_band_history) > self.max_buffer_size:
                self.upper_band_history = self.upper_band_history[-self.max_buffer_size:]
                self.middle_band_history = self.middle_band_history[-self.max_buffer_size:]
                self.lower_band_history = self.lower_band_history[-self.max_buffer_size:]
                self.bandwidth_history = self.bandwidth_history[-self.max_buffer_size:]
                self.bb_percent_history = self.bb_percent_history[-self.max_buffer_size:]
            
            return {
                'upper': upper_band,
                'middle': middle_band,
                'lower': lower_band,
                'bandwidth': bandwidth,
                'bb_percent': bb_percent,
                'std_dev': std_deviation
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета полос Боллинджера: {e}")
            return None
    
    def _analyze_price_position(self, current_price: float, bb_result: Dict[str, float]) -> Dict[str, Any]:
        """
        Анализ положения цены относительно полос Боллинджера
        
        Args:
            current_price: Текущая цена
            bb_result: Результат расчета полос Боллинджера
            
        Returns:
            Результат анализа положения
        """
        try:
            upper_band = bb_result['upper']
            middle_band = bb_result['middle']
            lower_band = bb_result['lower']
            bb_percent = bb_result['bb_percent']
            
            # Определение положения цены
            if current_price > upper_band:
                position = 'above_upper'
                zone = 'overbought'
            elif current_price < lower_band:
                position = 'below_lower'
                zone = 'oversold'
            elif current_price > middle_band:
                position = 'upper_half'
                zone = 'bullish'
            else:
                position = 'lower_half'
                zone = 'bearish'
            
            # Расстояние до полос в процентах
            distance_to_upper = ((upper_band - current_price) / current_price) * 100
            distance_to_lower = ((current_price - lower_band) / current_price) * 100
            distance_to_middle = ((current_price - middle_band) / current_price) * 100
            
            return {
                'position': position,
                'zone': zone,
                'bb_percent': bb_percent,
                'distance_to_upper': distance_to_upper,
                'distance_to_lower': distance_to_lower,
                'distance_to_middle': distance_to_middle
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа положения цены: {e}")
            return {'position': 'unknown', 'zone': 'neutral'}
    
    def _analyze_squeeze(self, bb_result: Dict[str, float]) -> Dict[str, Any]:
        """
        Анализ сжатия полос Боллинджера
        
        Args:
            bb_result: Результат расчета полос Боллинджера
            
        Returns:
            Результат анализа сжатия
        """
        try:
            current_bandwidth = bb_result['bandwidth']
            
            # Проверка наличия достаточной истории
            if len(self.bandwidth_history) < 20:
                return {
                    'is_squeeze': False,
                    'squeeze_strength': 0.0,
                    'duration': 0
                }
            
            # Средняя ширина полос за последние 20 периодов
            avg_bandwidth = sum(self.bandwidth_history[-20:]) / 20
            
            # Определение сжатия
            is_squeeze = current_bandwidth < (avg_bandwidth * (1 - self.squeeze_threshold / 100))
            
            # Обновление состояния сжатия
            if is_squeeze:
                if self.last_squeeze_state:
                    self.squeeze_duration += 1
                else:
                    self.squeeze_duration = 1
            else:
                self.squeeze_duration = 0
            
            self.last_squeeze_state = is_squeeze
            
            # Сила сжатия
            squeeze_strength = max(0, (avg_bandwidth - current_bandwidth) / avg_bandwidth)
            
            return {
                'is_squeeze': is_squeeze,
                'squeeze_strength': squeeze_strength,
                'duration': self.squeeze_duration,
                'current_bandwidth': current_bandwidth,
                'avg_bandwidth': avg_bandwidth,
                'threshold': avg_bandwidth * (1 - self.squeeze_threshold / 100)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа сжатия: {e}")
            return {'is_squeeze': False, 'squeeze_strength': 0.0, 'duration': 0}
    
    def _analyze_breakouts(self, current_price: float, bb_result: Dict[str, float]) -> Dict[str, Any]:
        """
        Анализ пробоев полос Боллинджера
        
        Args:
            current_price: Текущая цена
            bb_result: Результат расчета полос Боллинджера
            
        Returns:
            Результат анализа пробоев
        """
        try:
            if len(self.price_history) < 3 or len(self.upper_band_history) < 3:
                return {
                    'has_breakout': False,
                    'direction': None,
                    'confirmed': False
                }
            
            # Текущие и предыдущие значения
            prev_price = self.price_history[-2]
            prev_upper = self.upper_band_history[-2]
            prev_lower = self.lower_band_history[-2]
            
            current_upper = bb_result['upper']
            current_lower = bb_result['lower']
            
            # Проверка пробоев
            upper_breakout = (prev_price <= prev_upper and current_price > current_upper)
            lower_breakout = (prev_price >= prev_lower and current_price < current_lower)
            
            has_breakout = upper_breakout or lower_breakout
            direction = None
            
            if upper_breakout:
                direction = 'upward'
                self.last_breakout_direction = 'up'
            elif lower_breakout:
                direction = 'downward'
                self.last_breakout_direction = 'down'
            
            # Подтверждение пробоя (если требуется)
            confirmed = True
            if self.breakout_confirmation and has_breakout:
                # Проверка, что цена остается за пределами полосы
                if direction == 'upward':
                    confirmed = current_price > current_upper * 1.001  # 0.1% буфер
                elif direction == 'downward':
                    confirmed = current_price < current_lower * 0.999  # 0.1% буфер
            
            # Сила пробоя
            breakout_strength = 0.0
            if has_breakout and confirmed:
                if direction == 'upward':
                    breakout_strength = (current_price - current_upper) / current_upper
                elif direction == 'downward':
                    breakout_strength = (current_lower - current_price) / current_lower
            
            return {
                'has_breakout': has_breakout,
                'direction': direction,
                'confirmed': confirmed,
                'strength': min(breakout_strength, 1.0)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа пробоев: {e}")
            return {'has_breakout': False, 'direction': None, 'confirmed': False}
    
    def _analyze_volume(self) -> Dict[str, Any]:
        """
        Анализ объема для подтверждения сигналов
        
        Returns:
            Результат анализа объема
        """
        try:
            if len(self.volume_history) < 10:
                return {'confirmed': True, 'ratio': 1.0}
            
            current_volume = self.volume_history[-1]
            avg_volume = sum(self.volume_history[-10:]) / 10
            
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
            
            # Подтверждение при объеме выше среднего на 20%
            confirmed = volume_ratio >= 1.2
            
            return {
                'confirmed': confirmed,
                'ratio': volume_ratio,
                'current_volume': current_volume,
                'avg_volume': avg_volume
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа объема: {e}")
            return {'confirmed': True, 'ratio': 1.0}
    
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
    
    def _generate_bb_signal(self, position_analysis: Dict[str, Any], squeeze_analysis: Dict[str, Any],
                           breakout_analysis: Dict[str, Any], rsi_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерация сигнала на основе анализа полос Боллинджера
        
        Args:
            position_analysis: Анализ положения цены
            squeeze_analysis: Анализ сжатия
            breakout_analysis: Анализ пробоев
            rsi_analysis: Анализ RSI
            
        Returns:
            Торговый сигнал
        """
        try:
            # Приоритет 1: Подтвержденные пробои после сжатия
            if (squeeze_analysis['duration'] >= 3 and 
                breakout_analysis['has_breakout'] and 
                breakout_analysis['confirmed']):
                
                if breakout_analysis['direction'] == 'upward':
                    # Дополнительная проверка RSI
                    if not self.rsi_filter or rsi_analysis['zone'] != 'overbought':
                        return {
                            'signal': SignalType.BUY,
                            'reason': f"Пробой вверх после сжатия ({squeeze_analysis['duration']} периодов)"
                        }
                elif breakout_analysis['direction'] == 'downward':
                    # Дополнительная проверка RSI
                    if not self.rsi_filter or rsi_analysis['zone'] != 'oversold':
                        return {
                            'signal': SignalType.SELL,
                            'reason': f"Пробой вниз после сжатия ({squeeze_analysis['duration']} периодов)"
                        }
            
            # Приоритет 2: Отскоки от полос в зонах перекупленности/перепроданности
            if position_analysis['zone'] == 'oversold' and position_analysis['bb_percent'] < 10:
                # Проверка RSI для подтверждения
                if not self.rsi_filter or rsi_analysis['zone'] in ['oversold', 'bearish']:
                    return {
                        'signal': SignalType.BUY,
                        'reason': f"Отскок от нижней полосы (%B: {position_analysis['bb_percent']:.1f})"
                    }
            
            elif position_analysis['zone'] == 'overbought' and position_analysis['bb_percent'] > 90:
                # Проверка RSI для подтверждения
                if not self.rsi_filter or rsi_analysis['zone'] in ['overbought', 'bullish']:
                    return {
                        'signal': SignalType.SELL,
                        'reason': f"Отскок от верхней полосы (%B: {position_analysis['bb_percent']:.1f})"
                    }
            
            # Приоритет 3: Простые пробои без сжатия
            if (breakout_analysis['has_breakout'] and 
                breakout_analysis['confirmed'] and 
                breakout_analysis['strength'] > 0.005):  # 0.5% минимальная сила
                
                if breakout_analysis['direction'] == 'upward':
                    if not self.rsi_filter or rsi_analysis['zone'] != 'overbought':
                        return {
                            'signal': SignalType.BUY,
                            'reason': f"Пробой верхней полосы (сила: {breakout_analysis['strength']:.3f})"
                        }
                elif breakout_analysis['direction'] == 'downward':
                    if not self.rsi_filter or rsi_analysis['zone'] != 'oversold':
                        return {
                            'signal': SignalType.SELL,
                            'reason': f"Пробой нижней полосы (сила: {breakout_analysis['strength']:.3f})"
                        }
            
            # Нет сигналов
            return {
                'signal': SignalType.HOLD,
                'reason': 'Нет подходящих условий для входа'
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации BB сигнала: {e}")
            return {'signal': SignalType.HOLD, 'reason': 'Ошибка генерации сигнала'}
    
    def _calculate_signal_strength(self, position_analysis: Dict[str, Any], squeeze_analysis: Dict[str, Any],
                                 breakout_analysis: Dict[str, Any], volume_analysis: Dict[str, Any],
                                 rsi_analysis: Dict[str, Any]) -> float:
        """
        Расчет силы сигнала
        
        Args:
            position_analysis: Анализ положения цены
            squeeze_analysis: Анализ сжатия
            breakout_analysis: Анализ пробоев
            volume_analysis: Анализ объема
            rsi_analysis: Анализ RSI
            
        Returns:
            Сила сигнала (0.0 - 1.0)
        """
        try:
            base_strength = 0.3  # Базовая сила
            
            # Бонус за сжатие
            if squeeze_analysis['is_squeeze']:
                squeeze_bonus = min(squeeze_analysis['duration'] * 0.1, 0.3)
                base_strength += squeeze_bonus
            
            # Бонус за силу пробоя
            if breakout_analysis['has_breakout'] and breakout_analysis['confirmed']:
                breakout_bonus = min(breakout_analysis['strength'] * 2, 0.3)
                base_strength += breakout_bonus
            
            # Бонус за экстремальные значения %B
            bb_percent = position_analysis['bb_percent']
            if bb_percent < 10 or bb_percent > 90:
                extreme_bonus = min(abs(50 - bb_percent) / 100, 0.2)
                base_strength += extreme_bonus
            
            # Корректировка на объем
            volume_multiplier = min(volume_analysis.get('ratio', 1.0), 1.5)
            base_strength *= volume_multiplier
            
            # Корректировка на RSI (если используется)
            if self.rsi_filter:
                rsi_value = rsi_analysis['value']
                if rsi_value <= 30 or rsi_value >= 70:
                    rsi_bonus = 0.1
                    base_strength += rsi_bonus
            
            return min(base_strength, 1.0)
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы сигнала: {e}")
            return 0.0