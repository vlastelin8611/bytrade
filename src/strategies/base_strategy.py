#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Базовый класс для всех торговых стратегий

Определяет общий интерфейс и функциональность для всех стратегий:
- Управление состоянием
- Логирование
- Риск-менеджмент
- Интерфейс для анализа и торговли
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
import uuid
from ..core.risk_manager import RiskManager

class StrategyState(Enum):
    """Состояния стратегии"""
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

class SignalType(Enum):
    """Типы торговых сигналов"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"

class BaseStrategy(ABC):
    """
    Базовый класс для всех торговых стратегий
    """
    
    def __init__(self, name: str, config: Dict[str, Any], 
                 api_client, db_manager, config_manager):
        self.name = name
        self.config = config
        self.api_client = api_client
        self.db = db_manager
        self.config_manager = config_manager
        
        # Уникальный идентификатор сессии
        self.session_id = str(uuid.uuid4())
        
        # Состояние стратегии
        self.state = StrategyState.STOPPED
        self.start_time = None
        self.last_update = None
        
        # Информация о текущем ордере
        self.current_order_id = None
        
        # Настройки из конфигурации
        self.symbol = config.get('asset', 'BTCUSDT')
        self.position_size = config.get('position_size', 0.01)
        self.stop_loss_pct = config.get('stop_loss', 2.0)
        self.take_profit_pct = config.get('take_profit', 4.0)
        self.timeframe = config.get('timeframe', '1h')
        
        # Инициализация менеджера рисков
        risk_config = {
            'max_daily_loss_pct': config.get('max_daily_loss_pct', 20.0),
            'max_consecutive_losses': config.get('max_consecutive_losses', 3),
            'max_stop_loss_pct': config.get('max_stop_loss_pct', 40.0),
            'max_position_size_pct': config.get('max_position_size_pct', 10.0),
            'max_trades_per_day': config.get('max_trades_per_day', 10),
            'max_drawdown_pct': config.get('max_drawdown_pct', 15.0),
            'min_confidence_threshold': config.get('min_confidence_threshold', 0.7)
        }
        self.risk_manager = RiskManager(risk_config)
        
        # Устаревшие параметры риск-менеджмента (для совместимости)
        self.max_position_size = config.get('max_position_size', 0.1)
        self.max_daily_loss = config.get('max_daily_loss', 5.0)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 3)
        
        # Статистика
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        
        # Текущая позиция
        self.current_position = None
        self.entry_price = None
        self.stop_loss_price = None
        self.take_profit_price = None
        
        # Логгер
        self.logger = logging.getLogger(f"strategy.{self.name}")
        
        self.logger.info(f"Стратегия {self.name} инициализирована с улучшенным риск-менеджментом")
    
    @abstractmethod
    def analyze_market(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Анализ рыночных данных
        
        Args:
            market_data: Рыночные данные (цены, объемы, индикаторы)
            
        Returns:
            Результат анализа с сигналами и метриками
        """
        pass
    
    @abstractmethod
    def generate_signal(self, analysis: Dict[str, Any]) -> Tuple[SignalType, float]:
        """
        Генерация торгового сигнала на основе анализа
        
        Args:
            analysis: Результат анализа рынка
            
        Returns:
            Кортеж (тип сигнала, уверенность 0-1)
        """
        pass
        
    def execute_external_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполнение внешнего торгового сигнала (из индикаторов, ML-моделей и т.д.)
        
        Args:
            signal_data: Данные сигнала с ключами:
                - signal: Тип сигнала (BUY, SELL, CLOSE_LONG, CLOSE_SHORT)
                - price: Текущая цена
                - confidence: Уверенность в сигнале (0-1)
                - metadata: Дополнительные данные сигнала (опционально)
            
        Returns:
            Результат выполнения сигнала
        """
        try:
            # Проверка обязательных полей
            required_fields = ['signal', 'price']
            for field in required_fields:
                if field not in signal_data:
                    error_msg = f"Отсутствует обязательное поле: {field}"
                    self.logger.error(error_msg)
                    return {'status': 'error', 'message': error_msg}
            
            # Извлечение данных сигнала
            signal_type = signal_data['signal']
            price = float(signal_data['price'])
            confidence = float(signal_data.get('confidence', 0.8))
            metadata = signal_data.get('metadata', {})
            
            # Логирование получения внешнего сигнала
            self._log_strategy_event(
                "EXTERNAL_SIGNAL_RECEIVED",
                f"Получен внешний сигнал {signal_type} по цене {price} с уверенностью {confidence:.2f}",
                f"External signal received: {signal_type}, price: {price}, confidence: {confidence}",
                {
                    'signal': signal_type,
                    'price': price,
                    'confidence': confidence,
                    'source': metadata.get('source', 'unknown'),
                    'timestamp': metadata.get('timestamp', datetime.utcnow().isoformat())
                }
            )
            
            # Выполнение сигнала через основной метод
            result = self.execute_signal(signal_type, price, confidence)
            
            # Добавление метаданных к результату
            if 'metadata' in signal_data:
                result['metadata'] = signal_data['metadata']
                
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка выполнения внешнего сигнала: {e}")
            self._log_strategy_event(
                "EXTERNAL_SIGNAL_ERROR",
                f"Ошибка выполнения внешнего сигнала: {str(e)}",
                f"Error executing external signal: {type(e).__name__}: {str(e)}",
                {
                    'error': str(e),
                    'error_type': type(e).__name__,
                    'signal_data': signal_data
                }
            )
            return {
                'status': 'error',
                'message': str(e),
                'signal_data': signal_data
            }
    
    @abstractmethod
    def get_strategy_description(self) -> str:
        """
        Получение описания стратегии
        
        Returns:
            Человекочитаемое описание стратегии
        """
        pass
    
    def start(self) -> bool:
        """
        Запуск стратегии
        
        Returns:
            True если запуск успешен
        """
        try:
            if self.state == StrategyState.RUNNING:
                self.logger.warning("Стратегия уже запущена")
                self._log_strategy_event(
                    "START_ATTEMPT",
                    f"Попытка запуска уже работающей стратегии {self.name}",
                    "Strategy already running"
                )
                return False
            
            # Проверка конфигурации
            if not self._validate_config():
                self.logger.error("Некорректная конфигурация стратегии")
                self._log_strategy_event(
                    "START_FAILED",
                    f"Не удалось запустить стратегию {self.name} из-за некорректной конфигурации",
                    "Configuration validation failed"
                )
                return False
            
            # Проверка подключения к API
            if not self._check_api_connection():
                self.logger.error("Нет подключения к API")
                self._log_strategy_event(
                    "START_FAILED",
                    f"Не удалось запустить стратегию {self.name} из-за отсутствия подключения к API",
                    "API connection check failed"
                )
                return False
            
            self.state = StrategyState.RUNNING
            self.start_time = datetime.utcnow()
            self.last_update = self.start_time
            
            # Сброс дневной статистики
            self.daily_pnl = 0.0
            self.consecutive_losses = 0
            
            self._log_strategy_event(
                "START", 
                f"Стратегия {self.name} успешно запущена и готова к торговле",
                f"Strategy started at {self.start_time}",
                {'start_time': self.start_time.isoformat(), 'symbol': self.symbol}
            )
            self.logger.info(f"Стратегия {self.name} запущена")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка запуска стратегии: {e}")
            self.state = StrategyState.ERROR
            self._log_strategy_event(
                "START_ERROR",
                f"Критическая ошибка при запуске стратегии {self.name}: {str(e)}",
                f"Exception: {type(e).__name__}: {str(e)}"
            )
            return False
    
    def stop(self) -> bool:
        """
        Остановка стратегии
        
        Returns:
            True если остановка успешна
        """
        try:
            if self.state == StrategyState.STOPPED:
                self.logger.warning("Стратегия уже остановлена")
                self._log_strategy_event(
                    "STOP_ATTEMPT",
                    f"Попытка остановки уже остановленной стратегии {self.name}",
                    "Strategy already stopped"
                )
                return False
            
            # Закрытие открытых позиций
            if self.current_position:
                self.logger.info(f"Закрытие открытой позиции при остановке стратегии {self.name}")
                self._close_position("Strategy stopped")
            
            uptime = None
            if self.start_time:
                uptime = (datetime.utcnow() - self.start_time).total_seconds()
            
            self.state = StrategyState.STOPPED
            
            self._log_strategy_event(
                "STOP", 
                f"Стратегия {self.name} остановлена. Время работы: {uptime:.0f} сек, всего сделок: {self.total_trades}",
                f"Strategy stopped after {uptime} seconds",
                {
                    'uptime_seconds': uptime,
                    'total_trades': self.total_trades,
                    'total_pnl': self.total_pnl
                }
            )
            self.logger.info(f"Стратегия {self.name} остановлена")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Ошибка остановки стратегии: {e}")
            self._log_strategy_event(
                "STOP_ERROR",
                f"Ошибка при остановке стратегии {self.name}: {str(e)}",
                f"Exception: {type(e).__name__}: {str(e)}"
            )
            return False
    
    def pause(self) -> bool:
        """
        Приостановка стратегии
        
        Returns:
            True если приостановка успешна
        """
        if self.state == StrategyState.RUNNING:
            self.state = StrategyState.PAUSED
            self._log_strategy_event(
                "PAUSE", 
                f"Стратегия {self.name} приостановлена",
                f"Strategy paused at {datetime.utcnow()}",
                {'pause_time': datetime.utcnow().isoformat()}
            )
            self.logger.info(f"Стратегия {self.name} приостановлена")
            return True
        else:
            self._log_strategy_event(
                "PAUSE_FAILED",
                f"Не удалось приостановить стратегию {self.name} (состояние: {self.state.value})",
                f"Cannot pause strategy in state: {self.state.value}"
            )
            return False
    
    def resume(self) -> bool:
        """
        Возобновление стратегии
        
        Returns:
            True если возобновление успешно
        """
        if self.state == StrategyState.PAUSED:
            self.state = StrategyState.RUNNING
            self._log_strategy_event(
                "RESUME", 
                f"Стратегия {self.name} возобновлена и продолжает работу",
                f"Strategy resumed at {datetime.utcnow()}",
                {'resume_time': datetime.utcnow().isoformat()}
            )
            self.logger.info(f"Стратегия {self.name} возобновлена")
            return True
        else:
            self._log_strategy_event(
                "RESUME_FAILED",
                f"Не удалось возобновить стратегию {self.name} (состояние: {self.state.value})",
                f"Cannot resume strategy in state: {self.state.value}"
            )
            return False
    
    def update(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обновление стратегии с новыми рыночными данными
        
        Args:
            market_data: Новые рыночные данные
            
        Returns:
            Результат обновления с сигналами и действиями
        """
        if self.state != StrategyState.RUNNING:
            return {'status': 'not_running'}
        
        try:
            self.last_update = datetime.utcnow()
            
            # Анализ рынка
            analysis = self.analyze_market(market_data)
            
            # Генерация сигнала
            signal, confidence = self.generate_signal(analysis)
            
            # Логирование сигнала если он значимый
            if confidence > 0.5:
                self._log_strategy_event(
                    "SIGNAL_GENERATED",
                    f"Стратегия {self.name} сгенерировала сигнал {signal.value} с уверенностью {confidence:.2f}",
                    f"Signal: {signal.value}, confidence: {confidence}",
                    {
                        'signal': signal.value,
                        'confidence': confidence,
                        'price': market_data.get('price', 0)
                    }
                )
            
            # Проверка риск-лимитов с учетом уверенности сигнала
            if not self._check_risk_limits(confidence):
                self.logger.warning("Превышены риск-лимиты, стратегия приостановлена")
                self._log_strategy_event(
                    "RISK_LIMIT_EXCEEDED",
                    f"Стратегия {self.name} приостановлена из-за превышения риск-лимитов",
                    f"Risk limits exceeded, confidence: {confidence}",
                    {
                        'daily_pnl': self.daily_pnl,
                        'consecutive_losses': self.consecutive_losses,
                        'signal_confidence': confidence
                    }
                )
                self.pause()
                return {'status': 'risk_limit_exceeded'}
            
            # Выполнение сигнала через новый метод execute_signal
            current_price = market_data.get('price', 0)
            result = self.execute_signal(signal.value, current_price, confidence)
            
            # Обновление позиции
            self._update_position_status()
            
            return {
                'status': 'updated',
                'signal': signal.value,
                'confidence': confidence,
                'analysis': analysis,
                'action': result.get('result', {}),
                'order_id': self.current_order_id
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления стратегии: {e}")
            self.state = StrategyState.ERROR
            self._log_strategy_event(
                "UPDATE_ERROR",
                f"Критическая ошибка при обновлении стратегии {self.name}: {str(e)}",
                f"Exception: {type(e).__name__}: {str(e)}"
            )
            return {'status': 'error', 'error': str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """
        Получение текущего статуса стратегии
        
        Returns:
            Словарь с информацией о состоянии стратегии
        """
        uptime = None
        if self.start_time:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
        
        win_rate = 0.0
        if self.total_trades > 0:
            win_rate = (self.winning_trades / self.total_trades) * 100
        
        # Получение оценки рисков
        risk_assessment = self.risk_manager.get_risk_assessment()
        
        return {
            'name': self.name,
            'state': self.state.value,
            'session_id': self.session_id,
            'symbol': self.symbol,
            'uptime_seconds': uptime,
            'start_time': self.start_time,
            'last_update': self.last_update,
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'daily_pnl': self.daily_pnl,
            'total_pnl': self.total_pnl,
            'consecutive_losses': self.consecutive_losses,
            'current_position': self.current_position,
            'config': self.config,
            'risk_assessment': risk_assessment
        }
    
    def get_detailed_status(self) -> Dict[str, Any]:
        """
        Получение детального статуса стратегии, включая информацию о текущем ордере и позиции
        
        Returns:
            Словарь с детальным статусом стратегии
        """
        # Базовое состояние стратегии
        status = self.get_status()
        
        # Добавление информации о текущем ордере, если есть
        if self.current_order_id:
            try:
                order_info = self.api_client.get_order_info(
                    category='linear',
                    symbol=self.symbol,
                    orderId=self.current_order_id
                )
                status['current_order'] = order_info
            except Exception as e:
                self.logger.error(f"Ошибка получения информации о текущем ордере: {e}")
                status['current_order'] = {'error': str(e)}
        else:
            status['current_order'] = None
            
        # Добавление информации о текущей позиции
        try:
            position_info = self.api_client.get_position_info(
                category='linear',
                symbol=self.symbol
            )
            status['position_details'] = position_info
        except Exception as e:
            self.logger.error(f"Ошибка получения информации о текущей позиции: {e}")
            status['position_details'] = {'error': str(e)}
            
        # Добавление информации о текущей позиции в стратегии
        if self.current_position:
            status['position_info'] = {
                'type': self.current_position,
                'entry_price': self.entry_price,
                'stop_loss': self.stop_loss_price,
                'take_profit': self.take_profit_price,
                'position_size': self.position_size
            }
        
        # Добавление информации о риск-менеджере
        status['risk_details'] = self.risk_manager.get_detailed_assessment()
        
        return status
    
    def _validate_config(self) -> bool:
        """
        Валидация конфигурации стратегии
        
        Returns:
            True если конфигурация корректна
        """
        required_fields = ['asset', 'position_size', 'stop_loss', 'take_profit']
        
        for field in required_fields:
            if field not in self.config:
                self.logger.error(f"Отсутствует обязательное поле: {field}")
                return False
        
        # Проверка числовых значений
        if self.position_size <= 0 or self.position_size > self.max_position_size:
            self.logger.error(f"Некорректный размер позиции: {self.position_size}")
            return False
        
        if self.stop_loss_pct <= 0 or self.stop_loss_pct > 50:
            self.logger.error(f"Некорректный стоп-лосс: {self.stop_loss_pct}%")
            return False
        
        return True
    
    def _check_api_connection(self) -> bool:
        """
        Проверка подключения к API
        
        Returns:
            True если подключение активно
        """
        try:
            # Простая проверка через получение времени сервера
            response = self.api_client.get_server_time()
            return response.get('retCode') == 0
        except Exception as e:
            self.logger.error(f"Ошибка проверки API: {e}")
            return False
    
    def _check_risk_limits(self, signal_confidence: float = 0.0) -> bool:
        """
        Проверка риск-лимитов с использованием RiskManager
        
        Args:
            signal_confidence: Уверенность в сигнале
            
        Returns:
            True если лимиты не превышены
        """
        # Получение оценки рисков
        risk_assessment = self.risk_manager.get_risk_assessment()
        
        # Проверка блокировки торговли
        if risk_assessment['is_blocked']:
            self.logger.warning(f"Торговля заблокирована: {risk_assessment['block_reason']}")
            return False
        
        # Проверка разрешения на торговлю
        allowed, reason = self.risk_manager.check_trade_allowed(
            signal_confidence=signal_confidence,
            position_size_pct=self.position_size * 100,
            stop_loss_pct=self.stop_loss_pct
        )
        
        if not allowed:
            self.logger.warning(f"Торговля запрещена: {reason}")
            return False
        
        # Обратная совместимость со старыми проверками
        if abs(self.daily_pnl) > self.max_daily_loss:
            self.logger.warning(f"Превышен лимит дневных потерь: {self.daily_pnl}%")
            return False
        
        if self.consecutive_losses >= self.max_consecutive_losses:
            self.logger.warning(f"Превышен лимит последовательных потерь: {self.consecutive_losses}")
            return False
        
        return True
    
    def execute_signal(self, signal_type: str, price: float, confidence: float = 0.8) -> Dict[str, Any]:
        """
        Выполнение торгового сигнала через API
        
        Args:
            signal_type: Тип сигнала (BUY, SELL, CLOSE_LONG, CLOSE_SHORT)
            price: Текущая цена
            confidence: Уверенность в сигнале (0-1)
            
        Returns:
            Результат выполнения сигнала
        """
        try:
            # Преобразование строкового сигнала в SignalType
            signal_map = {
                'BUY': SignalType.BUY,
                'SELL': SignalType.SELL,
                'CLOSE_LONG': SignalType.CLOSE_LONG,
                'CLOSE_SHORT': SignalType.CLOSE_SHORT,
                'HOLD': SignalType.HOLD
            }
            
            signal = signal_map.get(signal_type.upper())
            if not signal:
                self.logger.error(f"Неизвестный тип сигнала: {signal_type}")
                return {'status': 'error', 'message': f'Неизвестный тип сигнала: {signal_type}'}
            
            # Создаем минимальные рыночные данные
            market_data = {'price': price}
            
            # Проверка риск-лимитов с учетом уверенности сигнала
            if not self._check_risk_limits(confidence):
                self.logger.warning("Превышены риск-лимиты, сигнал отклонен")
                self._log_strategy_event(
                    "SIGNAL_REJECTED",
                    f"Сигнал {signal_type} отклонен из-за превышения риск-лимитов",
                    f"Signal rejected due to risk limits: {signal_type}, confidence: {confidence}",
                    {
                        'signal': signal_type,
                        'confidence': confidence,
                        'price': price,
                        'daily_pnl': self.daily_pnl,
                        'consecutive_losses': self.consecutive_losses
                    }
                )
                return {
                    'status': 'rejected',
                    'reason': 'risk_limit_exceeded',
                    'signal': signal_type
                }
            
            # Обрабатываем сигнал через существующий метод
            result = self._process_signal(signal, confidence, market_data)
            
            # Логирование выполнения сигнала
            self._log_strategy_event(
                "SIGNAL_EXECUTED",
                f"Выполнен сигнал {signal_type} по цене {price} с уверенностью {confidence:.2f}",
                f"Signal executed: {signal_type}, price: {price}, confidence: {confidence}",
                {
                    'signal': signal_type,
                    'confidence': confidence,
                    'price': price,
                    'action': result.get('action', 'unknown'),
                    'order_id': self.current_order_id
                }
            )
            
            return {
                'status': 'success',
                'signal': signal_type,
                'confidence': confidence,
                'price': price,
                'result': result,
                'order_id': self.current_order_id
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка выполнения сигнала {signal_type}: {e}")
            self._log_strategy_event(
                "SIGNAL_ERROR",
                f"Ошибка выполнения сигнала {signal_type}: {str(e)}",
                f"Error executing signal: {type(e).__name__}: {str(e)}",
                {
                    'signal': signal_type,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            return {
                'status': 'error',
                'message': str(e),
                'signal': signal_type
            }
    
    def _process_signal(self, signal: SignalType, confidence: float, 
                      market_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Обработка торгового сигнала
        
        Args:
            signal: Тип сигнала
            confidence: Уверенность в сигнале
            market_data: Рыночные данные
            
        Returns:
            Результат обработки сигнала
        """
        current_price = market_data.get('price', 0)
        
        # Минимальная уверенность для торговли
        min_confidence = self.config.get('min_confidence', 0.7)
        
        if confidence < min_confidence:
            return {'action': 'no_action', 'reason': 'low_confidence'}
        
        # Обработка сигналов
        if signal == SignalType.BUY and not self.current_position:
            return self._open_long_position(current_price)
        
        elif signal == SignalType.SELL and not self.current_position:
            return self._open_short_position(current_price)
        
        elif signal == SignalType.CLOSE_LONG and self.current_position == 'long':
            return self._close_position("Signal to close long", current_price)
        
        elif signal == SignalType.CLOSE_SHORT and self.current_position == 'short':
            return self._close_position("Signal to close short", current_price)
        
        return {'action': 'no_action', 'reason': 'no_suitable_signal'}
    
    def _open_long_position(self, price: float) -> Dict[str, Any]:
        """
        Открытие длинной позиции
        
        Args:
            price: Цена входа
            
        Returns:
            Результат операции
        """
        try:
            # Расчет стоп-лосса и тейк-профита
            stop_loss = price * (1 - self.stop_loss_pct / 100)
            take_profit = price * (1 + self.take_profit_pct / 100)
            
            # Вызов API для открытия длинной позиции
            order_result = self.api_client.place_order(
                category='linear',
                symbol=self.symbol,
                side='Buy',
                orderType='Market',
                qty=str(self.position_size)
            )
            
            # Логирование результата ордера
            self.logger.info(f"Размещен ордер на покупку: {order_result}")
            
            # Сохранение ID ордера
            self.current_order_id = order_result.get('orderId') if order_result else None
            
            self.current_position = 'long'
            self.entry_price = price
            self.stop_loss_price = stop_loss
            self.take_profit_price = take_profit
            
            self._log_strategy_event(
                "POSITION_OPENED",
                f"Открыта длинная позиция по {self.symbol}: размер {self.position_size} по цене {price} USDT",
                f"Long position opened: size={self.position_size}, price={price}, sl={stop_loss}, tp={take_profit}",
                {
                    'position_type': 'long',
                    'entry_price': price,
                    'position_size': self.position_size,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'symbol': self.symbol
                }
            )
            
            return {
                'action': 'open_long',
                'price': price,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка открытия длинной позиции: {e}")
            return {'action': 'error', 'error': str(e)}
    
    def _open_short_position(self, price: float) -> Dict[str, Any]:
        """
        Открытие короткой позиции
        
        Args:
            price: Цена входа
            
        Returns:
            Результат операции
        """
        try:
            # Расчет стоп-лосса и тейк-профита
            stop_loss = price * (1 + self.stop_loss_pct / 100)
            take_profit = price * (1 - self.take_profit_pct / 100)
            
            # Вызов API для открытия короткой позиции
            order_result = self.api_client.place_order(
                category='linear',
                symbol=self.symbol,
                side='Sell',
                orderType='Market',
                qty=str(self.position_size)
            )
            
            # Логирование результата ордера
            self.logger.info(f"Размещен ордер на продажу: {order_result}")
            
            # Сохранение ID ордера
            self.current_order_id = order_result.get('orderId') if order_result else None
            
            self.current_position = 'short'
            self.entry_price = price
            self.stop_loss_price = stop_loss
            self.take_profit_price = take_profit
            
            self._log_strategy_event(
                "POSITION_OPENED",
                f"Открыта короткая позиция по {self.symbol}: размер {self.position_size} по цене {price} USDT",
                f"Short position opened: size={self.position_size}, price={price}, sl={stop_loss}, tp={take_profit}",
                {
                    'position_type': 'short',
                    'entry_price': price,
                    'position_size': self.position_size,
                    'stop_loss': stop_loss,
                    'take_profit': take_profit,
                    'symbol': self.symbol
                }
            )
            
            return {
                'action': 'open_short',
                'price': price,
                'stop_loss': stop_loss,
                'take_profit': take_profit
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка открытия короткой позиции: {e}")
            return {'action': 'error', 'error': str(e)}
    
    def _close_position(self, reason: str, current_price: float = None) -> Dict[str, Any]:
        """
        Закрытие текущей позиции
        
        Args:
            reason: Причина закрытия
            current_price: Текущая цена для расчета PnL
            
        Returns:
            Результат операции
        """
        try:
            if not self.current_position:
                return {'action': 'no_position'}
            
            # Расчет PnL если указана текущая цена
            pnl = 0.0
            pnl_pct = 0.0
            is_win = False
            
            if current_price and self.entry_price:
                if self.current_position == 'long':
                    pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
                elif self.current_position == 'short':
                    pnl_pct = ((self.entry_price - current_price) / self.entry_price) * 100
                
                is_win = pnl_pct > 0
                
                # Запись результата сделки в RiskManager
                trade_result = {
                    'pnl': pnl,
                    'pnl_pct': pnl_pct,
                    'is_win': is_win,
                    'timestamp': datetime.utcnow()
                }
                self.risk_manager.record_trade(trade_result)
                
                # Записываем результат в риск-менеджер
                self.risk_manager.record_trade_result(pnl_pct, self.symbol, self.name)
                
                # Обновление статистики
                if is_win:
                    self.winning_trades += 1
                    self.consecutive_losses = 0
                else:
                    self.losing_trades += 1
                    self.consecutive_losses += 1
                
                self.daily_pnl += pnl_pct
                self.total_pnl += pnl_pct
            
            # Вызов API для закрытия позиции
            side = 'Sell' if self.current_position == 'long' else 'Buy'
            close_result = self.api_client.place_order(
                category='linear',
                symbol=self.symbol,
                side=side,
                orderType='Market',
                qty=str(self.position_size)
            )
            
            # Логирование результата закрытия
            self.logger.info(f"Закрыта позиция: {close_result}")
            
            # Сброс ID ордера
            self.current_order_id = None
            
            position_type = self.current_position
            self.current_position = None
            self.entry_price = None
            self.stop_loss_price = None
            self.take_profit_price = None
            
            self.total_trades += 1
            
            pnl_info = f", PnL: {pnl_pct:.2f}%" if current_price else ""
            self._log_strategy_event(
                "POSITION_CLOSED",
                f"Закрыта {position_type} позиция по {self.symbol}. Причина: {reason}{pnl_info}",
                f"Position closed: type={position_type}, reason={reason}, pnl_pct={pnl_pct}, price={current_price}",
                {
                    'position_type': position_type,
                    'close_reason': reason,
                    'close_price': current_price,
                    'entry_price': self.entry_price,
                    'pnl_pct': pnl_pct,
                    'is_win': is_win,
                    'symbol': self.symbol,
                    'total_trades': self.total_trades
                }
            )
            
            return {
                'action': 'close_position',
                'position_type': position_type,
                'reason': reason,
                'pnl_pct': pnl_pct,
                'is_win': is_win
            }
            
        except Exception as e:
            self.logger.error(f"Ошибка закрытия позиции: {e}")
            return {'action': 'error', 'error': str(e)}
    
    def _update_position_status(self):
        """
        Обновление статуса текущей позиции
        """
        if not self.current_position:
            return
        
        try:
            # Получение текущей цены через API
            ticker_info = self.api_client.get_tickers(category='linear', symbol=self.symbol)
            
            if not ticker_info or 'result' not in ticker_info:
                self.logger.warning(f"Не удалось получить данные тикера для {self.symbol}")
                return
            
            # Извлечение текущей цены
            current_price = None
            if 'list' in ticker_info['result'] and ticker_info['result']['list']:
                ticker_data = ticker_info['result']['list'][0]
                if self.current_position == 'long':
                    current_price = float(ticker_data.get('lastPrice', 0))
                else:  # short
                    current_price = float(ticker_data.get('lastPrice', 0))
            
            if not current_price:
                self.logger.warning(f"Не удалось извлечь текущую цену для {self.symbol}")
                return
            
            # Расчет текущего PnL
            pnl_pct = 0.0
            if self.entry_price:
                if self.current_position == 'long':
                    pnl_pct = ((current_price - self.entry_price) / self.entry_price) * 100
                elif self.current_position == 'short':
                    pnl_pct = ((self.entry_price - current_price) / self.entry_price) * 100
            
            # Проверка стоп-лосса и тейк-профита
            if self.current_position == 'long':
                if current_price <= self.stop_loss_price:
                    self.logger.info(f"Сработал стоп-лосс для длинной позиции: {current_price} <= {self.stop_loss_price}")
                    self._close_position("Stop Loss triggered", current_price)
                elif current_price >= self.take_profit_price:
                    self.logger.info(f"Сработал тейк-профит для длинной позиции: {current_price} >= {self.take_profit_price}")
                    self._close_position("Take Profit triggered", current_price)
            elif self.current_position == 'short':
                if current_price >= self.stop_loss_price:
                    self.logger.info(f"Сработал стоп-лосс для короткой позиции: {current_price} >= {self.stop_loss_price}")
                    self._close_position("Stop Loss triggered", current_price)
                elif current_price <= self.take_profit_price:
                    self.logger.info(f"Сработал тейк-профит для короткой позиции: {current_price} <= {self.take_profit_price}")
                    self._close_position("Take Profit triggered", current_price)
            
            # Обновление текущего PnL в логах
            self.logger.debug(f"Текущий PnL для {self.symbol}: {pnl_pct:.2f}%")
            
        except Exception as e:
            self.logger.error(f"Ошибка при обновлении статуса позиции: {e}")
            return
    
    def cancel_current_order(self) -> Dict[str, Any]:
        """
        Отмена текущего ордера, если он существует
        
        Returns:
            Результат отмены ордера
        """
        if not self.current_order_id:
            return {
                'status': 'warning',
                'message': 'Нет активного ордера для отмены'
            }
            
        try:
            # Получение информации о текущем ордере перед отменой
            try:
                order_info = self.api_client.get_order_info(
                    category='linear',
                    symbol=self.symbol,
                    orderId=self.current_order_id
                )
            except Exception as e:
                self.logger.warning(f"Не удалось получить информацию о ордере перед отменой: {e}")
                order_info = {'orderId': self.current_order_id}
                
            # Отмена ордера
            cancel_result = self.api_client.cancel_order(
                category='linear',
                symbol=self.symbol,
                orderId=self.current_order_id
            )
            
            # Логирование события отмены ордера
            self._log_strategy_event(
                "ORDER_CANCELLED",
                f"Ордер {self.current_order_id} отменен",
                f"Order {self.current_order_id} cancelled",
                {
                    'order_id': self.current_order_id,
                    'symbol': self.symbol,
                    'order_info': order_info,
                    'cancel_result': cancel_result
                }
            )
            
            # Сброс ID текущего ордера
            self.current_order_id = None
            
            return {
                'status': 'success',
                'message': f"Ордер {self.current_order_id} успешно отменен",
                'order_info': order_info,
                'cancel_result': cancel_result
            }
            
        except Exception as e:
            error_msg = f"Ошибка при отмене ордера {self.current_order_id}: {e}"
            self.logger.error(error_msg)
            
            # Логирование ошибки
            self._log_strategy_event(
                "ORDER_CANCEL_ERROR",
                error_msg,
                f"Error cancelling order {self.current_order_id}: {type(e).__name__}: {str(e)}",
                {
                    'order_id': self.current_order_id,
                    'symbol': self.symbol,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            
            return {
                'status': 'error',
                'message': error_msg,
                'order_id': self.current_order_id,
                'error': str(e)
            }
            
    def update_stop_loss_take_profit(self, stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> Dict[str, Any]:
        """
        Обновление стоп-лосса и тейк-профита для текущей позиции
        
        Args:
            stop_loss: Новая цена стоп-лосса
            take_profit: Новая цена тейк-профита
            
        Returns:
            Результат обновления
        """
        if not self.current_position:
            return {
                'status': 'error',
                'message': 'Нет активной позиции для обновления стоп-лосса и тейк-профита'
            }
            
        if stop_loss is None and take_profit is None:
            return {
                'status': 'error',
                'message': 'Необходимо указать хотя бы один параметр: stop_loss или take_profit'
            }
            
        try:
            # Получение информации о текущей позиции
            position_info = self.api_client.get_position_info(
                category='linear',
                symbol=self.symbol
            )
            
            # Проверка наличия позиции
            if not position_info or 'size' not in position_info or float(position_info['size']) == 0:
                return {
                    'status': 'error',
                    'message': 'Нет активной позиции на бирже'
                }
                
            # Определение параметров для обновления
            update_params = {
                'category': 'linear',
                'symbol': self.symbol,
                'positionIdx': 0  # 0 для одностороннего режима
            }
            
            # Добавление стоп-лосса, если указан
            if stop_loss is not None:
                update_params['stopLoss'] = str(stop_loss)
                self.stop_loss_price = stop_loss
                
            # Добавление тейк-профита, если указан
            if take_profit is not None:
                update_params['takeProfit'] = str(take_profit)
                self.take_profit_price = take_profit
                
            # Обновление позиции через API
            result = self.api_client.set_trading_stop(**update_params)
            
            # Логирование события обновления
            self._log_strategy_event(
                "POSITION_SL_TP_UPDATED",
                f"Обновлены SL/TP для позиции {self.symbol}: SL={stop_loss}, TP={take_profit}",
                f"Updated SL/TP for position {self.symbol}: SL={stop_loss}, TP={take_profit}",
                {
                    'symbol': self.symbol,
                    'position_type': self.current_position,
                    'old_stop_loss': self.stop_loss_price if stop_loss is None else None,
                    'new_stop_loss': stop_loss,
                    'old_take_profit': self.take_profit_price if take_profit is None else None,
                    'new_take_profit': take_profit,
                    'api_result': result
                }
            )
            
            return {
                'status': 'success',
                'message': 'Стоп-лосс и тейк-профит успешно обновлены',
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'api_result': result
            }
            
        except Exception as e:
            error_msg = f"Ошибка при обновлении стоп-лосса и тейк-профита: {e}"
            self.logger.error(error_msg)
            
            # Логирование ошибки
            self._log_strategy_event(
                "POSITION_SL_TP_UPDATE_ERROR",
                error_msg,
                f"Error updating SL/TP for position {self.symbol}: {type(e).__name__}: {str(e)}",
                {
                    'symbol': self.symbol,
                    'position_type': self.current_position,
                    'requested_stop_loss': stop_loss,
                    'requested_take_profit': take_profit,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            
            return {
                'status': 'error',
                'message': error_msg,
                'error': str(e)
            }
            
    def partial_close_position(self, close_percent: float) -> Dict[str, Any]:
        """
        Частичное закрытие текущей позиции
        
        Args:
            close_percent: Процент позиции для закрытия (0-100)
            
        Returns:
            Результат закрытия части позиции
        """
        if not self.current_position:
            return {
                'status': 'error',
                'message': 'Нет активной позиции для частичного закрытия'
            }
            
        if close_percent <= 0 or close_percent > 100:
            return {
                'status': 'error',
                'message': 'Процент закрытия должен быть в диапазоне от 0 до 100'
            }
            
        try:
            # Получение информации о текущей позиции
            position_info = self.api_client.get_position_info(
                category='linear',
                symbol=self.symbol
            )
            
            # Проверка наличия позиции
            if not position_info or 'size' not in position_info or float(position_info['size']) == 0:
                return {
                    'status': 'error',
                    'message': 'Нет активной позиции на бирже'
                }
                
            # Расчет размера для закрытия
            current_size = float(position_info['size'])
            close_size = current_size * (close_percent / 100.0)
            
            # Определение направления закрытия
            side = 'Sell' if self.current_position == 'long' else 'Buy'
            
            # Создание ордера на закрытие части позиции
            order_params = {
                'category': 'linear',
                'symbol': self.symbol,
                'side': side,
                'orderType': 'Market',
                'qty': str(close_size),
                'reduceOnly': True
            }
            
            # Размещение ордера через API
            order_result = self.api_client.place_order(**order_params)
            
            # Получение ID ордера
            order_id = None
            if order_result and 'result' in order_result and 'orderId' in order_result['result']:
                order_id = order_result['result']['orderId']
            
            # Обновление размера позиции в стратегии
            remaining_size = current_size - close_size
            if remaining_size > 0:
                self.position_size = remaining_size
            else:
                # Если закрыли всю позицию, сбрасываем статус
                self._update_position_status(None)
            
            # Логирование события частичного закрытия
            self._log_strategy_event(
                "POSITION_PARTIAL_CLOSE",
                f"Частично закрыта позиция {self.symbol}: {close_percent}% ({close_size} из {current_size})",
                f"Partially closed position {self.symbol}: {close_percent}% ({close_size} of {current_size})",
                {
                    'symbol': self.symbol,
                    'position_type': self.current_position,
                    'close_percent': close_percent,
                    'close_size': close_size,
                    'original_size': current_size,
                    'remaining_size': remaining_size,
                    'order_id': order_id,
                    'order_result': order_result
                }
            )
            
            return {
                'status': 'success',
                'message': f"Успешно закрыто {close_percent}% позиции",
                'close_percent': close_percent,
                'close_size': close_size,
                'original_size': current_size,
                'remaining_size': remaining_size,
                'order_id': order_id,
                'order_result': order_result
            }
            
        except Exception as e:
            error_msg = f"Ошибка при частичном закрытии позиции: {e}"
            self.logger.error(error_msg)
            
            # Логирование ошибки
            self._log_strategy_event(
                "POSITION_PARTIAL_CLOSE_ERROR",
                error_msg,
                f"Error partially closing position {self.symbol}: {type(e).__name__}: {str(e)}",
                {
                    'symbol': self.symbol,
                    'position_type': self.current_position,
                    'close_percent': close_percent,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            
            return {
                'status': 'error',
                'message': error_msg,
                'error': str(e)
            }
            
    def modify_position_size(self, new_size: float, is_increase: bool = True) -> Dict[str, Any]:
        """
        Изменение размера текущей позиции (увеличение или уменьшение)
        
        Args:
            new_size: Размер для добавления или уменьшения позиции
            is_increase: True для увеличения позиции, False для уменьшения
            
        Returns:
            Результат изменения размера позиции
        """
        if not self.current_position:
            return {
                'status': 'error',
                'message': 'Нет активной позиции для изменения размера'
            }
            
        if new_size <= 0:
            return {
                'status': 'error',
                'message': 'Размер изменения должен быть положительным числом'
            }
            
        try:
            # Получение информации о текущей позиции
            position_info = self.api_client.get_position_info(
                category='linear',
                symbol=self.symbol
            )
            
            # Проверка наличия позиции
            if not position_info or 'size' not in position_info or float(position_info['size']) == 0:
                return {
                    'status': 'error',
                    'message': 'Нет активной позиции на бирже'
                }
                
            current_size = float(position_info['size'])
            
            # Определение направления ордера
            if is_increase:
                # Для увеличения позиции используем то же направление, что и у текущей позиции
                side = 'Buy' if self.current_position == 'long' else 'Sell'
                action_type = 'увеличения'
                action_type_en = 'increase'
                reduce_only = False
            else:
                # Для уменьшения позиции используем противоположное направление
                side = 'Sell' if self.current_position == 'long' else 'Buy'
                action_type = 'уменьшения'
                action_type_en = 'decrease'
                reduce_only = True
                
                # Проверка, что размер уменьшения не превышает текущий размер позиции
                if new_size >= current_size:
                    return {
                        'status': 'error',
                        'message': f'Размер уменьшения ({new_size}) не может быть больше или равен текущему размеру позиции ({current_size})'
                    }
            
            # Создание ордера на изменение размера позиции
            order_params = {
                'category': 'linear',
                'symbol': self.symbol,
                'side': side,
                'orderType': 'Market',
                'qty': str(new_size),
                'reduceOnly': reduce_only
            }
            
            # Размещение ордера через API
            order_result = self.api_client.place_order(**order_params)
            
            # Получение ID ордера
            order_id = None
            if order_result and 'result' in order_result and 'orderId' in order_result['result']:
                order_id = order_result['result']['orderId']
            
            # Обновление размера позиции в стратегии
            if is_increase:
                self.position_size = current_size + new_size
            else:
                remaining_size = current_size - new_size
                if remaining_size > 0:
                    self.position_size = remaining_size
                else:
                    # Если закрыли всю позицию, сбрасываем статус
                    self._update_position_status(None)
            
            # Логирование события изменения размера позиции
            self._log_strategy_event(
                f"POSITION_SIZE_{action_type_en.upper()}",
                f"Изменен размер позиции {self.symbol} ({action_type}): {new_size} (было: {current_size}, стало: {self.position_size})",
                f"Modified position size {self.symbol} ({action_type_en}): {new_size} (was: {current_size}, now: {self.position_size})",
                {
                    'symbol': self.symbol,
                    'position_type': self.current_position,
                    'is_increase': is_increase,
                    'size_change': new_size,
                    'original_size': current_size,
                    'new_size': self.position_size,
                    'order_id': order_id,
                    'order_result': order_result
                }
            )
            
            return {
                'status': 'success',
                'message': f"Успешно изменен размер позиции ({action_type})",
                'is_increase': is_increase,
                'size_change': new_size,
                'original_size': current_size,
                'new_size': self.position_size,
                'order_id': order_id,
                'order_result': order_result
            }
            
        except Exception as e:
            error_msg = f"Ошибка при изменении размера позиции: {e}"
            self.logger.error(error_msg)
            
            # Логирование ошибки
            self._log_strategy_event(
                "POSITION_SIZE_MODIFY_ERROR",
                error_msg,
                f"Error modifying position size {self.symbol}: {type(e).__name__}: {str(e)}",
                {
                    'symbol': self.symbol,
                    'position_type': self.current_position,
                    'is_increase': is_increase,
                    'requested_size': new_size,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            
            return {
                'status': 'error',
                'message': error_msg,
                'error': str(e)
            }
            
    def get_historical_data(self, interval: str = '1h', limit: int = 100) -> Dict[str, Any]:
        """
        Получение исторических данных для анализа
        
        Args:
            interval: Интервал свечей (1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d, 1w, 1M)
            limit: Количество свечей для получения (максимум 1000)
            
        Returns:
            Исторические данные в формате словаря
        """
        try:
            # Проверка валидности интервала
            valid_intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w', '1M']
            if interval not in valid_intervals:
                return {
                    'status': 'error',
                    'message': f'Неверный интервал. Допустимые значения: {valid_intervals}'
                }
                
            # Проверка лимита
            if limit <= 0 or limit > 1000:
                return {
                    'status': 'error',
                    'message': 'Количество свечей должно быть от 1 до 1000'
                }
                
            # Получение исторических данных через API
            kline_params = {
                'category': 'linear',
                'symbol': self.symbol,
                'interval': interval,
                'limit': limit
            }
            
            kline_result = self.api_client.get_kline(**kline_params)
            
            # Проверка результата
            if not kline_result or 'result' not in kline_result or 'list' not in kline_result['result']:
                return {
                    'status': 'error',
                    'message': 'Не удалось получить исторические данные',
                    'raw_result': kline_result
                }
                
            # Преобразование данных в удобный формат
            candles = kline_result['result']['list']
            formatted_candles = []
            
            for candle in candles:
                # Bybit возвращает данные в формате [timestamp, open, high, low, close, volume, ...]
                formatted_candles.append({
                    'timestamp': int(candle[0]),
                    'open': float(candle[1]),
                    'high': float(candle[2]),
                    'low': float(candle[3]),
                    'close': float(candle[4]),
                    'volume': float(candle[5])
                })
                
            # Логирование получения исторических данных
            self._log_strategy_event(
                "HISTORICAL_DATA_FETCHED",
                f"Получены исторические данные {self.symbol}, интервал: {interval}, количество: {len(formatted_candles)}",
                f"Fetched historical data for {self.symbol}, interval: {interval}, count: {len(formatted_candles)}",
                {
                    'symbol': self.symbol,
                    'interval': interval,
                    'count': len(formatted_candles)
                }
            )
                
            return {
                'status': 'success',
                'interval': interval,
                'symbol': self.symbol,
                'candles': formatted_candles,
                'count': len(formatted_candles)
            }
            
        except Exception as e:
            error_msg = f"Ошибка при получении исторических данных: {e}"
            self.logger.error(error_msg)
            
            # Логирование ошибки
            self._log_strategy_event(
                "HISTORICAL_DATA_ERROR",
                error_msg,
                f"Error fetching historical data for {self.symbol}: {type(e).__name__}: {str(e)}",
                {
                    'symbol': self.symbol,
                    'interval': interval,
                    'limit': limit,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            
            return {
                'status': 'error',
                'message': error_msg,
                'error': str(e)
            }
            
    def get_risk_status(self) -> Dict[str, Any]:
        """
        Получение текущего статуса рисков стратегии
        
        Returns:
            Информация о текущих рисках стратегии
        """
        # Здесь должна быть реализация оценки рисков стратегии
        # Например, анализ текущей позиции, убытков, волатильности и т.д.
        
        return {
            'status': 'success',
            'risk_level': 'low',  # low, medium, high
            'max_drawdown': 0.0,  # максимальная просадка в %
            'current_drawdown': 0.0,  # текущая просадка в %
            'position_risk': 'low'  # оценка риска текущей позиции
        }
        
    def force_close_position(self) -> Dict[str, Any]:
        """
        Принудительное закрытие текущей позиции
        
        Returns:
            Результат закрытия позиции
        """
        if not self.current_position:
            return {
                'status': 'error',
                'message': 'Нет активной позиции для закрытия'
            }
            
        try:
            # Получение информации о текущей позиции
            position_info = self.api_client.get_position_info(
                category='linear',
                symbol=self.symbol
            )
            
            # Проверка наличия позиции
            if not position_info or 'size' not in position_info or float(position_info['size']) == 0:
                return {
                    'status': 'error',
                    'message': 'Нет активной позиции на бирже'
                }
                
            current_size = float(position_info['size'])
            
            # Определение направления ордера для закрытия позиции
            side = 'Sell' if self.current_position == 'long' else 'Buy'
            
            # Создание ордера на закрытие позиции
            order_params = {
                'category': 'linear',
                'symbol': self.symbol,
                'side': side,
                'orderType': 'Market',
                'qty': str(current_size),
                'reduceOnly': True
            }
            
            # Размещение ордера через API
            order_result = self.api_client.place_order(**order_params)
            
            # Получение ID ордера
            order_id = None
            if order_result and 'result' in order_result and 'orderId' in order_result['result']:
                order_id = order_result['result']['orderId']
            
            # Сброс статуса позиции
            self._update_position_status(None)
            
            # Логирование события закрытия позиции
            self._log_strategy_event(
                "POSITION_FORCE_CLOSED",
                f"Принудительно закрыта позиция {self.symbol} размером {current_size}",
                f"Force closed position {self.symbol} with size {current_size}",
                {
                    'symbol': self.symbol,
                    'position_type': self.current_position,
                    'size': current_size,
                    'order_id': order_id,
                    'order_result': order_result
                }
            )
            
            return {
                'status': 'success',
                'message': 'Позиция успешно закрыта',
                'size': current_size,
                'order_id': order_id,
                'order_result': order_result
            }
            
        except Exception as e:
            error_msg = f"Ошибка при закрытии позиции: {e}"
            self.logger.error(error_msg)
            
            # Логирование ошибки
            self._log_strategy_event(
                "POSITION_FORCE_CLOSE_ERROR",
                error_msg,
                f"Error force closing position {self.symbol}: {type(e).__name__}: {str(e)}",
                {
                    'symbol': self.symbol,
                    'position_type': self.current_position,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            
            return {
                'status': 'error',
                'message': error_msg,
                'error': str(e)
            }
            
    def reset_risk_limits(self) -> Dict[str, Any]:
        """
        Сброс лимитов риска для стратегии
        
        Returns:
            Словарь с результатом операции
        """
        try:
            # Сброс лимитов риска в риск-менеджере
            self.risk_manager.reset_limits()
            
            # Логирование события сброса лимитов
            self._log_strategy_event(
                "RISK_LIMITS_RESET",
                f"Сброшены лимиты риска для стратегии {self.strategy_name}",
                f"Risk limits reset for strategy {self.strategy_name}",
                {
                    'strategy_name': self.strategy_name,
                    'symbol': self.symbol
                }
            )
            
            return {
                'status': 'success',
                'message': 'Лимиты риска успешно сброшены',
                'strategy_name': self.strategy_name,
                'symbol': self.symbol
            }
            
        except Exception as e:
            error_msg = f"Ошибка при сбросе лимитов риска: {e}"
            self.logger.error(error_msg)
            
            # Логирование ошибки
            self._log_strategy_event(
                "RISK_LIMITS_RESET_ERROR",
                error_msg,
                f"Error resetting risk limits for {self.strategy_name}: {type(e).__name__}: {str(e)}",
                {
                    'strategy_name': self.strategy_name,
                    'symbol': self.symbol,
                    'error': str(e),
                    'error_type': type(e).__name__
                }
            )
            
            return {
                'status': 'error',
                'message': error_msg,
                'error': str(e)
            }
    
    def get_risk_assessment(self) -> Dict[str, Any]:
        """
        Получение детальной информации о рисках
        
        Returns:
            Словарь с информацией о рисках
        """
        return self.risk_manager.get_risk_assessment()
    
    def update_risk_config(self, new_config: Dict[str, Any]) -> bool:
        """
        Обновление конфигурации риск-менеджмента
        
        Args:
            new_config: Новая конфигурация рисков
            
        Returns:
            True если обновление успешно
        """
        try:
            self.risk_manager.update_config(new_config)
            
            # Обновление локальных параметров для совместимости
            if 'max_daily_loss_pct' in new_config:
                self.max_daily_loss = new_config['max_daily_loss_pct']
            if 'max_consecutive_losses' in new_config:
                self.max_consecutive_losses = new_config['max_consecutive_losses']
            
            self.logger.info("Конфигурация риск-менеджмента обновлена")
            self._log_strategy_event("UPDATE_RISK_CONFIG", "Обновлена конфигурация рисков", data=new_config)
            
            return True
        except Exception as e:
            self.logger.error(f"Ошибка обновления конфигурации рисков: {e}")
            return False