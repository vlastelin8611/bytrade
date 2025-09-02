#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер базы данных для Bybit Trading Bot

Обеспечивает работу с SQLite базой данных для хранения:
- Логов всех операций
- Торговых данных
- Исторических данных
- Настроек стратегий
- Результатов анализа
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text, Boolean, JSON, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import json

Base = declarative_base()

class LogEntry(Base):
    """
    Модель для хранения логов приложения
    """
    __tablename__ = 'log_entries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    level = Column(String(10), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    logger_name = Column(String(50), nullable=False)
    module = Column(String(50))
    function = Column(String(50))
    line_number = Column(Integer)
    message = Column(Text, nullable=False)
    exception = Column(Text)
    session_id = Column(String(36))  # UUID сессии

class TradeEntry(Base):
    """
    Модель для хранения торговых операций
    """
    __tablename__ = 'trade_entries'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    order_id = Column(String(50), unique=True)
    symbol = Column(String(20), nullable=False)
    side = Column(String(10), nullable=False)  # Buy/Sell
    order_type = Column(String(20), nullable=False)  # Market/Limit
    quantity = Column(Float, nullable=False)
    price = Column(Float)
    executed_price = Column(Float)
    executed_quantity = Column(Float)
    status = Column(String(20), nullable=False)  # New/PartiallyFilled/Filled/Cancelled
    strategy_name = Column(String(50))
    profit_loss = Column(Float)
    commission = Column(Float)
    environment = Column(String(10), default='testnet')  # testnet/mainnet
    additional_data = Column(JSON)

class StrategyLog(Base):
    """
    Модель для хранения логов стратегий
    """
    __tablename__ = 'strategy_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    strategy_name = Column(String(50), nullable=False)
    symbol = Column(String(20))
    action = Column(String(50), nullable=False)
    technical_details = Column(Text)  # Технические детали для анализа
    human_readable = Column(Text)  # Человекочитаемое описание на русском
    data = Column(JSON)  # Дополнительные данные
    session_id = Column(String(36))

class MarketData(Base):
    """
    Модель для хранения рыночных данных
    """
    __tablename__ = 'market_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)  # 1m, 5m, 1h, 1d
    open_price = Column(Float, nullable=False)
    high_price = Column(Float, nullable=False)
    low_price = Column(Float, nullable=False)
    close_price = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)
    additional_indicators = Column(JSON)

class RiskEvent(Base):
    """
    Модель для хранения событий риск-менеджмента
    """
    __tablename__ = 'risk_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    event_type = Column(String(50), nullable=False)  # stop_loss, take_profit, max_drawdown
    symbol = Column(String(20))
    strategy_name = Column(String(50))
    trigger_value = Column(Float)
    current_value = Column(Float)
    action_taken = Column(String(100))
    description = Column(Text)
    severity = Column(String(20))  # low, medium, high, critical

class APIRequest(Base):
    """
    Модель для хранения логов API запросов
    """
    __tablename__ = 'api_requests'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    endpoint = Column(String(200), nullable=False)
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE
    params = Column(JSON)
    response_code = Column(Integer)
    success = Column(Boolean, nullable=False)
    error_message = Column(Text)
    response_time = Column(Float)  # в миллисекундах
    session_id = Column(String(36))

class TickerData(Base):
    """
    Модель для хранения текущих рыночных данных (тикеров)
    """
    __tablename__ = 'ticker_data'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    symbol = Column(String(20), nullable=False, unique=True)
    price = Column(Float, nullable=False)
    change_24h = Column(Float, nullable=False)
    volume_24h = Column(Float, nullable=False)
    high_24h = Column(Float, nullable=False)
    low_24h = Column(Float, nullable=False)
    category = Column(String(20), default='spot')
    risk_level = Column(String(10), default='medium')
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)

