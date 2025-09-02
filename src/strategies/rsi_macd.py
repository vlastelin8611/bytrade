#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Стратегия торговли на основе RSI и MACD

Использует комбинацию индикаторов RSI (Relative Strength Index)
и MACD (Moving Average Convergence Divergence) для генерации
торговых сигналов.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

from .base_strategy import BaseStrategy, SignalType

class RSIMACDStrategy(BaseStrategy):
    """
    Стратегия торговли на RSI + MACD
    
    Параметры:
    - rsi_period: Период для расчета RSI (по умолчанию 14)
    - rsi_oversold: Уровень перепроданности RSI (по умолчанию 30)
    - rsi_overbought: Уровень перекупленности RSI (по умолчанию 70)
    - macd_fast: Быстрый период MACD (по умолчанию 12)
    - macd_slow: Медленный период MACD (по умолчанию 26)
    - macd_signal: Период сигнальной линии MACD (по умолчанию 9)
    - min_macd_histogram: Минимальное значение гистограммы MACD
    - volume_confirmation: Требовать подтверждение объемом
    """
    
    def __init__(self, name: str, symbol: str, api_client, db_manager, config_manager, **kwargs):
        # Создаем config с символом для BaseStrategy
        config = kwargs.copy()
        config['asset'] = symbol
        super().__init__(name, config, api_client, db_manager, config_manager)
        
        # Параметры RSI
        self.rsi_period = kwargs.get('rsi_period', 14)
        self.rsi_oversold = kwargs.get('rsi_oversold', 30)
        self.rsi_overbought = kwargs.get('rsi_overbought', 70)
        
        # Параметры MACD
        self.macd_fast = kwargs.get('macd_fast', 12)
        self.macd_slow = kwargs.get('macd_slow', 26)
        self.macd_signal = kwargs.get('macd_signal', 9)
        self.min_macd_histogram = kwargs.get('min_macd_histogram', 0.001)
        
        # Дополнительные параметры
        self.volume_confirmation = kwargs.get('volume_confirmation', True)
        self.trend_filter = kwargs.get('trend_filter', True)
        
        # Валидация параметров
        if self.macd_fast >= self.macd_slow:
            raise ValueError("Быстрый период MACD должен быть меньше медленного")
        
        if not (0 < self.rsi_oversold < self.rsi_overbought < 100):
            raise ValueError("Некорректные уровни RSI")
        
        # Буферы данных
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.high_history: List[float] = []
        self.low_history: List[float] = []
        
        # Индикаторы
        self.rsi_history: List[float] = []
        self.macd_line_history: List[float] = []
        self.macd_signal_history: List[float] = []
        self.macd_histogram_history: List[float] = []
        
        # Состояние стратегии
        self.last_rsi = None
        self.last_macd_signal = None
        self.signal_confirmation_count = 0
        
        # Максимальный размер буферов
        self.max_buffer_size = max(self.macd_slow * 3, 200)
        
        self.logger.info(f"Инициализирована стратегия RSI+MACD: RSI={self.rsi_period}, MACD=({self.macd_fast},{self.macd_slow},{self.macd_signal})")
    
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
            min_required = max(self.rsi_period, self.macd_slow) + self.macd_signal
            if len(self.price_history) < min_required:
                return {
                    'status': 'insufficient_data',
                    'required': min_required,
                    'available': len(self.price_history)
                }
            
            # Расчет RSI
            rsi_result = self._calculate_rsi()
            if rsi_result is None:
                return {'status': 'error', 'error': 'Ошибка расчета RSI'}
            
            # Расчет MACD
            macd_result = self._calculate_macd()
            if not macd_result:
                return {'status': 'error', 'error': 'Ошибка расчета MACD'}
            
            # Анализ RSI сигналов
            rsi_analysis = self._analyze_rsi(rsi_result)
            
            # Анализ MACD сигналов
            macd_analysis = self._analyze_macd(macd_result)
            
            # Анализ объема
            volume_analysis = self._analyze_volume() if self.volume_confirmation else {'confirmed': True}
            
            # Анализ тренда
            trend_analysis = self._analyze_trend() if self.trend_filter else {'direction': 'neutral'}
            
            return {
                'status': 'success',
                'current_price': current_price,
                'rsi': {
                    'value': rsi_result,
                    'analysis': rsi_analysis
                },
                'macd': {
                    'line': macd_result['macd_line'],
                    'signal': macd_result['signal_line'],
                    'histogram': macd_result['histogram'],
                    'analysis': macd_analysis
                },
                'volume_analysis': volume_analysis,
                'trend_analysis': trend_analysis,
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
            
            rsi_data = analysis['rsi']
            macd_data = analysis['macd']
            volume_analysis = analysis['volume_analysis']
            trend_analysis = analysis['trend_analysis']
            
            # Получение сигналов от индикаторов
            rsi_signal = rsi_data['analysis']['signal']
            macd_signal = macd_data['analysis']['signal']
            
            # Проверка подтверждения объемом
            if self.volume_confirmation and not volume_analysis['confirmed']:
                return (SignalType.HOLD, 0.0)
            
            # Логика комбинирования сигналов
            combined_signal = self._combine_signals(rsi_signal, macd_signal, trend_analysis)
            
            if combined_signal['signal'] == SignalType.HOLD:
                return (SignalType.HOLD, 0.0)
            
            # Расчет силы сигнала
            signal_strength = self._calculate_combined_strength(
                rsi_data['analysis'],
                macd_data['analysis'],
                volume_analysis,
                trend_analysis
            )
            
            # Формирование детального ответа
            reason_parts = []
            if rsi_signal != SignalType.HOLD:
                reason_parts.append(f"RSI: {rsi_data['analysis']['reason']}")
            if macd_signal != SignalType.HOLD:
                reason_parts.append(f"MACD: {macd_data['analysis']['reason']}")
            
            reason = "; ".join(reason_parts)
            if trend_analysis['direction'] != 'neutral':
                reason += f"; Тренд: {trend_analysis['direction']}"
            
            return (combined_signal['signal'], signal_strength)
            
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
            'type': 'RSI + MACD',
            'description': 'Комбинированная стратегия на основе RSI и MACD индикаторов',
            'parameters': {
                'rsi_period': self.rsi_period,
                'rsi_oversold': self.rsi_oversold,
                'rsi_overbought': self.rsi_overbought,
                'macd_fast': self.macd_fast,
                'macd_slow': self.macd_slow,
                'macd_signal': self.macd_signal,
                'volume_confirmation': self.volume_confirmation,
                'trend_filter': self.trend_filter
            },
            'risk_level': 'Medium-High',
            'timeframe': '5m-4h',
            'suitable_for': ['Trending markets', 'Medium to high volatility'],
            'not_suitable_for': ['Very low volatility', 'Extremely choppy markets']
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
            
            self.last_rsi = rsi
            return rsi
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета RSI: {e}")
            return None
    
    def _calculate_macd(self) -> Optional[Dict[str, float]]:
        """
        Расчет MACD (Moving Average Convergence Divergence)
        
        Returns:
            Словарь с компонентами MACD или None
        """
        try:
            if len(self.price_history) < self.macd_slow:
                return None
            
            # Расчет EMA для быстрой и медленной линий
            fast_ema = self._calculate_ema(self.price_history, self.macd_fast)
            slow_ema = self._calculate_ema(self.price_history, self.macd_slow)
            
            if fast_ema is None or slow_ema is None:
                return None
            
            # MACD линия
            macd_line = fast_ema - slow_ema
            
            # Обновление истории MACD линии
            self.macd_line_history.append(macd_line)
            if len(self.macd_line_history) > self.max_buffer_size:
                self.macd_line_history = self.macd_line_history[-self.max_buffer_size:]
            
            # Сигнальная линия (EMA от MACD линии)
            if len(self.macd_line_history) >= self.macd_signal:
                signal_line = self._calculate_ema(self.macd_line_history, self.macd_signal)
                
                # Обновление истории сигнальной линии
                self.macd_signal_history.append(signal_line)
                if len(self.macd_signal_history) > self.max_buffer_size:
                    self.macd_signal_history = self.macd_signal_history[-self.max_buffer_size:]
                
                # Гистограмма
                histogram = macd_line - signal_line
                
                # Обновление истории гистограммы
                self.macd_histogram_history.append(histogram)
                if len(self.macd_histogram_history) > self.max_buffer_size:
                    self.macd_histogram_history = self.macd_histogram_history[-self.max_buffer_size:]
                
                return {
                    'macd_line': macd_line,
                    'signal_line': signal_line,
                    'histogram': histogram
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета MACD: {e}")
            return None
    
    def _calculate_ema(self, prices: List[float], period: int) -> Optional[float]:
        """
        Расчет экспоненциальной скользящей средней
        
        Args:
            prices: Список цен
            period: Период EMA
            
        Returns:
            Значение EMA или None
        """
        try:
            if len(prices) < period:
                return None
            
            multiplier = 2 / (period + 1)
            
            # Начальное значение - простая средняя
            ema = sum(prices[:period]) / period
            
            # Расчет EMA для остальных значений
            for price in prices[period:]:
                ema = (price * multiplier) + (ema * (1 - multiplier))
            
            return ema
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета EMA: {e}")
            return None
    
    def _analyze_rsi(self, rsi_value: float) -> Dict[str, Any]:
        """
        Анализ RSI сигналов
        
        Args:
            rsi_value: Текущее значение RSI
            
        Returns:
            Результат анализа RSI
        """
        try:
            # Определение зон
            if rsi_value <= self.rsi_oversold:
                signal = SignalType.BUY
                reason = f"RSI в зоне перепроданности ({rsi_value:.1f})"
                strength = (self.rsi_oversold - rsi_value) / self.rsi_oversold
            elif rsi_value >= self.rsi_overbought:
                signal = SignalType.SELL
                reason = f"RSI в зоне перекупленности ({rsi_value:.1f})"
                strength = (rsi_value - self.rsi_overbought) / (100 - self.rsi_overbought)
            else:
                signal = SignalType.HOLD
                reason = f"RSI в нейтральной зоне ({rsi_value:.1f})"
                strength = 0.0
            
            # Анализ дивергенции (если есть достаточно данных)
            divergence = self._detect_rsi_divergence() if len(self.rsi_history) > 10 else None
            
            return {
                'signal': signal,
                'strength': min(strength, 1.0),
                'reason': reason,
                'zone': self._get_rsi_zone(rsi_value),
                'divergence': divergence
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа RSI: {e}")
            return {'signal': SignalType.HOLD, 'strength': 0.0, 'reason': 'Ошибка анализа RSI'}
    
    def _analyze_macd(self, macd_data: Dict[str, float]) -> Dict[str, Any]:
        """
        Анализ MACD сигналов
        
        Args:
            macd_data: Данные MACD
            
        Returns:
            Результат анализа MACD
        """
        try:
            macd_line = macd_data['macd_line']
            signal_line = macd_data['signal_line']
            histogram = macd_data['histogram']
            
            # Анализ пересечения MACD и сигнальной линии
            crossover_signal = self._analyze_macd_crossover()
            
            # Анализ гистограммы
            histogram_signal = self._analyze_macd_histogram(histogram)
            
            # Комбинирование сигналов MACD
            if crossover_signal['signal'] != SignalType.HOLD:
                main_signal = crossover_signal['signal']
                reason = crossover_signal['reason']
                strength = crossover_signal['strength']
            elif histogram_signal['signal'] != SignalType.HOLD:
                main_signal = histogram_signal['signal']
                reason = histogram_signal['reason']
                strength = histogram_signal['strength']
            else:
                main_signal = SignalType.HOLD
                reason = "Нет четких сигналов MACD"
                strength = 0.0
            
            return {
                'signal': main_signal,
                'strength': strength,
                'reason': reason,
                'crossover': crossover_signal,
                'histogram_analysis': histogram_signal,
                'macd_above_signal': macd_line > signal_line
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа MACD: {e}")
            return {'signal': SignalType.HOLD, 'strength': 0.0, 'reason': 'Ошибка анализа MACD'}
    
    def _analyze_macd_crossover(self) -> Dict[str, Any]:
        """
        Анализ пересечений MACD и сигнальной линии
        
        Returns:
            Результат анализа пересечений
        """
        try:
            if len(self.macd_line_history) < 2 or len(self.macd_signal_history) < 2:
                return {'signal': SignalType.HOLD, 'strength': 0.0, 'reason': 'Недостаточно данных'}
            
            # Текущие и предыдущие значения
            macd_current = self.macd_line_history[-1]
            macd_previous = self.macd_line_history[-2]
            signal_current = self.macd_signal_history[-1]
            signal_previous = self.macd_signal_history[-2]
            
            # Проверка пересечений
            bullish_cross = (macd_previous <= signal_previous and macd_current > signal_current)
            bearish_cross = (macd_previous >= signal_previous and macd_current < signal_current)
            
            if bullish_cross:
                strength = abs(macd_current - signal_current) / abs(signal_current) if signal_current != 0 else 0.5
                return {
                    'signal': SignalType.BUY,
                    'strength': min(strength, 1.0),
                    'reason': 'Бычье пересечение MACD'
                }
            elif bearish_cross:
                strength = abs(macd_current - signal_current) / abs(signal_current) if signal_current != 0 else 0.5
                return {
                    'signal': SignalType.SELL,
                    'strength': min(strength, 1.0),
                    'reason': 'Медвежье пересечение MACD'
                }
            
            return {'signal': SignalType.HOLD, 'strength': 0.0, 'reason': 'Нет пересечений'}
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа пересечений MACD: {e}")
            return {'signal': SignalType.HOLD, 'strength': 0.0, 'reason': 'Ошибка анализа'}
    
    def _analyze_macd_histogram(self, histogram: float) -> Dict[str, Any]:
        """
        Анализ гистограммы MACD
        
        Args:
            histogram: Текущее значение гистограммы
            
        Returns:
            Результат анализа гистограммы
        """
        try:
            if len(self.macd_histogram_history) < 3:
                return {'signal': SignalType.HOLD, 'strength': 0.0, 'reason': 'Недостаточно данных'}
            
            # Анализ тренда гистограммы
            recent_histogram = self.macd_histogram_history[-3:]
            
            # Проверка на усиление сигнала
            if all(h > 0 for h in recent_histogram) and all(recent_histogram[i] > recent_histogram[i-1] for i in range(1, len(recent_histogram))):
                if histogram > self.min_macd_histogram:
                    return {
                        'signal': SignalType.BUY,
                        'strength': min(histogram / self.min_macd_histogram, 1.0),
                        'reason': 'Усиление бычьего импульса MACD'
                    }
            
            elif all(h < 0 for h in recent_histogram) and all(recent_histogram[i] < recent_histogram[i-1] for i in range(1, len(recent_histogram))):
                if abs(histogram) > self.min_macd_histogram:
                    return {
                        'signal': SignalType.SELL,
                        'strength': min(abs(histogram) / self.min_macd_histogram, 1.0),
                        'reason': 'Усиление медвежьего импульса MACD'
                    }
            
            return {'signal': SignalType.HOLD, 'strength': 0.0, 'reason': 'Слабый сигнал гистограммы'}
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа гистограммы MACD: {e}")
            return {'signal': SignalType.HOLD, 'strength': 0.0, 'reason': 'Ошибка анализа'}
    
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
            
            # Подтверждение при объеме выше среднего
            confirmed = volume_ratio >= 1.1
            
            return {
                'confirmed': confirmed,
                'ratio': volume_ratio,
                'current_volume': current_volume,
                'avg_volume': avg_volume
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа объема: {e}")
            return {'confirmed': True, 'ratio': 1.0}
    
    def _analyze_trend(self) -> Dict[str, Any]:
        """
        Анализ общего тренда
        
        Returns:
            Результат анализа тренда
        """
        try:
            if len(self.price_history) < 20:
                return {'direction': 'neutral', 'strength': 0.0}
            
            # Простой анализ тренда по скользящим средним
            short_ma = sum(self.price_history[-10:]) / 10
            long_ma = sum(self.price_history[-20:]) / 20
            
            if short_ma > long_ma * 1.005:  # 0.5% разница
                direction = 'up'
                strength = (short_ma - long_ma) / long_ma
            elif short_ma < long_ma * 0.995:
                direction = 'down'
                strength = (long_ma - short_ma) / long_ma
            else:
                direction = 'neutral'
                strength = 0.0
            
            return {
                'direction': direction,
                'strength': min(strength, 1.0),
                'short_ma': short_ma,
                'long_ma': long_ma
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа тренда: {e}")
            return {'direction': 'neutral', 'strength': 0.0}
    
    def _combine_signals(self, rsi_signal: SignalType, macd_signal: SignalType, trend_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Комбинирование сигналов RSI и MACD
        
        Args:
            rsi_signal: Сигнал RSI
            macd_signal: Сигнал MACD
            trend_analysis: Анализ тренда
            
        Returns:
            Комбинированный сигнал
        """
        try:
            # Если оба сигнала совпадают
            if rsi_signal == macd_signal and rsi_signal != SignalType.HOLD:
                # Проверка соответствия тренду
                if self.trend_filter:
                    trend_direction = trend_analysis['direction']
                    if ((rsi_signal == SignalType.BUY and trend_direction == 'up') or
                        (rsi_signal == SignalType.SELL and trend_direction == 'down') or
                        trend_direction == 'neutral'):
                        return {'signal': rsi_signal, 'reason': 'Подтверждение RSI и MACD'}
                    else:
                        return {'signal': SignalType.HOLD, 'reason': 'Сигнал против тренда'}
                else:
                    return {'signal': rsi_signal, 'reason': 'Подтверждение RSI и MACD'}
            
            # Если сигналы противоречат друг другу
            elif rsi_signal != SignalType.HOLD and macd_signal != SignalType.HOLD and rsi_signal != macd_signal:
                return {'signal': SignalType.HOLD, 'reason': 'Противоречивые сигналы RSI и MACD'}
            
            # Если только один индикатор дает сигнал
            elif rsi_signal != SignalType.HOLD:
                return {'signal': rsi_signal, 'reason': 'Сигнал только от RSI'}
            elif macd_signal != SignalType.HOLD:
                return {'signal': macd_signal, 'reason': 'Сигнал только от MACD'}
            
            # Нет сигналов
            return {'signal': SignalType.HOLD, 'reason': 'Нет сигналов от индикаторов'}
            
        except Exception as e:
            self.logger.error(f"Ошибка комбинирования сигналов: {e}")
            return {'signal': SignalType.HOLD, 'reason': 'Ошибка комбинирования'}
    
    def _calculate_combined_strength(self, rsi_analysis: Dict[str, Any], macd_analysis: Dict[str, Any], 
                                   volume_analysis: Dict[str, Any], trend_analysis: Dict[str, Any]) -> float:
        """
        Расчет комбинированной силы сигнала
        
        Args:
            rsi_analysis: Анализ RSI
            macd_analysis: Анализ MACD
            volume_analysis: Анализ объема
            trend_analysis: Анализ тренда
            
        Returns:
            Сила сигнала (0.0 - 1.0)
        """
        try:
            # Базовая сила от индикаторов
            rsi_strength = rsi_analysis.get('strength', 0.0)
            macd_strength = macd_analysis.get('strength', 0.0)
            
            # Средняя сила индикаторов
            base_strength = (rsi_strength + macd_strength) / 2
            
            # Корректировка на объем
            volume_multiplier = min(volume_analysis.get('ratio', 1.0), 1.5)
            
            # Корректировка на тренд
            trend_multiplier = 1.0
            if trend_analysis['direction'] != 'neutral':
                trend_multiplier = 1.0 + (trend_analysis.get('strength', 0.0) * 0.3)
            
            # Итоговая сила
            final_strength = base_strength * volume_multiplier * trend_multiplier
            
            return min(final_strength, 1.0)
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы сигнала: {e}")
            return 0.0
    
    def _get_rsi_zone(self, rsi_value: float) -> str:
        """
        Определение зоны RSI
        
        Args:
            rsi_value: Значение RSI
            
        Returns:
            Название зоны
        """
        if rsi_value <= self.rsi_oversold:
            return 'oversold'
        elif rsi_value >= self.rsi_overbought:
            return 'overbought'
        elif rsi_value < 50:
            return 'bearish'
        else:
            return 'bullish'
    
    def _detect_rsi_divergence(self) -> Optional[Dict[str, Any]]:
        """
        Обнаружение дивергенции RSI
        
        Returns:
            Информация о дивергенции или None
        """
        try:
            # Простая проверка дивергенции (требует более сложной реализации)
            if len(self.rsi_history) < 10 or len(self.price_history) < 10:
                return None
            
            # Здесь должна быть более сложная логика обнаружения дивергенции
            # Пока возвращаем None
            return None
            
        except Exception as e:
            self.logger.error(f"Ошибка обнаружения дивергенции: {e}")
            return None