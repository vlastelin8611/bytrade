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
            
            # Обработка сигнала
            result = self._process_signal(signal, confidence, market_data)
            
            # Обновление позиции
            self._update_position_status()
            
            return {
                'status': 'updated',
                'signal': signal.value,
                'confidence': confidence,
                'analysis': analysis,
                'action': result
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
            
            # Здесь должен быть реальный вызов API для открытия позиции
            # order_result = self.api_client.place_order(...)
            
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
            
            # Здесь должен быть реальный вызов API для закрытия позиции
            # close_result = self.api_client.close_position(...)
            
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
        
        # Здесь должна быть логика проверки статуса позиции через API
        # и обновления PnL, проверки стоп-лосса/тейк-профита
        pass
    
    def _log_strategy_event(self, action: str, human_description: str, 
                          technical_details: str = None, data: Dict = None):
        """
        Логирование события стратегии в базу данных
        
        Args:
            action: Тип действия
            human_description: Человекочитаемое описание
            technical_details: Технические детали
            data: Дополнительные данные
        """
        try:
            self.db.log_strategy_action({
                'strategy_name': self.name,
                'symbol': self.symbol,
                'action': action,
                'technical_details': technical_details or f"Action: {action}",
                'human_readable': human_description,
                'data': data or {},
                'session_id': self.session_id
            })
        except Exception as e:
            self.logger.error(f"Ошибка логирования события: {e}")
    
    def get_risk_status(self) -> Dict[str, Any]:
        """
        Получение детальной информации о рисках
        
        Returns:
            Словарь с информацией о рисках
        """
        return self.risk_manager.get_risk_assessment()
    
    def force_close_position(self, reason: str = "Force close") -> Dict[str, Any]:
        """
        Принудительное закрытие позиции
        
        Args:
            reason: Причина принудительного закрытия
            
        Returns:
            Результат операции
        """
        if not self.current_position:
            return {'action': 'no_position'}
        
        self.logger.warning(f"Принудительное закрытие позиции: {reason}")
        return self._close_position(reason)
    
    def reset_risk_limits(self) -> bool:
        """
        Сброс риск-лимитов (например, после анализа ситуации)
        
        Returns:
            True если сброс успешен
        """
        try:
            self.risk_manager.reset_daily_stats()
            self.consecutive_losses = 0
            self.daily_pnl = 0.0
            
            self.logger.info("Риск-лимиты сброшены")
            self._log_strategy_event("RESET_RISKS", "Риск-лимиты сброшены")
            
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сброса риск-лимитов: {e}")
            return False
    
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