class PerformanceMetrics(Base):
    """
    Модель для хранения метрик производительности стратегий
    """
    __tablename__ = 'performance_metrics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    strategy_name = Column(String(50))
    symbol = Column(String(20))
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_profit_loss = Column(Float, default=0.0)
    max_drawdown = Column(Float, default=0.0)
    sharpe_ratio = Column(Float)
    win_rate = Column(Float)
    avg_profit = Column(Float)
    avg_loss = Column(Float)
    additional_metrics = Column(JSON)

class DatabaseManager:
    """
    Менеджер базы данных для торгового бота
    Поддерживает разделение данных для testnet и mainnet режимов
    """
    
    def __init__(self, db_path: Optional[str] = None, environment: str = "testnet"):
        self.logger = logging.getLogger(__name__)
        self.environment = environment
        
        # Определяем путь к базе данных
        if db_path:
            self.db_path = Path(db_path)
        else:
            config_dir = Path.home() / ".bybit_trading_bot"
            config_dir.mkdir(exist_ok=True)
            
            # Разделяем БД для testnet и mainnet
            if environment == "mainnet":
                self.db_path = config_dir / "trading_bot_mainnet.db"
            else:
                self.db_path = config_dir / "trading_bot_testnet.db"
        
        # Создаем движок SQLAlchemy
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,  # Установить True для отладки SQL запросов
            pool_pre_ping=True,
            connect_args={'check_same_thread': False}
        )
        
        # Создаем фабрику сессий
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        self.logger.info(f"Инициализирован менеджер БД ({self.environment}): {self.db_path}")
    
    def get_environment(self) -> str:
        """
        Получение текущего окружения (testnet/mainnet)
        
        Returns:
            Строка с названием окружения
        """
        return self.environment
    
    def switch_environment(self, new_environment: str):
        """
        Переключение окружения БД (требует пересоздания менеджера)
        
        Args:
            new_environment: Новое окружение (testnet/mainnet)
        """
        if new_environment not in ["testnet", "mainnet"]:
            raise ValueError("Окружение должно быть 'testnet' или 'mainnet'")
        
        if new_environment != self.environment:
            self.logger.warning(f"Переключение окружения с {self.environment} на {new_environment} требует пересоздания DatabaseManager")
            raise RuntimeError("Для переключения окружения необходимо создать новый экземпляр DatabaseManager")
    
    def initialize_database(self):
        """
        Инициализация базы данных - создание всех таблиц
        """
        try:
            Base.metadata.create_all(bind=self.engine)
            self.logger.info("База данных успешно инициализирована")
            
            # Создаем индексы для оптимизации запросов
            self._create_indexes()
            
        except SQLAlchemyError as e:
            self.logger.error(f"Ошибка инициализации базы данных: {e}")
            raise
    
    def _create_indexes(self):
        """
        Создание индексов для оптимизации запросов
        """
        indexes = [
            ("idx_log_timestamp", "log_entries(timestamp)", "Индекс для временных меток логов"),
            ("idx_log_level", "log_entries(level)", "Индекс для уровней логов"),
            ("idx_log_logger", "log_entries(logger_name)", "Индекс для имен логгеров"),
            ("idx_trade_timestamp", "trade_entries(timestamp)", "Индекс для временных меток торговых операций"),
            ("idx_trade_symbol", "trade_entries(symbol)", "Индекс для символов торговых операций"),
            ("idx_trade_strategy", "trade_entries(strategy_name)", "Индекс для стратегий торговых операций"),
            ("idx_strategy_timestamp", "strategy_logs(timestamp)", "Индекс для временных меток логов стратегий"),
            ("idx_strategy_name", "strategy_logs(strategy_name)", "Индекс для имен стратегий"),
            ("idx_market_symbol_time", "market_data(symbol, timestamp)", "Составной индекс для рыночных данных"),
            ("idx_market_timeframe", "market_data(timeframe)", "Индекс для таймфреймов рыночных данных")
        ]
        
        try:
            # Используем сессию вместо raw connection для совместимости с SQLite
            with self.get_session() as session:
                for index_name, table_columns, description in indexes:
                    try:
                        sql = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_columns}"
                        session.execute(text(sql))
                        self.logger.debug(f"Создан индекс: {description}")
                    except Exception as index_error:
                        self.logger.error(f"Ошибка создания индекса {index_name}: {index_error}")
                        # Продолжаем создание остальных индексов
                        continue
                
                session.commit()
                self.logger.info("Процесс создания индексов завершен")
                
        except Exception as e:
            self.logger.error(f"Общая ошибка создания индексов: {e}")
            # Не поднимаем исключение, чтобы не блокировать инициализацию БД
    
    def get_session(self) -> Session:
        """
        Получение сессии базы данных
        """
        return self.SessionLocal()
    
    def log_entry(self, log_data: Dict[str, Any]):
        """
        Запись лога в базу данных
        """
        try:
            with self.get_session() as session:
                log_entry = LogEntry(
                    timestamp=log_data.get('timestamp', datetime.utcnow()),
                    level=log_data.get('level', 'INFO'),
                    logger_name=log_data.get('logger_name', ''),
                    module=log_data.get('module'),
                    function=log_data.get('function'),
                    line_number=log_data.get('line_number'),
                    message=log_data.get('message', ''),
                    exception=log_data.get('exception'),
                    session_id=log_data.get('session_id')
                )
                session.add(log_entry)
                session.commit()
                
        except Exception as e:
            # Избегаем рекурсивного логирования
            print(f"Ошибка записи лога в БД: {e}")
    
    def log_trade(self, trade_data: Dict[str, Any]):
        """
        Запись торговой операции в базу данных
        """
        try:
            with self.get_session() as session:
                trade_entry = TradeEntry(
                    timestamp=trade_data.get('timestamp', datetime.utcnow()),
                    order_id=trade_data.get('order_id'),
                    symbol=trade_data.get('symbol'),
                    side=trade_data.get('side'),
                    order_type=trade_data.get('order_type'),
                    quantity=trade_data.get('quantity'),
                    price=trade_data.get('price'),
                    executed_price=trade_data.get('executed_price'),
                    executed_quantity=trade_data.get('executed_quantity'),
                    status=trade_data.get('status'),
                    strategy_name=trade_data.get('strategy_name'),
                    profit_loss=trade_data.get('profit_loss'),
                    commission=trade_data.get('commission'),
                    environment=trade_data.get('environment', 'testnet'),
                    additional_data=trade_data.get('additional_data')
                )
                session.add(trade_entry)
                session.commit()
                
        except Exception as e:
            self.logger.error(f"Ошибка записи торговой операции в БД: {e}")
    
    def log_strategy_action(self, strategy_data: Dict[str, Any]):
        """
        Запись действия стратегии в базу данных
        """
        try:
            with self.get_session() as session:
                strategy_log = StrategyLog(
                    timestamp=strategy_data.get('timestamp', datetime.utcnow()),
                    strategy_name=strategy_data.get('strategy_name'),
                    symbol=strategy_data.get('symbol'),
                    action=strategy_data.get('action'),
                    technical_details=strategy_data.get('technical_details'),
                    human_readable=strategy_data.get('human_readable'),
                    data=strategy_data.get('data'),
                    session_id=strategy_data.get('session_id')
                )
                session.add(strategy_log)
                session.commit()
                
        except Exception as e:
            self.logger.error(f"Ошибка записи лога стратегии в БД: {e}")
    
    def save_market_data(self, market_data: Dict[str, Any]):
        """
        Сохранение рыночных данных
        """
        try:
            with self.get_session() as session:
                data_entry = MarketData(
                    timestamp=market_data.get('timestamp', datetime.utcnow()),
                    symbol=market_data.get('symbol'),
                    timeframe=market_data.get('timeframe'),
                    open_price=market_data.get('open_price'),
                    high_price=market_data.get('high_price'),
                    low_price=market_data.get('low_price'),
                    close_price=market_data.get('close_price'),
                    volume=market_data.get('volume'),
                    additional_indicators=market_data.get('additional_indicators')
                )
                session.add(data_entry)
                session.commit()
                
        except Exception as e:
            self.logger.error(f"Ошибка сохранения рыночных данных: {e}")
    
    def log_risk_event(self, risk_data: Dict[str, Any]):
        """
        Запись события риск-менеджмента
        """
        try:
            with self.get_session() as session:
                risk_event = RiskEvent(
                    timestamp=risk_data.get('timestamp', datetime.utcnow()),
                    event_type=risk_data.get('event_type'),
                    symbol=risk_data.get('symbol'),
                    strategy_name=risk_data.get('strategy_name'),
                    trigger_value=risk_data.get('trigger_value'),
                    current_value=risk_data.get('current_value'),
                    action_taken=risk_data.get('action_taken'),
                    description=risk_data.get('description'),
                    severity=risk_data.get('severity', 'medium')
                )
                session.add(risk_event)
                session.commit()
                
        except Exception as e:
            self.logger.error(f"Ошибка записи события риск-менеджмента: {e}")
    
    def get_strategy_logs(self, strategy_name: str, limit: int = 100) -> List[Dict]:
        """
        Получение логов стратегии
        """
        try:
            with self.get_session() as session:
                logs = session.query(StrategyLog).filter(
                    StrategyLog.strategy_name == strategy_name
                ).order_by(StrategyLog.timestamp.desc()).limit(limit).all()
                
                return [{
                    'timestamp': log.timestamp,
                    'action': log.action,
                    'technical_details': log.technical_details,
                    'human_readable': log.human_readable,
                    'symbol': log.symbol,
                    'data': log.data
                } for log in logs]
                
        except Exception as e:
            self.logger.error(f"Ошибка получения логов стратегии: {e}")
            return []
    
    def get_trade_history(self, symbol: str = None, strategy: str = None, 
                         days: int = 30) -> List[Dict]:
        """
        Получение истории торговых операций
        """
        try:
            with self.get_session() as session:
                query = session.query(TradeEntry)
                
                # Фильтрация по периоду
                start_date = datetime.utcnow() - timedelta(days=days)
                query = query.filter(TradeEntry.timestamp >= start_date)
                
                # Фильтрация по символу
                if symbol:
                    query = query.filter(TradeEntry.symbol == symbol)
                
                # Фильтрация по стратегии
                if strategy:
                    query = query.filter(TradeEntry.strategy_name == strategy)
                
                trades = query.order_by(TradeEntry.timestamp.desc()).all()
                
                return [{
                    'timestamp': trade.timestamp,
                    'order_id': trade.order_id,
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'quantity': trade.quantity,
                    'price': trade.price,
                    'executed_price': trade.executed_price,
                    'status': trade.status,
                    'strategy_name': trade.strategy_name,
                    'profit_loss': trade.profit_loss,
                    'environment': trade.environment
                } for trade in trades]
                
        except Exception as e:
            self.logger.error(f"Ошибка получения истории торговли: {e}")
            return []
    
    def cleanup_old_data(self, days_to_keep: int = 90):
        """
        Очистка старых данных из базы
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            with self.get_session() as session:
                # Удаляем старые логи
                deleted_logs = session.query(LogEntry).filter(
                    LogEntry.timestamp < cutoff_date
                ).delete()
                
                # Удаляем старые рыночные данные (кроме дневных)
                deleted_market = session.query(MarketData).filter(
                    MarketData.timestamp < cutoff_date,
                    MarketData.timeframe != '1d'
                ).delete()
                
                session.commit()
                
                self.logger.info(f"Очищено {deleted_logs} записей логов и {deleted_market} записей рыночных данных")
                
        except Exception as e:
            self.logger.error(f"Ошибка очистки старых данных: {e}")
    
    def backup_database(self, backup_path: Optional[str] = None):
        """
        Создание резервной копии базы данных
        """
        try:
            if not backup_path:
                backup_dir = self.db_path.parent / "backups"
                backup_dir.mkdir(exist_ok=True)
                backup_path = backup_dir / f"trading_bot_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            
            # Простое копирование файла SQLite
            import shutil
            shutil.copy2(self.db_path, backup_path)
            
            self.logger.info(f"Резервная копия создана: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Ошибка создания резервной копии: {e}")
            return None
    
    def log_performance(self, performance_data: Dict[str, Any]):
        """
        Запись метрик производительности в базу данных
        """
        try:
            with self.get_session() as session:
                # Определяем период
                period_start = performance_data.get('period_start', datetime.utcnow() - timedelta(days=1))
                period_end = performance_data.get('period_end', datetime.utcnow())
                
                performance_entry = PerformanceMetrics(
                    timestamp=performance_data.get('timestamp', datetime.utcnow()),
                    strategy_name=performance_data.get('strategy_name'),
                    symbol=performance_data.get('symbol'),
                    period_start=period_start,
                    period_end=period_end,
                    total_trades=performance_data.get('total_trades', 0),
                    winning_trades=performance_data.get('profitable_trades', 0),
                    losing_trades=performance_data.get('total_trades', 0) - performance_data.get('profitable_trades', 0),
                    total_profit_loss=performance_data.get('total_profit', 0.0),
                    max_drawdown=performance_data.get('max_drawdown', 0.0),
                    sharpe_ratio=performance_data.get('sharpe_ratio'),
                    win_rate=performance_data.get('win_rate', 0.0),
                    avg_profit=performance_data.get('avg_profit'),
                    avg_loss=performance_data.get('avg_loss'),
                    additional_metrics=performance_data.get('additional_metrics')
                )
                session.add(performance_entry)
                session.commit()
                
        except Exception as e:
            self.logger.error(f"Ошибка записи метрик производительности в БД: {e}")
    
    def get_performance_summary(self, strategy_name: str = None, 
                              days: int = 30) -> Dict[str, Any]:
        """
        Получение сводки производительности
        """
        try:
            with self.get_session() as session:
                query = session.query(TradeEntry)
                
                # Фильтрация по периоду
                start_date = datetime.utcnow() - timedelta(days=days)
                query = query.filter(TradeEntry.timestamp >= start_date)
                
                # Фильтрация по стратегии
                if strategy_name:
                    query = query.filter(TradeEntry.strategy_name == strategy_name)
                
                trades = query.all()
                
                if not trades:
                    return {'total_trades': 0}
                
                # Расчет метрик
                total_trades = len(trades)
                winning_trades = len([t for t in trades if t.profit_loss and t.profit_loss > 0])
                losing_trades = len([t for t in trades if t.profit_loss and t.profit_loss < 0])
                
                total_pnl = sum([t.profit_loss for t in trades if t.profit_loss])
                win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
                
                return {
                    'total_trades': total_trades,
                    'winning_trades': winning_trades,
                    'losing_trades': losing_trades,
                    'win_rate': round(win_rate, 2),
                    'total_pnl': round(total_pnl, 4) if total_pnl else 0,
                }
                
        except Exception as e:
            self.logger.error(f"Ошибка получения сводки производительности: {e}")
            return {'total_trades': 0}
    
    def log_api_request(self, endpoint: str, method: str, params: Dict = None, 
                       response_code: int = None, success: bool = True, 
                       error_message: str = None, response_time: float = None):
        """
        Запись лога API запроса в базу данных
        """
        try:
            with self.get_session() as session:
                api_request = APIRequest(
                    endpoint=endpoint,
                    method=method.upper(),
                    params=params,
                    response_code=response_code,
                    success=success,
                    error_message=error_message,
                    response_time=response_time
                )
                session.add(api_request)
                session.commit()
                
        except Exception as e:
            self.logger.error(f"Ошибка записи лога API запроса: {e}")
    
    def save_ticker_data(self, ticker_data: List[Dict[str, Any]]):
        """
        Сохранение данных тикеров в базу данных
        
        Args:
            ticker_data: Список словарей с данными тикеров
        """
        try:
            with self.get_session() as session:
                for ticker in ticker_data:
                    # Проверяем существует ли запись для данного символа
                    existing = session.query(TickerData).filter_by(symbol=ticker['symbol']).first()
                    
                    if existing:
                        # Обновляем существующую запись
                        existing.price = ticker['price']
                        existing.change_24h = ticker['change_24h']
                        existing.volume_24h = ticker['volume_24h']
                        existing.high_24h = ticker['high_24h']
                        existing.low_24h = ticker['low_24h']
                        existing.risk_level = ticker.get('risk_level', 'medium')
                        existing.last_updated = datetime.utcnow()
                    else:
                        # Создаем новую запись
                        ticker_entry = TickerData(
                            symbol=ticker['symbol'],
                            price=ticker['price'],
                            change_24h=ticker['change_24h'],
                            volume_24h=ticker['volume_24h'],
                            high_24h=ticker['high_24h'],
                            low_24h=ticker['low_24h'],
                            risk_level=ticker.get('risk_level', 'medium')
                        )
                        session.add(ticker_entry)
                
                session.commit()
                self.logger.info(f"Сохранено {len(ticker_data)} записей тикеров")
                
        except SQLAlchemyError as e:
            self.logger.error(f"Ошибка сохранения данных тикеров: {e}")
            raise
    
    def get_cached_ticker_data(self, max_age_minutes: int = 30) -> List[Dict[str, Any]]:
        """
        Получение кэшированных данных тикеров
        
        Args:
            max_age_minutes: Максимальный возраст данных в минутах
            
        Returns:
            Список словарей с данными тикеров
        """
        try:
            with self.get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
                
                tickers = session.query(TickerData).filter(
                    TickerData.last_updated >= cutoff_time
                ).order_by(TickerData.last_updated.desc()).all()
                
                result = []
                for ticker in tickers:
                    result.append({
                        'symbol': ticker.symbol,
                        'price': ticker.price,
                        'change_24h': ticker.change_24h,
                        'volume_24h': ticker.volume_24h,
                        'high_24h': ticker.high_24h,
                        'low_24h': ticker.low_24h,
                        'risk_level': ticker.risk_level,
                        'last_updated': ticker.last_updated
                    })
                
                self.logger.info(f"Загружено {len(result)} кэшированных тикеров")
                return result
                
        except SQLAlchemyError as e:
            self.logger.error(f"Ошибка загрузки кэшированных данных тикеров: {e}")
            return []
    
    def get_outdated_tickers(self, max_age_minutes: int = 30) -> List[str]:
        """
        Получение списка символов с устаревшими данными
        
        Args:
            max_age_minutes: Максимальный возраст данных в минутах
            
        Returns:
            Список символов с устаревшими данными
        """
        try:
            with self.get_session() as session:
                cutoff_time = datetime.utcnow() - timedelta(minutes=max_age_minutes)
                
                outdated = session.query(TickerData.symbol).filter(
                    TickerData.last_updated < cutoff_time
                ).all()
                
                return [ticker.symbol for ticker in outdated]
                
        except SQLAlchemyError as e:
            self.logger.error(f"Ошибка получения устаревших тикеров: {e}")
            return []

    def close(self):
        """
        Закрытие соединения с базой данных
        """
        try:
            self.engine.dispose()
            self.logger.info("Соединение с базой данных закрыто")
        except Exception as e:
            self.logger.error(f"Ошибка закрытия соединения с БД: {e}")