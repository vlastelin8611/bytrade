#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль торговых стратегий

Включает базовый класс стратегии, движок выполнения стратегий
и реализации конкретных стратегий.
"""

from .base_strategy import BaseStrategy, StrategyState, SignalType
from .strategy_engine import StrategyEngine

# Импорт конкретных стратегий
from .moving_averages import MovingAveragesStrategy
from .rsi_macd import RSIMACDStrategy
from .bollinger_bands import BollingerBandsStrategy
from .momentum_trading import MomentumTradingStrategy
from .grid_trading import GridTradingStrategy
from .adaptive_ml import AdaptiveMLStrategy

__all__ = [
    'BaseStrategy',
    'StrategyState', 
    'SignalType',
    'StrategyEngine',
    'MovingAveragesStrategy',
    'RSIMACDStrategy',
    'BollingerBandsStrategy',
    'MomentumTradingStrategy',
    'GridTradingStrategy',
    'AdaptiveMLStrategy',
    'AVAILABLE_STRATEGIES',
    'STRATEGY_METADATA',
    'get_strategy_class',
    'get_strategy_metadata',
    'list_available_strategies',
]

# Словарь доступных стратегий для удобного доступа
AVAILABLE_STRATEGIES = {
    'moving_averages': MovingAveragesStrategy,
    'rsi_macd': RSIMACDStrategy,
    'bollinger_bands': BollingerBandsStrategy,
    'momentum_trading': MomentumTradingStrategy,
    'grid_trading': GridTradingStrategy,
    'adaptive_ml': AdaptiveMLStrategy,
}

# Метаданные стратегий
STRATEGY_METADATA = {
    'moving_averages': {
        'name': 'Moving Averages',
        'description': 'Стратегия на основе пересечения скользящих средних',
        'risk_level': 'Low',
        'timeframe': '5m-1h',
        'suitable_markets': ['trending', 'stable']
    },
    'rsi_macd': {
        'name': 'RSI + MACD',
        'description': 'Комбинированная стратегия RSI и MACD',
        'risk_level': 'Medium',
        'timeframe': '15m-4h',
        'suitable_markets': ['trending', 'volatile']
    },
    'bollinger_bands': {
        'name': 'Bollinger Bands',
        'description': 'Стратегия на основе полос Боллинджера',
        'risk_level': 'Medium',
        'timeframe': '5m-1h',
        'suitable_markets': ['ranging', 'volatile']
    },
    'momentum_trading': {
        'name': 'Momentum Trading',
        'description': 'Стратегия торговли по моментуму',
        'risk_level': 'High',
        'timeframe': '1m-30m',
        'suitable_markets': ['trending', 'breakout']
    },
    'grid_trading': {
        'name': 'Grid Trading',
        'description': 'Сеточная торговая стратегия',
        'risk_level': 'Medium',
        'timeframe': '5m-1h',
        'suitable_markets': ['ranging', 'stable']
    },
    'adaptive_ml': {
        'name': 'Adaptive ML Strategy',
        'description': 'Адаптивная стратегия машинного обучения',
        'risk_level': 'Medium',
        'timeframe': '5m-1h',
        'suitable_markets': ['all']
    }
}

def get_strategy_class(strategy_name: str):
    """
    Получить класс стратегии по имени
    
    Args:
        strategy_name: Имя стратегии
        
    Returns:
        Класс стратегии или None
    """
    return AVAILABLE_STRATEGIES.get(strategy_name)

def get_strategy_metadata(strategy_name: str):
    """
    Получить метаданные стратегии
    
    Args:
        strategy_name: Имя стратегии
        
    Returns:
        Метаданные стратегии или None
    """
    return STRATEGY_METADATA.get(strategy_name)

def list_available_strategies():
    """
    Получить список доступных стратегий
    
    Returns:
        Список имен стратегий
    """
    return list(AVAILABLE_STRATEGIES.keys())