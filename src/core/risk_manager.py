import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class RiskLevel(Enum):
    """Уровни риска"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class RiskMetrics:
    """Метрики риска"""
    daily_pnl: float = 0.0
    daily_loss_pct: float = 0.0
    consecutive_losses: int = 0
    total_trades_today: int = 0
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    risk_level: RiskLevel = RiskLevel.LOW

class RiskManager:
    """
    Централизованный менеджер рисков для торговых стратегий
    
    Реализует требования:
    - Не более 20% баланса в день
    - Стоп после 3 неудач подряд
    - Стоп-лоссы до 40%
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger("risk_manager")
        
        # Специальный логгер для риск-событий
        self.risk_logger = logging.getLogger("risk_events")
        self.risk_logger.setLevel(logging.INFO)
        
        # Основные лимиты риска
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 20.0)  # 20% от баланса
        self.max_consecutive_losses = config.get('max_consecutive_losses', 3)
        self.max_stop_loss_pct = config.get('max_stop_loss_pct', 40.0)  # Максимальный стоп-лосс 40%
        self.max_position_size_pct = config.get('max_position_size_pct', 10.0)  # Максимальный размер позиции
        
        # Дополнительные параметры
        self.max_trades_per_day = config.get('max_trades_per_day', 10)
        self.max_drawdown_pct = config.get('max_drawdown_pct', 15.0)
        self.min_confidence_threshold = config.get('min_confidence_threshold', 0.7)
        
        # Текущие метрики
        self.metrics = RiskMetrics()
        self.daily_trades = []
        self.balance_history = []
        self.last_reset_date = datetime.utcnow().date()
        
        # Состояние блокировки
        self.is_blocked = False
        self.block_reason = None
        self.block_until = None
        
        self.logger.info("Менеджер рисков инициализирован")
        self.logger.info(f"Лимиты: дневные потери {self.max_daily_loss_pct}%, "
                        f"последовательные потери {self.max_consecutive_losses}, "
                        f"максимальный стоп-лосс {self.max_stop_loss_pct}%")
    
    def check_trade_allowed(self, signal_confidence: float, 
                          position_size_pct: float, 
                          stop_loss_pct: float) -> Tuple[bool, str]:
        """
        Проверка разрешения на торговлю
        
        Args:
            signal_confidence: Уверенность в сигнале (0-1)
            position_size_pct: Размер позиции в процентах от баланса
            stop_loss_pct: Размер стоп-лосса в процентах
            
        Returns:
            Tuple[bool, str]: (разрешено, причина отказа)
        """
        self._update_daily_metrics()
        
        # Проверка блокировки
        if self.is_blocked:
            if self.block_until and datetime.utcnow() < self.block_until:
                return False, f"Торговля заблокирована до {self.block_until}: {self.block_reason}"
            else:
                old_reason = self.block_reason
                self._unblock_trading()
                self._log_risk_event(
                    "trading_unblocked",
                    f"Блокировка торговли снята. Предыдущая причина: {old_reason}",
                    action_taken="Торговля разблокирована",
                    severity="low"
                )
        
        # Проверка дневных потерь
        if abs(self.metrics.daily_loss_pct) >= self.max_daily_loss_pct:
            reason = f"Превышен лимит дневных потерь: {self.metrics.daily_loss_pct:.2f}%"
            self._log_risk_event(
                "daily_loss_limit_exceeded",
                reason,
                trigger_value=self.max_daily_loss_pct,
                current_value=abs(self.metrics.daily_loss_pct),
                action_taken="Торговля заблокирована",
                severity="high"
            )
            self._block_trading(reason, hours=24)
            return False, "Превышен лимит дневных потерь"
        
        # Проверка последовательных потерь
        if self.metrics.consecutive_losses >= self.max_consecutive_losses:
            reason = f"Превышен лимит последовательных потерь: {self.metrics.consecutive_losses}"
            self._log_risk_event(
                "consecutive_losses_limit_exceeded",
                reason,
                trigger_value=self.max_consecutive_losses,
                current_value=self.metrics.consecutive_losses,
                action_taken="Торговля заблокирована",
                severity="high"
            )
            self._block_trading(reason, hours=4)
            return False, "Превышен лимит последовательных потерь"
        
        # Проверка размера стоп-лосса
        if stop_loss_pct > self.max_stop_loss_pct:
            self._log_risk_event(
                "stop_loss_limit_exceeded",
                f"Стоп-лосс превышает лимит: {stop_loss_pct:.2f}% > {self.max_stop_loss_pct}%",
                trigger_value=self.max_stop_loss_pct,
                current_value=stop_loss_pct,
                action_taken="Сделка отклонена",
                severity="medium"
            )
            return False, f"Стоп-лосс {stop_loss_pct}% превышает максимальный {self.max_stop_loss_pct}%"
        
        # Проверка размера позиции
        if position_size_pct > self.max_position_size_pct:
            self._log_risk_event(
                "position_size_limit_exceeded",
                f"Размер позиции превышает лимит: {position_size_pct:.2f}% > {self.max_position_size_pct}%",
                trigger_value=self.max_position_size_pct,
                current_value=position_size_pct,
                action_taken="Сделка отклонена",
                severity="medium"
            )
            return False, f"Размер позиции {position_size_pct}% превышает максимальный {self.max_position_size_pct}%"
        
        # Проверка уверенности в сигнале
        if signal_confidence < self.min_confidence_threshold:
            self._log_risk_event(
                "low_confidence_signal",
                f"Низкий уровень уверенности: {signal_confidence:.2f} < {self.min_confidence_threshold}",
                trigger_value=self.min_confidence_threshold,
                current_value=signal_confidence,
                action_taken="Сделка отклонена",
                severity="low"
            )
            return False, f"Низкая уверенность в сигнале: {signal_confidence:.2f}"
        
        # Проверка количества сделок в день
        if self.metrics.total_trades_today >= self.max_trades_per_day:
            self._log_risk_event(
                "daily_trades_limit_exceeded",
                f"Превышен лимит сделок в день: {self.metrics.total_trades_today}/{self.max_trades_per_day}",
                trigger_value=self.max_trades_per_day,
                current_value=self.metrics.total_trades_today,
                action_taken="Сделка отклонена",
                severity="medium"
            )
            return False, f"Превышен лимит сделок в день: {self.metrics.total_trades_today}"
        
        # Проверка просадки
        if self.metrics.current_drawdown >= self.max_drawdown_pct:
            reason = f"Превышена максимальная просадка: {self.metrics.current_drawdown:.2f}%"
            self._log_risk_event(
                "max_drawdown_exceeded",
                reason,
                trigger_value=self.max_drawdown_pct,
                current_value=self.metrics.current_drawdown,
                action_taken="Торговля заблокирована",
                severity="high"
            )
            self._block_trading(reason, hours=12)
            return False, "Превышена максимальная просадка"
        
        # Логируем успешное прохождение проверок
        self._log_risk_event(
            "trade_approved",
            f"Сделка одобрена: размер {position_size_pct:.2f}%, уверенность {signal_confidence:.2f}, стоп-лосс {stop_loss_pct:.2f}%",
            action_taken="Сделка одобрена",
            severity="low"
        )
        
        return True, "Торговля разрешена"
    
    def record_trade(self, trade_result: Dict[str, Any]):
        """
        Запись результата сделки
        
        Args:
            trade_result: Результат сделки с полями:
                - pnl: Прибыль/убыток
                - pnl_pct: Прибыль/убыток в процентах
                - is_win: Была ли сделка прибыльной
                - timestamp: Время сделки
                - symbol: Торговый символ (опционально)
                - strategy_name: Название стратегии (опционально)
        """
        try:
            trade_data = {
                'timestamp': trade_result.get('timestamp', datetime.utcnow()),
                'pnl': trade_result.get('pnl', 0.0),
                'pnl_pct': trade_result.get('pnl_pct', 0.0),
                'is_win': trade_result.get('is_win', False),
                'symbol': trade_result.get('symbol'),
                'strategy_name': trade_result.get('strategy_name')
            }
            
            self.daily_trades.append(trade_data)
            
            # Обновление метрик
            self._update_metrics_after_trade(trade_data)
            
            # Логируем результат сделки
            self._log_risk_event(
                "trade_completed",
                f"Сделка завершена: PnL {trade_data['pnl_pct']:.2f}% ({'прибыль' if trade_data['is_win'] else 'убыток'})",
                symbol=trade_data['symbol'],
                strategy_name=trade_data['strategy_name'],
                current_value=trade_data['pnl_pct'],
                action_taken="Обновлены метрики риска",
                severity="low" if trade_data['is_win'] else "medium"
            )
            
            self.logger.info(f"Записана сделка: PnL {trade_data['pnl_pct']:.2f}%, "
                           f"Результат: {'Прибыль' if trade_data['is_win'] else 'Убыток'}")
            
        except Exception as e:
            self.logger.error(f"Ошибка записи сделки: {e}")
    
    def get_risk_assessment(self) -> Dict[str, Any]:
        """
        Получение текущей оценки рисков
        
        Returns:
            Словарь с оценкой рисков
        """
        self._update_daily_metrics()
        
        return {
            'risk_level': self.metrics.risk_level.value,
            'is_blocked': self.is_blocked,
            'block_reason': self.block_reason,
            'block_until': self.block_until,
            'daily_loss_pct': self.metrics.daily_loss_pct,
            'consecutive_losses': self.metrics.consecutive_losses,
            'trades_today': self.metrics.total_trades_today,
            'current_drawdown': self.metrics.current_drawdown,
            'max_drawdown': self.metrics.max_drawdown,
            'win_rate': self.metrics.win_rate,
            'remaining_daily_risk': max(0, self.max_daily_loss_pct - abs(self.metrics.daily_loss_pct)),
            'trades_remaining': max(0, self.max_trades_per_day - self.metrics.total_trades_today)
        }
    
    def _update_daily_metrics(self):
        """Обновление дневных метрик"""
        current_date = datetime.utcnow().date()
        
        # Сброс дневных метрик в новый день
        if current_date != self.last_reset_date:
            self._reset_daily_metrics()
            self.last_reset_date = current_date
        
        # Расчет дневных метрик
        today_trades = [t for t in self.daily_trades 
                       if t['timestamp'].date() == current_date]
        
        self.metrics.total_trades_today = len(today_trades)
        self.metrics.daily_pnl = sum(t['pnl'] for t in today_trades)
        self.metrics.daily_loss_pct = sum(t['pnl_pct'] for t in today_trades)
        
        # Расчет винрейта
        if today_trades:
            wins = sum(1 for t in today_trades if t['is_win'])
            self.metrics.win_rate = wins / len(today_trades) * 100
        
        # Определение уровня риска
        self._calculate_risk_level()
    
    def _update_metrics_after_trade(self, trade_data: Dict[str, Any]):
        """Обновление метрик после сделки"""
        # Обновление последовательных потерь
        if trade_data['is_win']:
            self.metrics.consecutive_losses = 0
        else:
            self.metrics.consecutive_losses += 1
        
        # Обновление просадки
        if trade_data['pnl_pct'] < 0:
            self.metrics.current_drawdown += abs(trade_data['pnl_pct'])
            self.metrics.max_drawdown = max(self.metrics.max_drawdown, 
                                          self.metrics.current_drawdown)
        else:
            # Уменьшение просадки при прибыльной сделке
            self.metrics.current_drawdown = max(0, 
                                              self.metrics.current_drawdown - trade_data['pnl_pct'])
    
    def _calculate_risk_level(self):
        """Расчет текущего уровня риска"""
        risk_score = 0
        
        # Дневные потери
        daily_loss_ratio = abs(self.metrics.daily_loss_pct) / self.max_daily_loss_pct
        risk_score += daily_loss_ratio * 40
        
        # Последовательные потери
        consecutive_ratio = self.metrics.consecutive_losses / self.max_consecutive_losses
        risk_score += consecutive_ratio * 30
        
        # Просадка
        drawdown_ratio = self.metrics.current_drawdown / self.max_drawdown_pct
        risk_score += drawdown_ratio * 20
        
        # Количество сделок
        trades_ratio = self.metrics.total_trades_today / self.max_trades_per_day
        risk_score += trades_ratio * 10
        
        # Определение уровня
        if risk_score >= 80:
            self.metrics.risk_level = RiskLevel.CRITICAL
        elif risk_score >= 60:
            self.metrics.risk_level = RiskLevel.HIGH
        elif risk_score >= 30:
            self.metrics.risk_level = RiskLevel.MEDIUM
        else:
            self.metrics.risk_level = RiskLevel.LOW
    
    def _block_trading(self, reason: str, hours: int = 1):
        """Блокировка торговли"""
        self.is_blocked = True
        self.block_reason = reason
        self.block_until = datetime.utcnow() + timedelta(hours=hours)
        
        self.logger.warning(f"Торговля заблокирована на {hours} часов: {reason}")
    
    def _unblock_trading(self):
        """Разблокировка торговли"""
        self.is_blocked = False
        self.block_reason = None
        self.block_until = None
        
        self.logger.info("Торговля разблокирована")
    
    def _reset_daily_metrics(self):
        """Сброс дневных метрик"""
        self.metrics.daily_pnl = 0.0
        self.metrics.daily_loss_pct = 0.0
        self.metrics.total_trades_today = 0
        self.metrics.win_rate = 0.0
        
        # Очистка старых сделок (оставляем только за последние 7 дней)
        week_ago = datetime.utcnow() - timedelta(days=7)
        self.daily_trades = [t for t in self.daily_trades if t['timestamp'] > week_ago]
        
        self.logger.info("Дневные метрики сброшены")
    
    def force_unblock(self):
        """Принудительная разблокировка (для администратора)"""
        self._unblock_trading()
        self.logger.warning("Выполнена принудительная разблокировка торговли")
    
    def get_detailed_report(self) -> str:
        """Получение детального отчета по рискам"""
        assessment = self.get_risk_assessment()
        
        report = f"""
=== ОТЧЕТ ПО УПРАВЛЕНИЮ РИСКАМИ ===

Текущий уровень риска: {assessment['risk_level'].upper()}
Статус торговли: {'ЗАБЛОКИРОВАНА' if assessment['is_blocked'] else 'АКТИВНА'}

Дневные показатели:
- Потери: {assessment['daily_loss_pct']:.2f}% (лимит: {self.max_daily_loss_pct}%)
- Сделок сегодня: {assessment['trades_today']} (лимит: {self.max_trades_per_day})
- Последовательные потери: {assessment['consecutive_losses']} (лимит: {self.max_consecutive_losses})
- Винрейт: {assessment['win_rate']:.1f}%

Просадка:
- Текущая: {assessment['current_drawdown']:.2f}%
- Максимальная: {assessment['max_drawdown']:.2f}%

Остаточные лимиты:
- Дневной риск: {assessment['remaining_daily_risk']:.2f}%
- Сделок осталось: {assessment['trades_remaining']}
"""
        
        if assessment['is_blocked']:
            report += f"\nБлокировка до: {assessment['block_until']}\nПричина: {assessment['block_reason']}"
        
        return report
    
    def reset_daily_stats(self):
        """Принудительный сброс дневной статистики"""
        self._reset_daily_metrics()
        self.logger.info("Дневная статистика принудительно сброшена")
    
    def update_config(self, new_config: Dict[str, Any]):
        """Обновление конфигурации риск-менеджмента"""
        for key, value in new_config.items():
            if hasattr(self, key):
                setattr(self, key, value)
                self.logger.info(f"Обновлен параметр {key}: {value}")
        
        self.logger.info("Конфигурация риск-менеджмента обновлена")
    
    def _log_risk_event(self, event_type: str, description: str, 
                       symbol: str = None, strategy_name: str = None,
                       trigger_value: float = None, current_value: float = None,
                       action_taken: str = None, severity: str = "medium"):
        """Логирование риск-события в базу данных"""
        # Проверяем наличие db_manager в конфигурации
        db_manager = getattr(self, 'db_manager', None)
        if db_manager:
            try:
                db_manager.log_risk_event({
                    'event_type': event_type,
                    'symbol': symbol,
                    'strategy_name': strategy_name,
                    'trigger_value': trigger_value,
                    'current_value': current_value,
                    'action_taken': action_taken,
                    'description': description,
                    'severity': severity
                })
            except Exception as e:
                self.logger.error(f"Ошибка логирования риск-события: {e}")
        
        # Также логируем в обычный лог
        self.risk_logger.warning(f"RISK EVENT [{severity.upper()}]: {description}")