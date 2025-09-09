#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вкладка "Активы/рынки"

Отображает:
- Список доступных торговых пар
- Рыночные данные в реальном времени
- Графики цен
- Книга ордеров
- История сделок
"""

import logging
from typing import Dict, List, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QLineEdit, QComboBox, QSplitter, QTabWidget,
    QHeaderView, QAbstractItemView, QMessageBox, QProgressBar,
    QCheckBox, QSpinBox, QDoubleSpinBox, QDialog, QDialogButtonBox,
    QTextEdit, QDateEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSortFilterProxyModel, QDate, QDateTime
from PySide6.QtGui import QFont, QStandardItemModel, QStandardItem, QColor, QPainter
from PySide6.QtCharts import QChart, QChartView, QCandlestickSeries, QCandlestickSet, QLineSeries, QDateTimeAxis, QValueAxis

class MarketDataWorker(QThread):
    """
    Воркер для получения рыночных данных
    """
    
    data_received = Signal(dict)
    error_occurred = Signal(str)
    progress_updated = Signal(int, str)  # прогресс (%), сообщение
    
    def __init__(self, config_manager, bybit_client=None, db_manager=None):
        super().__init__()
        self.config = config_manager
        self.bybit_client = bybit_client
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        self.running = True
    
    def run(self):
        """
        Получение рыночных данных с оптимизацией и логированием
        """
        import time
        start_time = time.time()
        
        try:
            if self.bybit_client:
                self.logger.info("Начало загрузки рыночных данных...")
                self.progress_updated.emit(10, "Подключение к API...")
                
                # Определяем приоритеты обновления
                priority_symbols = self._get_priority_symbols() if self.db_manager else []
                
                # Получение реальных данных через API
                try:
                    # Получаем тикеры для всех инструментов
                    api_start = time.time()
                    self.progress_updated.emit(30, "Загрузка данных с биржи...")
                    tickers_response = self.bybit_client.get_tickers()
                    api_time = time.time() - api_start
                    self.logger.info(f"API запрос выполнен за {api_time:.2f} секунд")
                    
                    # Обрабатываем данные
                    process_start = time.time()
                    tickers = []
                    processed_count = 0
                    
                    if (tickers_response.get('retCode') == 0 and 
                        'result' in tickers_response and 
                        'list' in tickers_response['result']):
                        
                        total_tickers = len(tickers_response['result']['list'])
                        self.logger.info(f"Обработка {total_tickers} тикеров...")
                        self.progress_updated.emit(50, f"Обработка {total_tickers} тикеров...")
                        
                        # Применяем приоритетную логику обновления
                        priority_info = priority_symbols if isinstance(priority_symbols, dict) else {}
                        outdated_symbols = set(priority_info.get('outdated_symbols', []))
                        cached_symbols = priority_info.get('cached_symbols', set())
                        
                        for i, ticker in enumerate(tickers_response['result']['list']):
                            if not self.running:
                                break
                                
                            try:
                                # Фильтруем только USDT пары для ускорения
                                symbol = ticker.get('symbol', '')
                                if not symbol.endswith('USDT'):
                                    continue
                                
                                # Приоритетная обработка:
                                # 1. Символы без данных (не в кэше) - высший приоритет
                                # 2. Устаревшие символы - средний приоритет  
                                # 3. Остальные символы - низкий приоритет
                                is_new_symbol = symbol not in cached_symbols
                                is_outdated = symbol in outdated_symbols
                                
                                # Обрабатываем в порядке приоритета
                                if not (is_new_symbol or is_outdated):
                                    # Пропускаем символы с актуальными данными для ускорения
                                    if processed_count > 50:  # Ограничиваем количество для производительности
                                        continue
                                    
                                tickers.append({
                                    "symbol": symbol,
                                    "price": float(ticker.get('lastPrice', 0)),
                                    "change_24h": float(ticker.get('price24hPcnt', 0)) * 100,
                                    "volume_24h": float(ticker.get('volume24h', 0)),
                                    "high_24h": float(ticker.get('highPrice24h', 0)),
                                    "low_24h": float(ticker.get('lowPrice24h', 0)),
                                    "category": "spot",
                                    "risk_level": "medium"
                                })
                                processed_count += 1
                                
                                # Обновляем прогресс каждые 50 тикеров
                                if i % 50 == 0:
                                    progress = 50 + int((i / total_tickers) * 30)
                                    self.progress_updated.emit(progress, f"Обработано {processed_count} тикеров...")
                                
                            except (ValueError, TypeError) as e:
                                self.logger.warning(f"Ошибка обработки тикера {ticker.get('symbol', 'unknown')}: {e}")
                                continue
                    
                    process_time = time.time() - process_start
                    self.logger.info(f"Обработано {processed_count} тикеров за {process_time:.2f} секунд")
                    
                    self.progress_updated.emit(90, "Сортировка данных...")
                    # Сортируем по объему для лучшего UX
                    tickers.sort(key=lambda x: x['volume_24h'], reverse=True)
                    
                    market_data = {"tickers": tickers}
                    
                except Exception as e:
                    self.logger.error(f"Ошибка получения данных через API: {e}")
                    self.error_occurred.emit(f"Ошибка API: {e}")
                    return
            else:
                # Без API клиента данные не загружаются
                self.logger.info("API клиент не настроен, данные не загружаются")
                return
            
            total_time = time.time() - start_time
            self.logger.info(f"Загрузка рыночных данных завершена за {total_time:.2f} секунд")
            self.progress_updated.emit(100, "Завершено!")
            self.data_received.emit(market_data)
            
        except Exception as e:
            self.logger.error(f"Ошибка в MarketDataWorker: {e}")
            self.error_occurred.emit(str(e))
    
    def _get_test_data(self):
        """
        Возвращает пустые данные - данные отображаются только при наличии API ключей
        """
        return {
            "tickers": [],
            "orderbook": {},
            "recent_trades": {}
        }
    
    def _get_priority_symbols(self):
        """
        Получение списка символов с приоритетами обновления
        Высший приоритет - символы без данных, затем по возрасту данных
        """
        try:
            if not self.db_manager:
                return []
            
            # Получаем устаревшие символы (старше 30 минут)
            outdated_symbols = self.db_manager.get_outdated_tickers(max_age_minutes=30)
            
            # Получаем все кэшированные данные
            cached_data = self.db_manager.get_cached_ticker_data(max_age_minutes=1440)  # 24 часа
            cached_symbols = {ticker['symbol'] for ticker in cached_data}
            
            # Приоритет 1: Символы без данных вообще (будут определены при загрузке с API)
            # Приоритет 2: Устаревшие символы
            priority_info = {
                'outdated_symbols': outdated_symbols,
                'cached_symbols': cached_symbols
            }
            
            self.logger.info(f"Приоритеты обновления: {len(outdated_symbols)} устаревших символов")
            return priority_info
            
        except Exception as e:
            self.logger.error(f"Ошибка определения приоритетов: {e}")
            return []
    
    def stop(self):
        """
        Остановка воркера
        """
        self.running = False
        self.quit()
        self.wait()

class MarketsTab(QWidget):
    """
    Вкладка активов и рынков
    """
    
    def __init__(self, config_manager, db_manager):
        super().__init__()
        
        self.config = config_manager
        self.db_manager = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Автоматическая инициализация Bybit клиента для testnet
        self.bybit_client = self._init_bybit_client()
        self.logger.info(f"=== BYBIT CLIENT INITIALIZED: {self.bybit_client is not None} ===")
        
        # Данные рынков
        self.market_data: Optional[Dict[str, Any]] = None
        self.selected_symbol = "BTCUSDT"
        
        # Воркер для получения данных
        self.worker = None
        
        # Таймер для обновления данных
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._refresh_data)
        
        # Инициализация UI
        self._init_ui()
        
        # Автоматический запуск обновления данных если есть клиент
        self.logger.info(f"=== CHECKING CLIENT FOR AUTO REFRESH: {self.bybit_client is not None} ===")
        if self.bybit_client:
            self.logger.info("=== STARTING TIMER AND CALLING _refresh_data ===")
            self.update_timer.start(10000)  # Обновление каждые 10 секунд для оперативности
            self._refresh_data()  # Первоначальная загрузка данных
        else:
            self.logger.warning("=== BYBIT CLIENT IS NONE, NOT STARTING AUTO REFRESH ===")
        
        self.logger.info("Вкладка рынков инициализирована")
    
    def _init_bybit_client(self):
        """
        Инициализация Bybit клиента (принудительно testnet)
        """
        try:
            from src.api.bybit_client import BybitClient
            
            # Принудительно используем testnet
            testnet = True
            environment = 'testnet'
            api_credentials = self.config.get_api_credentials(environment)
            
            if api_credentials and api_credentials.get('api_key') and api_credentials.get('api_secret'):
                client = BybitClient(
                    api_key=api_credentials['api_key'],
                    api_secret=api_credentials['api_secret'],
                    testnet=testnet,
                    config_manager=self.config,
                    db_manager=self.db_manager
                )
                self.logger.info(f"Bybit клиент инициализирован (testnet: {testnet}, environment: {environment})")
                return client
            else:
                self.logger.warning("API ключи testnet не найдены")
                return None
                
        except Exception as e:
            self.logger.error(f"Ошибка инициализации Bybit клиента: {e}")
            return None
    
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Активы и рынки")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Проверка API ключей
        if not self.bybit_client:
            self._create_api_warning(layout)
            # Не создаем остальные UI элементы, поэтому не вызываем _connect_signals
            return
        
        # Панель фильтров
        self._create_filter_panel(layout)
        
        # Основной сплиттер
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # Левая панель - список активов
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self._create_assets_list(left_layout)
        main_splitter.addWidget(left_widget)
        
        # Правая панель - детальная информация
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self._create_market_details(right_layout)
        main_splitter.addWidget(right_widget)
        
        # Установка пропорций
        main_splitter.setSizes([400, 600])
        
        # Кнопки управления
        self._create_control_buttons(layout)
        
        # Подключение сигналов после полной инициализации UI
        self._connect_signals()
    
    def _connect_signals(self):
        """
        Подключение сигналов UI элементов
        """
        try:
            if hasattr(self, 'search_edit'):
                self.search_edit.textChanged.connect(self._filter_assets)
            
            if hasattr(self, 'category_combo'):
                self.category_combo.currentTextChanged.connect(self._filter_assets)
            
            if hasattr(self, 'risk_combo'):
                self.risk_combo.currentTextChanged.connect(self._filter_assets)
            
            if hasattr(self, 'favorites_checkbox'):
                self.favorites_checkbox.toggled.connect(self._filter_assets)
            
            # Подключение автообновления
            if hasattr(self, 'auto_update_checkbox'):
                self.auto_update_checkbox.toggled.connect(self._toggle_auto_update)
            
            # Подключение выбора актива
            if hasattr(self, 'assets_table'):
                self.assets_table.itemSelectionChanged.connect(self._on_asset_selected)
            
            # Подключение кнопки избранного
            if hasattr(self, 'favorite_button'):
                self.favorite_button.clicked.connect(self._toggle_favorite)
            
            # Подключение кнопки экспорта
            if hasattr(self, 'export_button'):
                self.export_button.clicked.connect(self._export_data)
                
        except Exception as e:
            self.logger.error(f"Ошибка подключения сигналов: {e}")
    
    def _connect_worker_signals(self):
        """
        Подключение сигналов воркера
        """
        try:
            if self.worker and hasattr(self, '_on_data_received'):
                self.worker.data_received.connect(self._on_data_received)
                self.worker.error_occurred.connect(self._on_error_occurred)
                self.worker.finished.connect(self._on_worker_finished)
                self.worker.progress_updated.connect(self._on_progress_updated)
                self.logger.info("Сигналы воркера успешно подключены")
            else:
                self.logger.warning(f"Не удалось подключить сигналы: worker={self.worker is not None}, has_method={hasattr(self, '_on_data_received')}")
        except Exception as e:
            self.logger.error(f"Ошибка подключения сигналов воркера: {e}")
    
    def _create_api_warning(self, layout):
        """
        Создание предупреждения о необходимости ввода API ключей
        """
        warning_frame = QFrame()
        warning_frame.setStyleSheet("""
            QFrame {
                background-color: #fff3cd;
                border: 2px solid #ffeaa7;
                border-radius: 8px;
                padding: 20px;
                margin: 10px;
            }
        """)
        warning_layout = QVBoxLayout(warning_frame)
        
        # Иконка и заголовок
        header_layout = QHBoxLayout()
        warning_icon = QLabel("⚠️")
        warning_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(warning_icon)
        
        warning_title = QLabel("API ключи не настроены")
        warning_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #856404;")
        header_layout.addWidget(warning_title)
        header_layout.addStretch()
        warning_layout.addLayout(header_layout)
        
        # Описание
        warning_text = QLabel(
            "Для отображения актуальных рыночных данных необходимо настроить API ключи Bybit.\n"
            "Пока API ключи не введены, отображаются сохраненные данные из базы данных."
        )
        warning_text.setStyleSheet("color: #856404; margin: 10px 0;")
        warning_text.setWordWrap(True)
        warning_layout.addWidget(warning_text)
        
        # Кнопка настройки
        setup_button = QPushButton("Настроить API ключи")
        setup_button.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #212529;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        setup_button.clicked.connect(self._open_api_settings)
        warning_layout.addWidget(setup_button)
        
        layout.addWidget(warning_frame)
        
        # Показать сохраненные данные из БД
        self._show_cached_data(layout)
    
    def _show_cached_data(self, layout):
        """
        Отображение сохраненных данных из базы данных
        """
        cached_group = QGroupBox("Сохраненные данные")
        cached_layout = QVBoxLayout(cached_group)
        
        info_label = QLabel("Отображаются последние сохраненные рыночные данные:")
        info_label.setStyleSheet("color: #6c757d; font-style: italic;")
        cached_layout.addWidget(info_label)
        
        # Простая таблица с кэшированными данными
        self.cached_table = QTableWidget()
        self.cached_table.setColumnCount(4)
        self.cached_table.setHorizontalHeaderLabels(["Символ", "Цена", "Изменение 24ч", "Объем"])
        self.cached_table.setMaximumHeight(200)
        
        # Загрузка данных из БД
        self._load_cached_market_data()
        
        cached_layout.addWidget(self.cached_table)
        layout.addWidget(cached_group)
    
    def _load_cached_market_data(self):
        """
        Загрузка кэшированных рыночных данных из БД
        """
        try:
            # Загрузка данных из БД
            if self.db_manager:
                cached_tickers = self.db_manager.get_cached_ticker_data(max_age_minutes=60)
                if cached_tickers:
                    self.logger.info(f"Загружено {len(cached_tickers)} кэшированных тикеров")
                    self._update_assets_table(cached_tickers)
                else:
                    self.logger.info("Кэшированные данные не найдены")
            else:
                self.logger.warning("DatabaseManager не инициализирован")
                    
        except Exception as e:
            self.logger.error(f"Ошибка загрузки кэшированных данных: {e}")
    
    def _open_api_settings(self):
        """
        Открытие настроек API ключей
        """
        QMessageBox.information(
            self, 
            "Настройка API", 
            "Перейдите в меню 'Настройки' -> 'API ключи' для настройки подключения к Bybit."
        )
    
    def _create_filter_panel(self, layout):
        """
        Создание панели фильтров
        """
        filter_group = QGroupBox("Фильтры")
        filter_layout = QHBoxLayout(filter_group)
        
        # Поиск по символу
        filter_layout.addWidget(QLabel("Поиск:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Введите символ...")
        filter_layout.addWidget(self.search_edit)
        
        # Категория
        filter_layout.addWidget(QLabel("Категория:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems(["Все", "Spot", "Futures", "Options"])
        filter_layout.addWidget(self.category_combo)
        
        # Уровень риска
        filter_layout.addWidget(QLabel("Риск:"))
        self.risk_combo = QComboBox()
        self.risk_combo.addItems(["Все", "Низкий", "Средний", "Высокий"])
        filter_layout.addWidget(self.risk_combo)
        
        # Только избранные
        self.favorites_checkbox = QCheckBox("Только избранные")
        filter_layout.addWidget(self.favorites_checkbox)
        
        filter_layout.addStretch()
        
        # Автообновление
        self.auto_update_checkbox = QCheckBox("Автообновление")
        self.auto_update_checkbox.setChecked(True)
        filter_layout.addWidget(self.auto_update_checkbox)
        
        layout.addWidget(filter_group)
    
    def _create_assets_list(self, layout):
        """
        Создание списка активов
        """
        group = QGroupBox("Список активов")
        group_layout = QVBoxLayout(group)
        
        # Таблица активов
        self.assets_table = QTableWidget()
        self.assets_table.setColumnCount(8)
        self.assets_table.setHorizontalHeaderLabels([
            "Символ", "Цена", "Изм. 24ч", "Объем 24ч", "Макс. 24ч", "Мин. 24ч", "Риск", "История"
        ])
        
        # Настройка таблицы
        header = self.assets_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, 7):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Колонка с кнопкой
        
        self.assets_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.assets_table.setAlternatingRowColors(True)
        self.assets_table.setSortingEnabled(True)
        
        group_layout.addWidget(self.assets_table)
        layout.addWidget(group)
    
    def _create_market_details(self, layout):
        """
        Создание детальной информации о рынке
        """
        # Информация о выбранном активе
        info_group = QGroupBox(f"Информация о {self.selected_symbol}")
        info_layout = QGridLayout(info_group)
        
        # Текущая цена
        self.current_price_label = QLabel("-")
        self.current_price_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        info_layout.addWidget(QLabel("Текущая цена:"), 0, 0)
        info_layout.addWidget(self.current_price_label, 0, 1)
        
        # Изменение за 24ч
        self.change_24h_label = QLabel("-")
        info_layout.addWidget(QLabel("Изм. 24ч:"), 1, 0)
        info_layout.addWidget(self.change_24h_label, 1, 1)
        
        # Объем за 24ч
        self.volume_24h_label = QLabel("-")
        info_layout.addWidget(QLabel("Объем 24ч:"), 2, 0)
        info_layout.addWidget(self.volume_24h_label, 2, 1)
        
        layout.addWidget(info_group)
        
        # Вкладки с детальной информацией
        details_tabs = QTabWidget()
        
        # Вкладка "Книга ордеров"
        orderbook_widget = QWidget()
        self._create_orderbook_tab(orderbook_widget)
        details_tabs.addTab(orderbook_widget, "Книга ордеров")
        
        # Вкладка "Последние сделки"
        trades_widget = QWidget()
        self._create_trades_tab(trades_widget)
        details_tabs.addTab(trades_widget, "Последние сделки")
        
        # Вкладка "График"
        chart_widget = QWidget()
        self._create_chart_tab(chart_widget)
        details_tabs.addTab(chart_widget, "График")
        
        layout.addWidget(details_tabs)
    
    def _create_orderbook_tab(self, widget):
        """
        Создание вкладки книги ордеров
        """
        layout = QVBoxLayout(widget)
        
        # Заголовок
        layout.addWidget(QLabel("Книга ордеров"))
        
        # Сплиттер для покупок и продаж
        splitter = QSplitter(Qt.Horizontal)
        
        # Таблица покупок (bids)
        bids_group = QGroupBox("Покупки")
        bids_layout = QVBoxLayout(bids_group)
        
        self.bids_table = QTableWidget()
        self.bids_table.setColumnCount(2)
        self.bids_table.setHorizontalHeaderLabels(["Цена", "Количество"])
        self.bids_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        bids_layout.addWidget(self.bids_table)
        splitter.addWidget(bids_group)
        
        # Таблица продаж (asks)
        asks_group = QGroupBox("Продажи")
        asks_layout = QVBoxLayout(asks_group)
        
        self.asks_table = QTableWidget()
        self.asks_table.setColumnCount(2)
        self.asks_table.setHorizontalHeaderLabels(["Цена", "Количество"])
        self.asks_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        asks_layout.addWidget(self.asks_table)
        splitter.addWidget(asks_group)
        
        layout.addWidget(splitter)
    
    def _create_trades_tab(self, widget):
        """
        Создание вкладки последних сделок
        """
        layout = QVBoxLayout(widget)
        
        # Заголовок
        layout.addWidget(QLabel("Последние сделок"))
        
        # Таблица сделок
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(4)
        self.trades_table.setHorizontalHeaderLabels(["Время", "Цена", "Количество", "Сторона"])
        
        header = self.trades_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        for i in range(1, 4):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        layout.addWidget(self.trades_table)
        
    def _create_chart_tab(self, widget):
        """
        Создание вкладки графика цен
        """
        layout = QVBoxLayout(widget)
        
        # Верхняя панель с настройками
        controls_layout = QHBoxLayout()
        
        # Выбор типа графика
        chart_type_label = QLabel("Тип графика:")
        controls_layout.addWidget(chart_type_label)
        
        self.chart_type_combo = QComboBox()
        self.chart_type_combo.addItems(["Свечи", "Линия"])
        self.chart_type_combo.currentIndexChanged.connect(self._update_chart)
        controls_layout.addWidget(self.chart_type_combo)
        
        # Выбор интервала
        interval_label = QLabel("Интервал:")
        controls_layout.addWidget(interval_label)
        
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1w"])
        self.interval_combo.setCurrentText("1h")
        self.interval_combo.currentIndexChanged.connect(self._update_chart)
        controls_layout.addWidget(self.interval_combo)
        
        # Выбор количества свечей
        limit_label = QLabel("Количество свечей:")
        controls_layout.addWidget(limit_label)
        
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["50", "100", "200", "500"])
        self.limit_combo.setCurrentText("100")
        self.limit_combo.currentIndexChanged.connect(self._update_chart)
        controls_layout.addWidget(self.limit_combo)
        
        # Кнопка обновления
        self.update_chart_button = QPushButton("Обновить")
        self.update_chart_button.clicked.connect(self._update_chart)
        controls_layout.addWidget(self.update_chart_button)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # График
        self.chart_view = QChartView()
        self.chart_view.setRenderHint(QPainter.Antialiasing)
        self.chart_view.setMinimumHeight(400)
        layout.addWidget(self.chart_view)
        
        # Создаем пустой график
        self._create_empty_chart()
    
    def _create_control_buttons(self, layout):
        """
        Создание кнопок управления
        """
        button_layout = QHBoxLayout()
        
        # Кнопка обновления
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self._refresh_data)
        button_layout.addWidget(self.refresh_button)
        
        # Прогресс-бар загрузки
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        button_layout.addWidget(self.progress_bar)
        
        # Кнопка добавления в избранное
        self.favorite_button = QPushButton("В избранное")
        button_layout.addWidget(self.favorite_button)
        
        button_layout.addStretch()
        
        # Кнопка экспорта
        self.export_button = QPushButton("Экспорт данных")
        button_layout.addWidget(self.export_button)
        
        layout.addLayout(button_layout)
    
    def _on_data_received(self, data: Dict[str, Any]):
        """
        Обработка полученных рыночных данных
        """
        self.logger.info("=== ВЫЗВАН МЕТОД _on_data_received ===")
        try:
            self.market_data = data
            tickers = data.get('tickers', [])
            
            self.logger.info(f"Получено {len(tickers)} тикеров для обработки")
            
            # Сохранение данных в БД
            if tickers and self.db_manager:
                try:
                    # Проверим формат первого тикера для отладки
                    if tickers:
                        first_ticker = tickers[0]
                        self.logger.info(f"Пример тикера: {first_ticker}")
                    
                    self.db_manager.save_ticker_data(tickers)
                    self.logger.info(f"Данные успешно сохранены в БД")
                except Exception as db_error:
                    self.logger.error(f"Ошибка сохранения в БД: {db_error}")
            
            self._update_assets_table(tickers)
            self._update_market_details()
            
        except Exception as e:
            self.logger.error(f"Ошибка обработки рыночных данных: {e}")
            self._on_error_occurred(str(e))
    
    def _on_error_occurred(self, error_message: str):
        """
        Обработка ошибок
        """
        QMessageBox.warning(self, "Ошибка", f"Не удалось получить рыночные данные:\n{error_message}")
    
    def _on_worker_finished(self):
        """
        Завершение работы воркера
        """
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Обновить")
        
        # Скрыть прогресс-бар
        self.progress_bar.setVisible(False)
    
    def _on_progress_updated(self, progress, message):
        """
        Обработка обновления прогресса загрузки данных
        """
        try:
            if progress > 0:
                self.progress_bar.setRange(0, 100)
                self.progress_bar.setValue(progress)
            else:
                self.progress_bar.setRange(0, 0)  # Неопределенный прогресс
            
            # Обновляем текст кнопки с информацией о прогрессе
            self.refresh_button.setText(f"Обновление... {message}")
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления прогресса: {e}")

    def _refresh_data(self):
        """
        Обновление рыночных данных
        """
        self.logger.info("=== ВЫЗВАН МЕТОД _refresh_data ===")
        try:
            # Проверка наличия API ключей
            if not self.bybit_client:
                self.logger.info("API ключи не настроены, данные не обновляются")
                return
                
            if not self.auto_update_checkbox.isChecked():
                return
            
            self.refresh_button.setEnabled(False)
            self.refresh_button.setText("Обновление...")
            
            # Показать прогресс-бар
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Неопределенный прогресс
            
            # Остановка предыдущего воркера
            if self.worker and self.worker.isRunning():
                self.worker.stop()
            
            # Создание нового воркера
            self.worker = MarketDataWorker(self.config, self.bybit_client, self.db_manager)
            
            # Подключение сигналов воркера (после создания воркера)
            if self.worker:
                try:
                    self.worker.data_received.connect(self._on_data_received)
                    self.worker.error_occurred.connect(self._on_error_occurred)
                    self.worker.finished.connect(self._on_worker_finished)
                    self.worker.progress_updated.connect(self._on_progress_updated)
                    self.logger.info("Сигналы воркера успешно подключены")
                except Exception as connect_error:
                    self.logger.error(f"Ошибка подключения сигналов: {connect_error}")
                    # Проверим, какие методы существуют
                    self.logger.info(f"Методы класса: {[method for method in dir(self) if method.startswith('_on_')]}")
            
            # Запуск воркера
            self.worker.start()
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления рыночных данных: {e}")
    
    def _update_assets_table(self, tickers: List[Dict[str, Any]]):
        """
        Обновление таблицы активов
        """
        try:
            self.assets_table.setRowCount(len(tickers))
            
            for row, ticker in enumerate(tickers):
                # Символ
                self.assets_table.setItem(row, 0, QTableWidgetItem(ticker['symbol']))
                
                # Цена
                price_item = QTableWidgetItem(f"${ticker['price']:,.2f}")
                self.assets_table.setItem(row, 1, price_item)
                
                # Изменение за 24ч
                change = ticker['change_24h']
                change_item = QTableWidgetItem(f"{change:+.2f}%")
                change_color = "green" if change >= 0 else "red"
                change_item.setForeground(Qt.GlobalColor.__dict__[change_color])
                self.assets_table.setItem(row, 2, change_item)
                
                # Объем за 24ч
                volume = ticker['volume_24h']
                volume_item = QTableWidgetItem(f"${volume:,.0f}")
                self.assets_table.setItem(row, 3, volume_item)
                
                # Максимум за 24ч
                high_item = QTableWidgetItem(f"${ticker['high_24h']:,.2f}")
                self.assets_table.setItem(row, 4, high_item)
                
                # Минимум за 24ч
                low_item = QTableWidgetItem(f"${ticker['low_24h']:,.2f}")
                self.assets_table.setItem(row, 5, low_item)
                
                # Уровень риска
                risk_level = ticker['risk_level']
                risk_item = QTableWidgetItem(risk_level.capitalize())
                risk_colors = {"low": Qt.green, "medium": QColor(255, 165, 0), "high": Qt.red}
                if risk_level in risk_colors:
                    risk_item.setForeground(risk_colors[risk_level])
                self.assets_table.setItem(row, 6, risk_item)
                
                # Кнопка истории
                history_button = QPushButton("📊 История")
                history_button.setMaximumWidth(100)
                history_button.clicked.connect(lambda checked, symbol=ticker['symbol']: self._show_historical_data(symbol))
                self.assets_table.setCellWidget(row, 7, history_button)
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления последних сделок: {e}")
    
    def _update_market_details(self):
        """
        Обновление детальной информации о выбранном активе
        """
        try:
            if not self.market_data:
                return
            
            # Поиск данных по выбранному символу
            ticker_data = None
            for ticker in self.market_data.get('tickers', []):
                if ticker['symbol'] == self.selected_symbol:
                    ticker_data = ticker
                    break
            
            if not ticker_data:
                return
            
            # Обновление основной информации
            self.current_price_label.setText(f"${ticker_data['price']:,.2f}")
            
            change = ticker_data['change_24h']
            change_color = "green" if change >= 0 else "red"
            self.change_24h_label.setText(f"{change:+.2f}%")
            self.change_24h_label.setStyleSheet(f"color: {change_color}; font-weight: bold;")
            
            volume = ticker_data['volume_24h']
            self.volume_24h_label.setText(f"${volume:,.0f}")
            
            # Обновление книги ордеров
            self._update_orderbook()
            
            # Обновление последних сделок
            self._update_recent_trades()
            
            # Обновление графика
            self._update_chart()
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления детальной информации: {e}")
    
    def _update_orderbook(self):
        """
        Обновление книги ордеров
        """
        try:
            if not self.market_data:
                return
            
            orderbook = self.market_data.get('orderbook', {}).get(self.selected_symbol, {})
            
            # Обновление покупок (bids)
            bids = orderbook.get('bids', [])
            self.bids_table.setRowCount(len(bids))
            for row, (price, quantity) in enumerate(bids):
                self.bids_table.setItem(row, 0, QTableWidgetItem(f"${price:,.2f}"))
                self.bids_table.setItem(row, 1, QTableWidgetItem(f"{quantity:.4f}"))
            
            # Обновление продаж (asks)
            asks = orderbook.get('asks', [])
            self.asks_table.setRowCount(len(asks))
            for row, (price, quantity) in enumerate(asks):
                price_item = QTableWidgetItem(f"${price:,.2f}")
                price_item.setForeground(Qt.red)
                self.asks_table.setItem(row, 0, price_item)
                self.asks_table.setItem(row, 1, QTableWidgetItem(f"{quantity:.4f}"))
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления книги ордеров: {e}")
    
    def _update_recent_trades(self):
        """
        Обновление последних сделок
        """
        try:
            if not self.market_data:
                return
            
            trades = self.market_data.get('recent_trades', {}).get(self.selected_symbol, [])
            
            self.trades_table.setRowCount(len(trades))
            for row, trade in enumerate(trades):
                # Время
                self.trades_table.setItem(row, 0, QTableWidgetItem(trade['time']))
                
                # Цена
                price_item = QTableWidgetItem(f"${trade['price']:,.2f}")
                self.trades_table.setItem(row, 1, price_item)
                
                # Количество
                self.trades_table.setItem(row, 2, QTableWidgetItem(f"{trade['quantity']:.4f}"))
                
                # Сторона
                side = trade['side']
                side_item = QTableWidgetItem(side.upper())
                side_color = Qt.green if side == "buy" else Qt.red
                side_item.setForeground(side_color)
                self.trades_table.setItem(row, 3, side_item)
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления последних сделок: {e}")


class HistoricalDataDialog(QDialog):
    """
    Диалог для отображения исторических данных актива
    """
    
    def __init__(self, symbol: str, api_client, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.api_client = api_client
        self.logger = logging.getLogger(__name__)
        
        self.setWindowTitle(f"Исторические данные - {symbol}")
        self.setModal(True)
        self.resize(800, 600)
        
        self._init_ui()
        self._load_historical_data()
    
    def _init_ui(self):
        """
        Инициализация интерфейса
        """
        layout = QVBoxLayout(self)
        
        # Заголовок
        title_label = QLabel(f"Исторические данные для {self.symbol}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Параметры запроса
        params_group = QGroupBox("Параметры")
        params_layout = QHBoxLayout(params_group)
        
        params_layout.addWidget(QLabel("Интервал:"))
        self.interval_combo = QComboBox()
        self.interval_combo.addItems(["1", "5", "15", "30", "60", "240", "D"])
        self.interval_combo.setCurrentText("60")
        params_layout.addWidget(self.interval_combo)
        
        params_layout.addWidget(QLabel("Дата с:"))
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        params_layout.addWidget(self.start_date)
        
        params_layout.addWidget(QLabel("Дата по:"))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        params_layout.addWidget(self.end_date)
        
        self.load_button = QPushButton("Загрузить")
        self.load_button.clicked.connect(self._load_historical_data)
        params_layout.addWidget(self.load_button)
        
        layout.addWidget(params_group)
        
        # Таблица данных
        self.data_table = QTableWidget()
        self.data_table.setColumnCount(6)
        self.data_table.setHorizontalHeaderLabels([
            "Время", "Открытие", "Максимум", "Минимум", "Закрытие", "Объем"
        ])
        
        # Настройка таблицы
        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Stretch)
        
        layout.addWidget(self.data_table)
        
        # Текстовое поле для отображения сырых данных
        self.raw_data_text = QTextEdit()
        self.raw_data_text.setMaximumHeight(150)
        self.raw_data_text.setPlaceholderText("Сырые данные API будут отображены здесь...")
        layout.addWidget(QLabel("Сырые данные API:"))
        layout.addWidget(self.raw_data_text)
        
        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _load_historical_data(self):
        """
        Загрузка исторических данных
        """
        try:
            self.load_button.setEnabled(False)
            self.load_button.setText("Загрузка...")
            
            # Получение параметров
            interval = self.interval_combo.currentText()
            start_date = self.start_date.date().toPython()
            end_date = self.end_date.date().toPython()
            
            # Конвертация дат в timestamp (миллисекунды)
            import time
            from datetime import datetime, timezone
            
            start_timestamp = int(datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp() * 1000)
            end_timestamp = int(datetime.combine(end_date, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp() * 1000)
            
            # Синхронный запрос данных
            try:
                response = self.bybit_client.get_klines(
                    symbol=self.symbol,
                    interval=interval,
                    limit=200,
                    start_time=start_timestamp,
                    end_time=end_timestamp
                )
            except Exception as e:
                self.logger.error(f"Ошибка получения данных: {e}")
                response = None
            
            if response and response.get('retCode') == 0:
                self._display_data(response)
            else:
                error_msg = response.get('retMsg', 'Неизвестная ошибка') if response else 'Нет ответа от API'
                QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить данные: {error_msg}")
                
        except Exception as e:
            self.logger.error(f"Ошибка загрузки исторических данных: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки данных: {str(e)}")
        finally:
            self.load_button.setEnabled(True)
            self.load_button.setText("Загрузить")
    
    def _display_data(self, response: dict):
        """
        Отображение данных в таблице
        """
        try:
            # Отображение сырых данных
            import json
            self.raw_data_text.setPlainText(json.dumps(response, indent=2, ensure_ascii=False))
            
            # Извлечение данных свечей
            klines_data = response.get('result', {}).get('list', [])
            
            if not klines_data:
                QMessageBox.information(self, "Информация", "Нет данных для отображения")
                return
            
            # Заполнение таблицы
            self.data_table.setRowCount(len(klines_data))
            
            for row, kline in enumerate(klines_data):
                if isinstance(kline, list) and len(kline) >= 6:
                    # Время (timestamp в миллисекундах)
                    timestamp = int(kline[0])
                    dt = datetime.fromtimestamp(timestamp / 1000)
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    self.data_table.setItem(row, 0, QTableWidgetItem(time_str))
                    
                    # OHLCV данные
                    self.data_table.setItem(row, 1, QTableWidgetItem(f"{float(kline[1]):.4f}"))  # Open
                    self.data_table.setItem(row, 2, QTableWidgetItem(f"{float(kline[2]):.4f}"))  # High
                    self.data_table.setItem(row, 3, QTableWidgetItem(f"{float(kline[3]):.4f}"))  # Low
                    self.data_table.setItem(row, 4, QTableWidgetItem(f"{float(kline[4]):.4f}"))  # Close
                    self.data_table.setItem(row, 5, QTableWidgetItem(f"{float(kline[5]):.2f}"))   # Volume
            
            self.logger.info(f"Загружено {len(klines_data)} свечей для {self.symbol}")
            
        except Exception as e:
            self.logger.error(f"Ошибка отображения данных: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка отображения данных: {str(e)}")
            self._on_error_occurred(str(e))
    
    def _show_historical_data(self, symbol: str):
        """
        Показ исторических данных для актива
        """
        try:
            if not self.bybit_client:
                QMessageBox.warning(self, "Предупреждение", "API клиент недоступен")
                return
            
            # Создаем диалог для отображения исторических данных
            dialog = HistoricalDataDialog(symbol, self.bybit_client, self)
            dialog.exec()
            
        except Exception as e:
            self.logger.error(f"Ошибка показа исторических данных для {symbol}: {e}")
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить исторические данные: {str(e)}")
    
    def _on_asset_selected(self):
        """
        Обработчик выбора актива
        """
        try:
            current_row = self.assets_table.currentRow()
            if current_row >= 0:
                symbol_item = self.assets_table.item(current_row, 0)
                if symbol_item:
                    self.selected_symbol = symbol_item.text()
                    self._update_market_details()
                    
                    # Обновление заголовка группы
                    for widget in self.findChildren(QGroupBox):
                        if "Информация о" in widget.title():
                            widget.setTitle(f"Информация о {self.selected_symbol}")
                            break
            
        except Exception as e:
            self.logger.error(f"Ошибка выбора актива: {e}")
    
    def _filter_assets(self):
        """
        Фильтрация списка активов
        """
        try:
            if not hasattr(self, 'assets_table') or not self.assets_table:
                return
                
            search_text = self.search_edit.text().lower() if hasattr(self, 'search_edit') else ""
            category = self.category_combo.currentText() if hasattr(self, 'category_combo') else "Все"
            risk_level = self.risk_combo.currentText() if hasattr(self, 'risk_combo') else "Все"
            favorites_only = self.favorites_checkbox.isChecked() if hasattr(self, 'favorites_checkbox') else False
            
            # Фильтрация строк таблицы
            for row in range(self.assets_table.rowCount()):
                show_row = True
                
                # Фильтр по поиску
                if search_text:
                    symbol_item = self.assets_table.item(row, 0)
                    if symbol_item and search_text not in symbol_item.text().lower():
                        show_row = False
                
                # Скрыть/показать строку
                self.assets_table.setRowHidden(row, not show_row)
            
        except Exception as e:
            self.logger.error(f"Ошибка фильтрации активов: {e}")
    
    def _toggle_auto_update(self, enabled: bool):
        """
        Переключение автообновления
        """
        try:
            if enabled:
                self.update_timer.start(5000)
            else:
                self.update_timer.stop()
            
        except Exception as e:
            self.logger.error(f"Ошибка переключения автообновления: {e}")
    
    def _toggle_favorite(self):
        """
        Добавление/удаление из избранного
        """
        try:
            # Здесь будет реализация избранного
            QMessageBox.information(self, "Избранное", f"Актив {self.selected_symbol} добавлен в избранное")
            
        except Exception as e:
            self.logger.error(f"Ошибка работы с избранным: {e}")
    
    def _export_data(self):
        """
        Экспорт рыночных данных
        """
        try:
            if not self.market_data:
                QMessageBox.information(self, "Экспорт", "Нет данных для экспорта")
                return
            
            # Здесь будет реализация экспорта
            QMessageBox.information(self, "Экспорт", "Функция экспорта будет реализована")
            
        except Exception as e:
            self.logger.error(f"Ошибка экспорта данных: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка экспорта: {e}")
    
    def closeEvent(self, event):
        """
        Обработчик закрытия вкладки
        """
        try:
            # Остановка таймера
            self.update_timer.stop()
            
            # Остановка воркера
            if self.worker and self.worker.isRunning():
                self.worker.stop()
            
            event.accept()
            
        except Exception as e:
            self.logger.error(f"Ошибка закрытия вкладки рынков: {e}")
            event.accept()