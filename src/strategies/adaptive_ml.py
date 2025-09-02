#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Адаптивная ML стратегия

Использует машинное обучение для адаптации к изменяющимся рыночным условиям
и генерации торговых сигналов на основе множественных индикаторов.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import json
import statistics

from .base_strategy import BaseStrategy, SignalType

class AdaptiveMLStrategy(BaseStrategy):
    """
    Адаптивная ML стратегия
    
    Параметры:
    - feature_window: Окно для расчета признаков (по умолчанию 50)
    - prediction_horizon: Горизонт прогнозирования (по умолчанию 5)
    - confidence_threshold: Порог уверенности для сигналов (по умолчанию 0.6)
    - adaptation_period: Период адаптации модели (по умолчанию 100)
    - use_technical_indicators: Использовать технические индикаторы
    - use_market_regime: Использовать определение рыночного режима
    - use_sentiment_analysis: Использовать анализ настроений
    - risk_adjustment: Корректировка на риск
    """
    
    def __init__(self, name: str, config: Dict[str, Any], api_client, db_manager, config_manager):
        super().__init__(name, config, api_client, db_manager, config_manager)
        
        # Параметры стратегии из конфигурации
        self.feature_window = config.get('feature_window', 50)
        self.prediction_horizon = config.get('prediction_horizon', 5)
        self.confidence_threshold = config.get('confidence_threshold', 0.6)
        self.adaptation_period = config.get('adaptation_period', 100)
        self.use_technical_indicators = config.get('use_technical_indicators', True)
        self.use_market_regime = config.get('use_market_regime', True)
        self.use_sentiment_analysis = config.get('use_sentiment_analysis', False)
        self.risk_adjustment = config.get('risk_adjustment', True)
        
        # Параметры технических индикаторов
        self.rsi_period = config.get('rsi_period', 14)
        self.macd_fast = config.get('macd_fast', 12)
        self.macd_slow = config.get('macd_slow', 26)
        self.macd_signal = config.get('macd_signal', 9)
        self.bb_period = config.get('bb_period', 20)
        self.bb_std = config.get('bb_std', 2.0)
        
        # Валидация параметров
        if self.feature_window < 20:
            raise ValueError("Окно признаков должно быть не менее 20")
        
        if self.confidence_threshold < 0.5 or self.confidence_threshold > 1.0:
            raise ValueError("Порог уверенности должен быть между 0.5 и 1.0")
        
        # Буферы данных
        self.price_history: List[float] = []
        self.volume_history: List[float] = []
        self.high_history: List[float] = []
        self.low_history: List[float] = []
        self.timestamp_history: List[datetime] = []
        
        # Кэш признаков и предсказаний
        self.feature_cache: Dict[str, List[float]] = {}
        self.prediction_cache: List[Dict[str, Any]] = []
        self.model_performance: Dict[str, float] = {
            'accuracy': 0.5,
            'precision': 0.5,
            'recall': 0.5,
            'f1_score': 0.5
        }
        
        # Состояние модели
        self.model_trained = False
        self.last_adaptation = None
        self.market_regime = 'unknown'
        self.regime_confidence = 0.0
        
        # Статистика
        self.correct_predictions = 0
        self.total_predictions = 0
        self.adaptation_count = 0
        
        # Максимальный размер буферов
        self.max_buffer_size = max(self.feature_window * 4, 500)
        
        self.logger.info(f"Инициализирована адаптивная ML стратегия: окно={self.feature_window}, порог={self.confidence_threshold}")
    
    def analyze_market(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализ рыночных данных с использованием ML
        
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
            if len(self.price_history) < self.feature_window:
                return {
                    'status': 'insufficient_data',
                    'required': self.feature_window,
                    'available': len(self.price_history)
                }
            
            # Извлечение признаков
            features = self._extract_features()
            
            # Определение рыночного режима
            market_regime_analysis = self._analyze_market_regime()
            
            # Анализ технических индикаторов
            technical_analysis = self._analyze_technical_indicators()
            
            # ML предсказание
            ml_prediction = self._make_ml_prediction(features)
            
            # Анализ уверенности модели
            confidence_analysis = self._analyze_model_confidence()
            
            # Проверка необходимости адаптации
            adaptation_analysis = self._check_adaptation_needed()
            
            return {
                'status': 'success',
                'current_price': current_price,
                'features': features,
                'market_regime': market_regime_analysis,
                'technical_analysis': technical_analysis,
                'ml_prediction': ml_prediction,
                'confidence_analysis': confidence_analysis,
                'adaptation_analysis': adaptation_analysis,
                'model_performance': self.model_performance,
                'data_points': len(self.price_history)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа рынка: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def generate_signal(self, analysis: Dict[str, Any]) -> Tuple[SignalType, float]:
        """
        Генерация торгового сигнала на основе ML анализа
        
        Args:
            analysis: Результат анализа рынка
            
        Returns:
            Торговый сигнал
        """
        try:
            if analysis.get('status') != 'success':
                return (SignalType.HOLD, 0.0)
            
            ml_prediction = analysis['ml_prediction']
            confidence_analysis = analysis['confidence_analysis']
            market_regime = analysis['market_regime']
            technical_analysis = analysis['technical_analysis']
            
            # Проверка уверенности модели
            if confidence_analysis['overall_confidence'] < self.confidence_threshold:
                return (SignalType.HOLD, 0.0)
            
            # Проверка необходимости адаптации
            if analysis['adaptation_analysis']['needs_adaptation']:
                self._adapt_model(analysis)
                return (SignalType.HOLD, 0.0)
            
            # Генерация базового сигнала
            base_signal = self._generate_base_signal(ml_prediction, market_regime)
            
            # Корректировка сигнала техническими индикаторами
            adjusted_signal = self._adjust_signal_with_technicals(base_signal, technical_analysis)
            
            # Корректировка на рыночный режим
            regime_adjusted_signal = self._adjust_signal_for_regime(adjusted_signal, market_regime)
            
            # Корректировка на риск
            if self.risk_adjustment:
                final_signal = self._adjust_signal_for_risk(regime_adjusted_signal, analysis)
            else:
                final_signal = regime_adjusted_signal
            
            # Расчет итоговой силы сигнала
            signal_strength = self._calculate_final_signal_strength(
                final_signal, confidence_analysis, market_regime, technical_analysis
            )
            
            # Обновление статистики предсказаний
            if isinstance(final_signal, dict) and 'signal' in final_signal:
                self._update_prediction_stats(final_signal)
                signal_type = final_signal['signal']
            else:
                # Создаем временный объект для статистики
                temp_signal_data = {
                    'signal': SignalType.HOLD,
                    'confidence': signal_strength
                }
                self._update_prediction_stats(temp_signal_data)
                signal_type = SignalType.HOLD
            
            return (signal_type, signal_strength)
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации сигнала: {e}")
            return (SignalType.HOLD, 0.0)
    
    def get_strategy_description(self) -> str:
        """
        Получение описания стратегии
        
        Returns:
            Человекочитаемое описание стратегии
        """
        return f"""Адаптивная ML стратегия '{self.name}'
        
Описание: Использует машинное обучение для адаптации к изменяющимся рыночным условиям.
Автоматически анализирует исторические данные и обучается на опыте торговли.
        
Параметры:
- Окно признаков: {self.feature_window}
- Горизонт прогнозирования: {self.prediction_horizon}
- Порог уверенности: {self.confidence_threshold}
- Период адаптации: {self.adaptation_period}
- Технические индикаторы: {'Да' if self.use_technical_indicators else 'Нет'}
- Анализ рыночного режима: {'Да' if self.use_market_regime else 'Нет'}
        
Особенности:
- Автоматическая адаптация к рынку
- Множественные технические индикаторы
- Определение рыночного режима
- Управление уверенностью модели
- Динамическая корректировка параметров
        
Подходит для: всех рыночных условий, адаптивной торговли, сложных паттернов
Не подходит для: очень низкой ликвидности, экстремальных скачков волатильности"""
    
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
            new_timestamps = []
            
            for kline in klines:
                if isinstance(kline, list) and len(kline) >= 6:
                    timestamp = datetime.fromtimestamp(int(kline[0]) / 1000)
                    open_price = float(kline[1])
                    high_price = float(kline[2])
                    low_price = float(kline[3])
                    close_price = float(kline[4])
                    volume = float(kline[5])
                    
                    new_timestamps.append(timestamp)
                    new_prices.append(close_price)
                    new_volumes.append(volume)
                    new_highs.append(high_price)
                    new_lows.append(low_price)
            
            # Обновление буферов
            self.timestamp_history.extend(new_timestamps)
            self.price_history.extend(new_prices)
            self.volume_history.extend(new_volumes)
            self.high_history.extend(new_highs)
            self.low_history.extend(new_lows)
            
            # Ограничение размера буферов
            if len(self.price_history) > self.max_buffer_size:
                excess = len(self.price_history) - self.max_buffer_size
                self.timestamp_history = self.timestamp_history[excess:]
                self.price_history = self.price_history[excess:]
                self.volume_history = self.volume_history[excess:]
                self.high_history = self.high_history[excess:]
                self.low_history = self.low_history[excess:]
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления истории данных: {e}")
    
    def _extract_features(self) -> Dict[str, Any]:
        """
        Извлечение признаков для ML модели
        
        Returns:
            Словарь признаков
        """
        try:
            features = {}
            
            if len(self.price_history) < self.feature_window:
                return features
            
            recent_prices = self.price_history[-self.feature_window:]
            recent_volumes = self.volume_history[-self.feature_window:]
            recent_highs = self.high_history[-self.feature_window:]
            recent_lows = self.low_history[-self.feature_window:]
            
            # Ценовые признаки
            features.update(self._extract_price_features(recent_prices))
            
            # Объемные признаки
            features.update(self._extract_volume_features(recent_volumes))
            
            # Признаки волатильности
            features.update(self._extract_volatility_features(recent_prices, recent_highs, recent_lows))
            
            # Технические индикаторы как признаки
            if self.use_technical_indicators:
                features.update(self._extract_technical_features(recent_prices, recent_volumes))
            
            # Временные признаки
            features.update(self._extract_temporal_features())
            
            # Кэширование признаков
            for key, value in features.items():
                if key not in self.feature_cache:
                    self.feature_cache[key] = []
                self.feature_cache[key].append(value)
                
                # Ограничение размера кэша
                if len(self.feature_cache[key]) > self.max_buffer_size:
                    self.feature_cache[key] = self.feature_cache[key][-self.max_buffer_size:]
            
            return features
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения признаков: {e}")
            return {}
    
    def _extract_price_features(self, prices: List[float]) -> Dict[str, float]:
        """
        Извлечение ценовых признаков
        
        Args:
            prices: Список цен
            
        Returns:
            Ценовые признаки
        """
        try:
            if len(prices) < 5:
                return {}
            
            current_price = prices[-1]
            
            # Доходности
            returns_1 = (prices[-1] - prices[-2]) / prices[-2] if len(prices) >= 2 else 0
            returns_5 = (prices[-1] - prices[-6]) / prices[-6] if len(prices) >= 6 else 0
            returns_10 = (prices[-1] - prices[-11]) / prices[-11] if len(prices) >= 11 else 0
            
            # Скользящие средние
            sma_5 = sum(prices[-5:]) / 5 if len(prices) >= 5 else current_price
            sma_10 = sum(prices[-10:]) / 10 if len(prices) >= 10 else current_price
            sma_20 = sum(prices[-20:]) / 20 if len(prices) >= 20 else current_price
            
            # Отношения к скользящим средним
            price_to_sma5 = current_price / sma_5 - 1
            price_to_sma10 = current_price / sma_10 - 1
            price_to_sma20 = current_price / sma_20 - 1
            
            # Статистические характеристики
            price_std = statistics.stdev(prices[-20:]) if len(prices) >= 20 else 0
            price_mean = statistics.mean(prices[-20:]) if len(prices) >= 20 else current_price
            price_zscore = (current_price - price_mean) / price_std if price_std > 0 else 0
            
            return {
                'returns_1': returns_1,
                'returns_5': returns_5,
                'returns_10': returns_10,
                'price_to_sma5': price_to_sma5,
                'price_to_sma10': price_to_sma10,
                'price_to_sma20': price_to_sma20,
                'price_zscore': price_zscore,
                'price_volatility': price_std / price_mean if price_mean > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения ценовых признаков: {e}")
            return {}
    
    def _extract_volume_features(self, volumes: List[float]) -> Dict[str, float]:
        """
        Извлечение объемных признаков
        
        Args:
            volumes: Список объемов
            
        Returns:
            Объемные признаки
        """
        try:
            if len(volumes) < 5:
                return {}
            
            current_volume = volumes[-1]
            
            # Средние объемы
            avg_volume_5 = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else current_volume
            avg_volume_10 = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else current_volume
            avg_volume_20 = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else current_volume
            
            # Отношения объемов
            volume_ratio_5 = current_volume / avg_volume_5 if avg_volume_5 > 0 else 1
            volume_ratio_10 = current_volume / avg_volume_10 if avg_volume_10 > 0 else 1
            volume_ratio_20 = current_volume / avg_volume_20 if avg_volume_20 > 0 else 1
            
            # Тренд объема
            volume_trend = 0
            if len(volumes) >= 5:
                recent_avg = sum(volumes[-3:]) / 3
                older_avg = sum(volumes[-6:-3]) / 3
                volume_trend = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
            
            return {
                'volume_ratio_5': volume_ratio_5,
                'volume_ratio_10': volume_ratio_10,
                'volume_ratio_20': volume_ratio_20,
                'volume_trend': volume_trend
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения объемных признаков: {e}")
            return {}
    
    def _extract_volatility_features(self, prices: List[float], highs: List[float], lows: List[float]) -> Dict[str, float]:
        """
        Извлечение признаков волатильности
        
        Args:
            prices: Список цен закрытия
            highs: Список максимумов
            lows: Список минимумов
            
        Returns:
            Признаки волатильности
        """
        try:
            if len(prices) < 10:
                return {}
            
            # True Range
            true_ranges = []
            for i in range(1, min(len(prices), len(highs), len(lows))):
                tr1 = highs[i] - lows[i]
                tr2 = abs(highs[i] - prices[i-1])
                tr3 = abs(lows[i] - prices[i-1])
                true_ranges.append(max(tr1, tr2, tr3))
            
            # Average True Range
            atr_14 = sum(true_ranges[-14:]) / min(len(true_ranges), 14) if true_ranges else 0
            atr_7 = sum(true_ranges[-7:]) / min(len(true_ranges), 7) if true_ranges else 0
            
            # Волатильность доходностей
            returns = []
            for i in range(1, len(prices)):
                returns.append((prices[i] - prices[i-1]) / prices[i-1])
            
            volatility_10 = statistics.stdev(returns[-10:]) if len(returns) >= 10 else 0
            volatility_20 = statistics.stdev(returns[-20:]) if len(returns) >= 20 else 0
            
            # Отношение волатильностей
            volatility_ratio = volatility_10 / volatility_20 if volatility_20 > 0 else 1
            
            return {
                'atr_14': atr_14 / prices[-1] if prices[-1] > 0 else 0,  # Нормализованный ATR
                'atr_7': atr_7 / prices[-1] if prices[-1] > 0 else 0,
                'volatility_10': volatility_10,
                'volatility_20': volatility_20,
                'volatility_ratio': volatility_ratio
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения признаков волатильности: {e}")
            return {}
    
    def _extract_technical_features(self, prices: List[float], volumes: List[float]) -> Dict[str, float]:
        """
        Извлечение признаков технических индикаторов
        
        Args:
            prices: Список цен
            volumes: Список объемов
            
        Returns:
            Технические признаки
        """
        try:
            features = {}
            
            if len(prices) < self.rsi_period:
                return features
            
            # RSI
            rsi = self._calculate_rsi(prices)
            features['rsi'] = rsi
            features['rsi_oversold'] = 1 if rsi < 30 else 0
            features['rsi_overbought'] = 1 if rsi > 70 else 0
            
            # MACD
            if len(prices) >= self.macd_slow:
                macd_line, macd_signal, macd_histogram = self._calculate_macd(prices)
                features['macd_line'] = macd_line
                features['macd_signal'] = macd_signal
                features['macd_histogram'] = macd_histogram
                features['macd_bullish'] = 1 if macd_line > macd_signal else 0
            
            # Bollinger Bands
            if len(prices) >= self.bb_period:
                bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(prices)
                current_price = prices[-1]
                features['bb_position'] = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
                features['bb_squeeze'] = 1 if (bb_upper - bb_lower) / bb_middle < 0.1 else 0
            
            return features
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения технических признаков: {e}")
            return {}
    
    def _extract_temporal_features(self) -> Dict[str, float]:
        """
        Извлечение временных признаков
        
        Returns:
            Временные признаки
        """
        try:
            if not self.timestamp_history:
                return {}
            
            current_time = self.timestamp_history[-1]
            
            # Час дня (0-23)
            hour_of_day = current_time.hour
            
            # День недели (0-6)
            day_of_week = current_time.weekday()
            
            # Синусоидальное кодирование времени
            hour_sin = np.sin(2 * np.pi * hour_of_day / 24)
            hour_cos = np.cos(2 * np.pi * hour_of_day / 24)
            day_sin = np.sin(2 * np.pi * day_of_week / 7)
            day_cos = np.cos(2 * np.pi * day_of_week / 7)
            
            return {
                'hour_sin': hour_sin,
                'hour_cos': hour_cos,
                'day_sin': day_sin,
                'day_cos': day_cos,
                'is_weekend': 1 if day_of_week >= 5 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка извлечения временных признаков: {e}")
            return {}
    
    def _analyze_market_regime(self) -> Dict[str, Any]:
        """
        Определение рыночного режима
        
        Returns:
            Анализ рыночного режима
        """
        try:
            if len(self.price_history) < 50:
                return {
                    'regime': 'unknown',
                    'confidence': 0.0,
                    'trend_strength': 0.0,
                    'volatility_regime': 'normal'
                }
            
            recent_prices = self.price_history[-50:]
            
            # Анализ тренда
            trend_strength = self._calculate_trend_strength(recent_prices)
            
            # Анализ волатильности
            returns = [(recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1] 
                      for i in range(1, len(recent_prices))]
            volatility = statistics.stdev(returns) if len(returns) > 1 else 0
            
            # Определение режима
            if abs(trend_strength) > 3.0:
                if trend_strength > 0:
                    regime = 'bull_trend'
                else:
                    regime = 'bear_trend'
                confidence = min(abs(trend_strength) / 5.0, 1.0)
            elif volatility > 0.03:  # 3% дневная волатильность
                regime = 'high_volatility'
                confidence = min(volatility / 0.05, 1.0)
            elif volatility < 0.01:  # 1% дневная волатильность
                regime = 'low_volatility'
                confidence = min((0.02 - volatility) / 0.01, 1.0)
            else:
                regime = 'sideways'
                confidence = 0.6
            
            # Определение режима волатильности
            if volatility > 0.04:
                volatility_regime = 'high'
            elif volatility < 0.01:
                volatility_regime = 'low'
            else:
                volatility_regime = 'normal'
            
            # Обновление состояния
            self.market_regime = regime
            self.regime_confidence = confidence
            
            return {
                'regime': regime,
                'confidence': confidence,
                'trend_strength': trend_strength,
                'volatility': volatility,
                'volatility_regime': volatility_regime
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа рыночного режима: {e}")
            return {'regime': 'unknown', 'confidence': 0.0}
    
    def _analyze_technical_indicators(self) -> Dict[str, Any]:
        """
        Анализ технических индикаторов
        
        Returns:
            Результат анализа технических индикаторов
        """
        try:
            if len(self.price_history) < max(self.rsi_period, self.macd_slow, self.bb_period):
                return {'status': 'insufficient_data'}
            
            analysis = {'status': 'success'}
            
            # RSI анализ
            rsi = self._calculate_rsi(self.price_history)
            analysis['rsi'] = {
                'value': rsi,
                'signal': 'oversold' if rsi < 30 else 'overbought' if rsi > 70 else 'neutral',
                'strength': abs(rsi - 50) / 50
            }
            
            # MACD анализ
            macd_line, macd_signal_line, macd_histogram = self._calculate_macd(self.price_history)
            analysis['macd'] = {
                'line': macd_line,
                'signal': macd_signal_line,
                'histogram': macd_histogram,
                'trend': 'bullish' if macd_line > macd_signal_line else 'bearish',
                'strength': abs(macd_histogram) / max(abs(macd_line), abs(macd_signal_line), 0.001)
            }
            
            # Bollinger Bands анализ
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(self.price_history)
            current_price = self.price_history[-1]
            bb_position = (current_price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
            
            analysis['bollinger_bands'] = {
                'upper': bb_upper,
                'middle': bb_middle,
                'lower': bb_lower,
                'position': bb_position,
                'signal': 'oversold' if bb_position < 0.2 else 'overbought' if bb_position > 0.8 else 'neutral',
                'squeeze': (bb_upper - bb_lower) / bb_middle < 0.1
            }
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа технических индикаторов: {e}")
            return {'status': 'error', 'error': str(e)}
    
    def _make_ml_prediction(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Создание ML предсказания (упрощенная версия)
        
        Args:
            features: Признаки для предсказания
            
        Returns:
            ML предсказание
        """
        try:
            if not features:
                return {
                    'prediction': 'hold',
                    'confidence': 0.0,
                    'probability': {'buy': 0.33, 'sell': 0.33, 'hold': 0.34}
                }
            
            # Упрощенная логика предсказания на основе признаков
            # В реальной реализации здесь был бы обученный ML алгоритм
            
            score = 0.0
            weight_sum = 0.0
            
            # Ценовые сигналы
            if 'returns_1' in features:
                score += features['returns_1'] * 10  # Краткосрочный моментум
                weight_sum += 1
            
            if 'price_to_sma5' in features:
                score += features['price_to_sma5'] * 5  # Отношение к SMA
                weight_sum += 1
            
            if 'rsi' in features:
                rsi = features['rsi']
                if rsi < 30:
                    score += 0.3  # Сигнал покупки
                elif rsi > 70:
                    score -= 0.3  # Сигнал продажи
                weight_sum += 1
            
            if 'macd_histogram' in features:
                score += features['macd_histogram'] * 2
                weight_sum += 1
            
            if 'bb_position' in features:
                bb_pos = features['bb_position']
                if bb_pos < 0.2:
                    score += 0.2  # Сигнал покупки
                elif bb_pos > 0.8:
                    score -= 0.2  # Сигнал продажи
                weight_sum += 1
            
            # Нормализация
            if weight_sum > 0:
                score = score / weight_sum
            
            # Преобразование в вероятности
            if score > 0.1:
                prediction = 'buy'
                buy_prob = min(0.5 + score, 0.8)
                sell_prob = max(0.1, 0.3 - score)
                hold_prob = 1.0 - buy_prob - sell_prob
            elif score < -0.1:
                prediction = 'sell'
                sell_prob = min(0.5 - score, 0.8)
                buy_prob = max(0.1, 0.3 + score)
                hold_prob = 1.0 - buy_prob - sell_prob
            else:
                prediction = 'hold'
                hold_prob = 0.6
                buy_prob = 0.2
                sell_prob = 0.2
            
            confidence = max(buy_prob, sell_prob, hold_prob)
            
            return {
                'prediction': prediction,
                'confidence': confidence,
                'probability': {
                    'buy': buy_prob,
                    'sell': sell_prob,
                    'hold': hold_prob
                },
                'score': score,
                'features_used': len(features)
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка ML предсказания: {e}")
            return {
                'prediction': 'hold',
                'confidence': 0.0,
                'probability': {'buy': 0.33, 'sell': 0.33, 'hold': 0.34}
            }
    
    def _analyze_model_confidence(self) -> Dict[str, Any]:
        """
        Анализ уверенности модели
        
        Returns:
            Анализ уверенности
        """
        try:
            # Базовая уверенность на основе производительности модели
            base_confidence = self.model_performance['accuracy']
            
            # Корректировка на количество данных
            data_confidence = min(len(self.price_history) / self.feature_window, 1.0)
            
            # Корректировка на стабильность рынка
            if len(self.price_history) >= 20:
                recent_volatility = statistics.stdev([
                    (self.price_history[i] - self.price_history[i-1]) / self.price_history[i-1]
                    for i in range(-20, 0)
                ])
                stability_confidence = max(0.3, 1.0 - recent_volatility * 20)
            else:
                stability_confidence = 0.5
            
            # Корректировка на время с последней адаптации
            if self.last_adaptation:
                time_since_adaptation = (datetime.now() - self.last_adaptation).total_seconds() / 3600
                adaptation_confidence = max(0.5, 1.0 - time_since_adaptation / 24)  # Снижение за 24 часа
            else:
                adaptation_confidence = 0.7  # Средняя уверенность без адаптации
            
            # Общая уверенность
            overall_confidence = (
                base_confidence * 0.4 +
                data_confidence * 0.2 +
                stability_confidence * 0.2 +
                adaptation_confidence * 0.2
            )
            
            return {
                'overall_confidence': overall_confidence,
                'base_confidence': base_confidence,
                'data_confidence': data_confidence,
                'stability_confidence': stability_confidence,
                'adaptation_confidence': adaptation_confidence,
                'model_accuracy': self.model_performance['accuracy'],
                'predictions_made': self.total_predictions
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа уверенности модели: {e}")
            return {'overall_confidence': 0.5}
    
    def _check_adaptation_needed(self) -> Dict[str, Any]:
        """
        Проверка необходимости адаптации модели
        
        Returns:
            Результат проверки адаптации
        """
        try:
            needs_adaptation = False
            reasons = []
            
            # Проверка производительности
            if self.model_performance['accuracy'] < 0.45:
                needs_adaptation = True
                reasons.append(f"Низкая точность ({self.model_performance['accuracy']:.2f})")
            
            # Проверка времени с последней адаптации
            if self.last_adaptation:
                hours_since_adaptation = (datetime.now() - self.last_adaptation).total_seconds() / 3600
                if hours_since_adaptation > 48:  # 48 часов
                    needs_adaptation = True
                    reasons.append(f"Давно не адаптировалась ({hours_since_adaptation:.1f}ч)")
            elif self.total_predictions > self.adaptation_period:
                needs_adaptation = True
                reasons.append("Первая адаптация")
            
            # Проверка количества неправильных предсказаний подряд
            if hasattr(self, 'consecutive_wrong_predictions'):
                if self.consecutive_wrong_predictions > 5:
                    needs_adaptation = True
                    reasons.append(f"Много неправильных предсказаний подряд ({self.consecutive_wrong_predictions})")
            
            return {
                'needs_adaptation': needs_adaptation,
                'reasons': reasons,
                'last_adaptation': self.last_adaptation,
                'adaptation_count': self.adaptation_count
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка проверки адаптации: {e}")
            return {'needs_adaptation': False, 'reasons': []}
    
    def _adapt_model(self, analysis: Dict[str, Any]):
        """
        Адаптация модели (упрощенная версия)
        
        Args:
            analysis: Результат анализа рынка
        """
        try:
            self.logger.info("Начинается адаптация модели...")
            
            # В реальной реализации здесь было бы переобучение модели
            # Пока что просто обновляем параметры
            
            # Корректировка порога уверенности
            if self.model_performance['accuracy'] < 0.5:
                self.confidence_threshold = min(self.confidence_threshold + 0.05, 0.8)
            else:
                self.confidence_threshold = max(self.confidence_threshold - 0.02, 0.5)
            
            # Обновление статистики производительности (симуляция)
            # В реальности это было бы основано на фактических результатах
            market_regime = analysis.get('market_regime', {})
            if market_regime.get('confidence', 0) > 0.7:
                # Высокая уверенность в режиме - улучшаем производительность
                self.model_performance['accuracy'] = min(self.model_performance['accuracy'] + 0.05, 0.85)
            else:
                # Неопределенность - небольшое снижение
                self.model_performance['accuracy'] = max(self.model_performance['accuracy'] - 0.02, 0.4)
            
            # Обновление других метрик
            self.model_performance['precision'] = self.model_performance['accuracy'] * 0.95
            self.model_performance['recall'] = self.model_performance['accuracy'] * 0.9
            self.model_performance['f1_score'] = 2 * (self.model_performance['precision'] * self.model_performance['recall']) / \
                                                  (self.model_performance['precision'] + self.model_performance['recall'])
            
            # Обновление состояния
            self.last_adaptation = datetime.now()
            self.adaptation_count += 1
            self.model_trained = True
            
            self.logger.info(f"Адаптация завершена. Новая точность: {self.model_performance['accuracy']:.3f}, порог: {self.confidence_threshold:.3f}")
            
        except Exception as e:
            self.logger.error(f"Ошибка адаптации модели: {e}")
    
    def _generate_base_signal(self, ml_prediction: Dict[str, Any], market_regime: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерация базового сигнала на основе ML предсказания
        
        Args:
            ml_prediction: ML предсказание
            market_regime: Рыночный режим
            
        Returns:
            Базовый сигнал
        """
        try:
            prediction = ml_prediction['prediction']
            confidence = ml_prediction['confidence']
            
            if prediction == 'buy':
                signal = SignalType.BUY
                reason = f"ML предсказание: покупка (уверенность: {confidence:.2f})"
            elif prediction == 'sell':
                signal = SignalType.SELL
                reason = f"ML предсказание: продажа (уверенность: {confidence:.2f})"
            else:
                signal = SignalType.HOLD
                reason = f"ML предсказание: удержание (уверенность: {confidence:.2f})"
            
            return {
                'signal': signal,
                'reason': reason,
                'confidence': confidence,
                'ml_prediction': prediction
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка генерации базового сигнала: {e}")
            return {'signal': SignalType.HOLD, 'reason': 'Ошибка генерации сигнала'}
    
    def _adjust_signal_with_technicals(self, base_signal: Dict[str, Any], technical_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Корректировка сигнала техническими индикаторами
        
        Args:
            base_signal: Базовый сигнал
            technical_analysis: Технический анализ
            
        Returns:
            Скорректированный сигнал
        """
        try:
            if not self.use_technical_indicators or technical_analysis.get('status') != 'success':
                return base_signal
            
            if not isinstance(base_signal, dict) or 'signal' not in base_signal:
                return base_signal
                
            signal = base_signal['signal']
            reason = base_signal.get('reason', 'Неизвестная причина')
            
            # Проверка RSI
            rsi_analysis = technical_analysis.get('rsi', {})
            if rsi_analysis.get('signal') == 'oversold' and signal == SignalType.SELL:
                signal = SignalType.HOLD
                reason += "; RSI перепродан - отмена продажи"
            elif rsi_analysis.get('signal') == 'overbought' and signal == SignalType.BUY:
                signal = SignalType.HOLD
                reason += "; RSI перекуплен - отмена покупки"
            
            # Проверка MACD
            macd_analysis = technical_analysis.get('macd', {})
            if macd_analysis.get('trend') == 'bearish' and signal == SignalType.BUY:
                if macd_analysis.get('strength', 0) > 0.5:
                    signal = SignalType.HOLD
                    reason += "; MACD медвежий - отмена покупки"
            elif macd_analysis.get('trend') == 'bullish' and signal == SignalType.SELL:
                if macd_analysis.get('strength', 0) > 0.5:
                    signal = SignalType.HOLD
                    reason += "; MACD бычий - отмена продажи"
            
            # Проверка Bollinger Bands
            bb_analysis = technical_analysis.get('bollinger_bands', {})
            if bb_analysis.get('signal') == 'oversold' and signal == SignalType.SELL:
                signal = SignalType.HOLD
                reason += "; BB перепродан - отмена продажи"
            elif bb_analysis.get('signal') == 'overbought' and signal == SignalType.BUY:
                signal = SignalType.HOLD
                reason += "; BB перекуплен - отмена покупки"
            
            return {
                'signal': signal,
                'reason': reason,
                'confidence': base_signal['confidence'],
                'technical_adjustment': True
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка корректировки сигнала техническими индикаторами: {e}")
            return base_signal
    
    def _adjust_signal_for_regime(self, signal_data: Dict[str, Any], market_regime: Dict[str, Any]) -> Dict[str, Any]:
        """
        Корректировка сигнала на рыночный режим
        
        Args:
            signal_data: Данные сигнала
            market_regime: Рыночный режим
            
        Returns:
            Скорректированный сигнал
        """
        try:
            if not self.use_market_regime:
                return signal_data
            
            if not isinstance(signal_data, dict) or 'signal' not in signal_data:
                return signal_data
                
            signal = signal_data['signal']
            reason = signal_data.get('reason', 'Неизвестная причина')
            regime = market_regime.get('regime', 'unknown')
            regime_confidence = market_regime.get('confidence', 0.0)
            
            # Корректировка для трендовых режимов
            if regime == 'bull_trend' and signal == SignalType.SELL and regime_confidence > 0.7:
                signal = SignalType.HOLD
                reason += f"; бычий тренд (уверенность: {regime_confidence:.2f}) - отмена продажи"
            elif regime == 'bear_trend' and signal == SignalType.BUY and regime_confidence > 0.7:
                signal = SignalType.HOLD
                reason += f"; медвежий тренд (уверенность: {regime_confidence:.2f}) - отмена покупки"
            
            # Корректировка для режимов волатильности
            elif regime == 'high_volatility' and regime_confidence > 0.6:
                # В высокой волатильности более консервативный подход
                if signal != SignalType.HOLD:
                    reason += f"; высокая волатильность - повышенная осторожность"
            
            return {
                'signal': signal,
                'reason': reason,
                'confidence': signal_data['confidence'],
                'regime_adjustment': True,
                'market_regime': regime
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка корректировки сигнала на режим: {e}")
            return signal_data
    
    def _adjust_signal_for_risk(self, signal_data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Корректировка сигнала на риск
        
        Args:
            signal_data: Данные сигнала
            analysis: Полный анализ рынка
            
        Returns:
            Скорректированный сигнал
        """
        try:
            if not isinstance(signal_data, dict) or 'signal' not in signal_data:
                return signal_data
                
            signal = signal_data['signal']
            reason = signal_data.get('reason', 'Неизвестная причина')
            confidence = signal_data.get('confidence', 0.0)
            
            # Проверка общей уверенности
            overall_confidence = analysis.get('confidence_analysis', {}).get('overall_confidence', 0.5)
            if overall_confidence < 0.4 and signal != SignalType.HOLD:
                signal = SignalType.HOLD
                reason += f"; низкая общая уверенность ({overall_confidence:.2f})"
            
            # Проверка производительности модели
            model_accuracy = self.model_performance['accuracy']
            if model_accuracy < 0.45 and signal != SignalType.HOLD:
                signal = SignalType.HOLD
                reason += f"; низкая точность модели ({model_accuracy:.2f})"
            
            # Корректировка уверенности на основе риска
            risk_adjusted_confidence = confidence
            if overall_confidence < 0.6:
                risk_adjusted_confidence *= 0.8
            if model_accuracy < 0.5:
                risk_adjusted_confidence *= 0.7
            
            return {
                'signal': signal,
                'reason': reason,
                'confidence': risk_adjusted_confidence,
                'risk_adjustment': True,
                'original_confidence': confidence
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка корректировки сигнала на риск: {e}")
            return signal_data
    
    def _calculate_final_signal_strength(self, signal_data: Dict[str, Any], confidence_analysis: Dict[str, Any],
                                       market_regime: Dict[str, Any], technical_analysis: Dict[str, Any]) -> float:
        """
        Расчет итоговой силы сигнала
        
        Args:
            signal_data: Данные сигнала
            confidence_analysis: Анализ уверенности
            market_regime: Рыночный режим
            technical_analysis: Технический анализ
            
        Returns:
            Сила сигнала (0.0 - 1.0)
        """
        try:
            if signal_data['signal'] == SignalType.HOLD:
                return 0.0
            
            base_strength = signal_data.get('confidence', 0.5)
            
            # Корректировка на общую уверенность модели
            overall_confidence = confidence_analysis.get('overall_confidence', 0.5)
            confidence_multiplier = overall_confidence
            
            # Корректировка на рыночный режим
            regime_confidence = market_regime.get('confidence', 0.5)
            regime_multiplier = 0.8 + (regime_confidence * 0.4)  # 0.8 - 1.2
            
            # Корректировка на технические индикаторы
            technical_multiplier = 1.0
            if technical_analysis.get('status') == 'success':
                # Подсчет подтверждающих индикаторов
                confirmations = 0
                total_indicators = 0
                
                rsi_signal = technical_analysis.get('rsi', {}).get('signal', 'neutral')
                if rsi_signal != 'neutral':
                    total_indicators += 1
                    if (signal_data['signal'] == SignalType.BUY and rsi_signal == 'oversold') or \
                       (signal_data['signal'] == SignalType.SELL and rsi_signal == 'overbought'):
                        confirmations += 1
                
                macd_trend = technical_analysis.get('macd', {}).get('trend', 'neutral')
                if macd_trend != 'neutral':
                    total_indicators += 1
                    if (signal_data['signal'] == SignalType.BUY and macd_trend == 'bullish') or \
                       (signal_data['signal'] == SignalType.SELL and macd_trend == 'bearish'):
                        confirmations += 1
                
                if total_indicators > 0:
                    confirmation_ratio = confirmations / total_indicators
                    technical_multiplier = 0.7 + (confirmation_ratio * 0.6)  # 0.7 - 1.3
            
            # Итоговая сила
            final_strength = base_strength * confidence_multiplier * regime_multiplier * technical_multiplier
            
            return min(final_strength, 1.0)
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы сигнала: {e}")
            return 0.0
    
    def _update_prediction_stats(self, signal_data: Dict[str, Any]):
        """
        Обновление статистики предсказаний
        
        Args:
            signal_data: Данные сигнала
        """
        try:
            self.total_predictions += 1
            
            # Кэширование предсказания для последующей оценки
            prediction_record = {
                'timestamp': datetime.now(),
                'signal': signal_data['signal'],
                'confidence': signal_data.get('confidence', 0.0),
                'price': self.price_history[-1] if self.price_history else 0,
                'market_regime': self.market_regime
            }
            
            self.prediction_cache.append(prediction_record)
            
            # Ограничение размера кэша
            if len(self.prediction_cache) > 100:
                self.prediction_cache = self.prediction_cache[-100:]
            
            # Периодическая оценка точности (упрощенная)
            if len(self.prediction_cache) >= 10 and self.total_predictions % 10 == 0:
                self._evaluate_recent_predictions()
                
        except Exception as e:
            self.logger.error(f"Ошибка обновления статистики предсказаний: {e}")
    
    def _evaluate_recent_predictions(self):
        """
        Оценка недавних предсказаний (упрощенная версия)
        """
        try:
            if len(self.prediction_cache) < 5 or len(self.price_history) < 10:
                return
            
            correct = 0
            total = 0
            
            # Проверка последних 5 предсказаний
            for i in range(-5, 0):
                if abs(i) > len(self.prediction_cache):
                    continue
                    
                prediction = self.prediction_cache[i]
                
                # Найти цену через некоторое время после предсказания
                prediction_time = prediction['timestamp']
                prediction_price = prediction['price']
                
                # Упрощенная проверка: сравнить с текущей ценой
                current_price = self.price_history[-1]
                price_change = (current_price - prediction_price) / prediction_price
                
                predicted_signal = prediction['signal']
                
                # Оценка правильности (упрощенная)
                if predicted_signal == SignalType.BUY and price_change > 0.005:  # 0.5% рост
                    correct += 1
                elif predicted_signal == SignalType.SELL and price_change < -0.005:  # 0.5% падение
                    correct += 1
                elif predicted_signal == SignalType.HOLD and abs(price_change) < 0.01:  # Стабильность
                    correct += 1
                
                total += 1
            
            if total > 0:
                recent_accuracy = correct / total
                
                # Обновление производительности модели
                self.model_performance['accuracy'] = (
                    self.model_performance['accuracy'] * 0.8 + recent_accuracy * 0.2
                )
                
                self.logger.info(f"Оценка предсказаний: {correct}/{total} ({recent_accuracy:.2f}), общая точность: {self.model_performance['accuracy']:.3f}")
                
        except Exception as e:
            self.logger.error(f"Ошибка оценки предсказаний: {e}")
    
    def _calculate_trend_strength(self, prices: List[float]) -> float:
        """
        Расчет силы тренда
        
        Args:
            prices: Список цен
            
        Returns:
            Сила тренда (-10 до +10)
        """
        try:
            if len(prices) < 20:
                return 0.0
            
            # Линейная регрессия для определения тренда
            x = list(range(len(prices)))
            n = len(prices)
            
            sum_x = sum(x)
            sum_y = sum(prices)
            sum_xy = sum(x[i] * prices[i] for i in range(n))
            sum_x2 = sum(xi * xi for xi in x)
            
            # Коэффициент наклона
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            
            # Нормализация относительно средней цены
            avg_price = sum_y / n
            normalized_slope = (slope * n) / avg_price
            
            # Масштабирование до диапазона -10 до +10
            trend_strength = normalized_slope * 1000
            
            return max(-10, min(10, trend_strength))
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета силы тренда: {e}")
            return 0.0
    
    def _calculate_rsi(self, prices: List[float]) -> float:
        """
        Расчет RSI
        
        Args:
            prices: Список цен
            
        Returns:
            Значение RSI (0-100)
        """
        try:
            if len(prices) < self.rsi_period + 1:
                return 50.0
            
            # Расчет изменений цен
            price_changes = []
            for i in range(1, len(prices)):
                change = prices[i] - prices[i-1]
                price_changes.append(change)
            
            if len(price_changes) < self.rsi_period:
                return 50.0
            
            # Разделение на прибыли и убытки
            gains = [max(0, change) for change in price_changes[-self.rsi_period:]]
            losses = [max(0, -change) for change in price_changes[-self.rsi_period:]]
            
            # Средние прибыли и убытки
            avg_gain = sum(gains) / len(gains)
            avg_loss = sum(losses) / len(losses)
            
            if avg_loss == 0:
                return 100.0
            
            # RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return rsi
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета RSI: {e}")
            return 50.0
    
    def _calculate_macd(self, prices: List[float]) -> Tuple[float, float, float]:
        """
        Расчет MACD
        
        Args:
            prices: Список цен
            
        Returns:
            Кортеж (MACD линия, сигнальная линия, гистограмма)
        """
        try:
            if len(prices) < self.macd_slow:
                return 0.0, 0.0, 0.0
            
            # EMA расчет
            def calculate_ema(data: List[float], period: int) -> float:
                if len(data) < period:
                    return sum(data) / len(data)
                
                multiplier = 2 / (period + 1)
                ema = sum(data[:period]) / period
                
                for price in data[period:]:
                    ema = (price * multiplier) + (ema * (1 - multiplier))
                
                return ema
            
            # Быстрая и медленная EMA
            fast_ema = calculate_ema(prices, self.macd_fast)
            slow_ema = calculate_ema(prices, self.macd_slow)
            
            # MACD линия
            macd_line = fast_ema - slow_ema
            
            # Для сигнальной линии нужна история MACD
            if not hasattr(self, '_macd_history'):
                self._macd_history = []
            
            self._macd_history.append(macd_line)
            if len(self._macd_history) > 50:
                self._macd_history = self._macd_history[-50:]
            
            # Сигнальная линия (EMA от MACD)
            macd_signal_line = calculate_ema(self._macd_history, self.macd_signal)
            
            # Гистограмма
            histogram = macd_line - macd_signal_line
            
            return macd_line, macd_signal_line, histogram
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета MACD: {e}")
            return 0.0, 0.0, 0.0
    
    def _calculate_bollinger_bands(self, prices: List[float]) -> Tuple[float, float, float]:
        """
        Расчет полос Боллинджера
        
        Args:
            prices: Список цен
            
        Returns:
            Кортеж (верхняя полоса, средняя линия, нижняя полоса)
        """
        try:
            if len(prices) < self.bb_period:
                current_price = prices[-1] if prices else 0
                return current_price, current_price, current_price
            
            # Средняя линия (SMA)
            recent_prices = prices[-self.bb_period:]
            middle_line = sum(recent_prices) / len(recent_prices)
            
            # Стандартное отклонение
            variance = sum((price - middle_line) ** 2 for price in recent_prices) / len(recent_prices)
            std_dev = variance ** 0.5
            
            # Верхняя и нижняя полосы
            upper_band = middle_line + (self.bb_std * std_dev)
            lower_band = middle_line - (self.bb_std * std_dev)
            
            return upper_band, middle_line, lower_band
            
        except Exception as e:
            self.logger.error(f"Ошибка расчета полос Боллинджера: {e}")
            current_price = prices[-1] if prices else 0
            return current_price, current_price, current_price