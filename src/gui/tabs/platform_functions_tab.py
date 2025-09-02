#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вкладка "Дополнительные функции платформы"

Дополнительные инструменты и функции:
- Анализ рынка и технические индикаторы
- Калькулятор позиций и рисков
- Бэктестинг стратегий
- Алерты и уведомления
- Экспорт данных и отчетов
"""

import logging
from typing import Dict, List, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QLineEdit, QComboBox, QSplitter, QTabWidget,
    QHeaderView, QAbstractItemView, QMessageBox, QProgressBar,
    QCheckBox, QSpinBox, QDoubleSpinBox, QTextEdit, QDialog,
    QDialogButtonBox, QFormLayout, QSlider, QDateEdit, QTimeEdit
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QDate, QTime
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis

class BacktestDialog(QDialog):
    """
    Диалог настройки бэктестинга
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Настройка бэктестинга")
        self.setMinimumSize(500, 400)
        
        self._init_ui()
    
    def _init_ui(self):
        """
        Инициализация интерфейса диалога
        """
        layout = QVBoxLayout(self)
        
        # Форма настроек
        form_layout = QFormLayout()
        
        # Стратегия
        self.strategy_combo = QComboBox()
        self.strategy_combo.addItems([
            "Скользящие средние (MA)",
            "RSI + MACD",
            "Bollinger Bands",
            "Momentum Trading",
            "Grid Trading"
        ])
        form_layout.addRow("Стратегия:", self.strategy_combo)
        
        # Актив
        self.asset_combo = QComboBox()
        self.asset_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT"])
        form_layout.addRow("Актив:", self.asset_combo)
        
        # Период тестирования
        period_layout = QHBoxLayout()
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate().addDays(-365))
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        period_layout.addWidget(QLabel("с"))
        period_layout.addWidget(self.start_date)
        period_layout.addWidget(QLabel("по"))
        period_layout.addWidget(self.end_date)
        form_layout.addRow("Период:", period_layout)
        
        # Начальный капитал
        self.initial_capital_spin = QDoubleSpinBox()
        self.initial_capital_spin.setRange(100, 1000000)
        self.initial_capital_spin.setValue(10000)
        self.initial_capital_spin.setSuffix(" USDT")
        form_layout.addRow("Начальный капитал:", self.initial_capital_spin)
        
        # Комиссия
        self.commission_spin = QDoubleSpinBox()
        self.commission_spin.setRange(0.0, 1.0)
        self.commission_spin.setValue(0.1)
        self.commission_spin.setSuffix("%")
        self.commission_spin.setDecimals(3)
        form_layout.addRow("Комиссия:", self.commission_spin)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_config(self) -> Dict[str, Any]:
        """
        Получение конфигурации бэктестинга
        """
        return {
            "strategy": self.strategy_combo.currentText(),
            "asset": self.asset_combo.currentText(),
            "start_date": self.start_date.date().toString("yyyy-MM-dd"),
            "end_date": self.end_date.date().toString("yyyy-MM-dd"),
            "initial_capital": self.initial_capital_spin.value(),
            "commission": self.commission_spin.value()
        }

class AlertDialog(QDialog):
    """
    Диалог создания алерта
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Создание алерта")
        self.setMinimumSize(400, 300)
        
        self._init_ui()
    
    def _init_ui(self):
        """
        Инициализация интерфейса диалога
        """
        layout = QVBoxLayout(self)
        
        # Форма настроек
        form_layout = QFormLayout()
        
        # Актив
        self.asset_combo = QComboBox()
        self.asset_combo.addItems(["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT"])
        form_layout.addRow("Актив:", self.asset_combo)
        
        # Тип алерта
        self.alert_type_combo = QComboBox()
        self.alert_type_combo.addItems([
            "Цена выше",
            "Цена ниже",
            "Изменение цены %",
            "Объем торгов",
            "RSI уровень",
            "MACD сигнал"
        ])
        form_layout.addRow("Тип алерта:", self.alert_type_combo)
        
        # Значение
        self.value_spin = QDoubleSpinBox()
        self.value_spin.setRange(0.0, 1000000.0)
        self.value_spin.setValue(50000.0)
        form_layout.addRow("Значение:", self.value_spin)
        
        # Сообщение
        self.message_edit = QLineEdit()
        self.message_edit.setPlaceholderText("Текст уведомления...")
        form_layout.addRow("Сообщение:", self.message_edit)
        
        # Способ уведомления
        notification_layout = QVBoxLayout()
        self.telegram_check = QCheckBox("Telegram")
        self.telegram_check.setChecked(True)
        self.sound_check = QCheckBox("Звуковое уведомление")
        self.popup_check = QCheckBox("Всплывающее окно")
        notification_layout.addWidget(self.telegram_check)
        notification_layout.addWidget(self.sound_check)
        notification_layout.addWidget(self.popup_check)
        form_layout.addRow("Уведомления:", notification_layout)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_config(self) -> Dict[str, Any]:
        """
        Получение конфигурации алерта
        """
        return {
            "asset": self.asset_combo.currentText(),
            "type": self.alert_type_combo.currentText(),
            "value": self.value_spin.value(),
            "message": self.message_edit.text(),
            "telegram": self.telegram_check.isChecked(),
            "sound": self.sound_check.isChecked(),
            "popup": self.popup_check.isChecked()
        }

class PlatformFunctionsTab(QWidget):
    """
    Вкладка дополнительных функций платформы
    """
    
    def __init__(self, config_manager, db_manager):
        super().__init__()
        
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Активные алерты
        self.active_alerts: List[Dict[str, Any]] = []
        
        self._init_ui()
        
        # Таймер для обновления данных
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_data)
        self.update_timer.start(5000)  # Обновление каждые 5 секунд
        
        self.logger.info("Вкладка дополнительных функций инициализирована")
    
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Дополнительные функции платформы")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Создаем вкладки для разных функций
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Вкладка анализа рынка
        self._create_market_analysis_tab()
        
        # Вкладка калькулятора
        self._create_calculator_tab()
        
        # Вкладка бэктестинга
        self._create_backtest_tab()
        
        # Вкладка алертов
        self._create_alerts_tab()
        
        # Вкладка экспорта
        self._create_export_tab()
    
    def _create_market_analysis_tab(self):
        """
        Создание вкладки анализа рынка
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Выбор актива для анализа
        asset_layout = QHBoxLayout()
        asset_layout.addWidget(QLabel("Актив:"))
        
        self.analysis_asset_combo = QComboBox()
        self.analysis_asset_combo.addItems([
            "BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT",
            "BNBUSDT", "XRPUSDT", "MATICUSDT", "AVAXUSDT", "DOTUSDT",
            "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "FTMUSDT",
            "NEARUSDT", "APTUSDT", "OPUSDT", "ARBUSDT", "INJUSDT",
            "SUIUSDT", "TIARUSDT", "SEIUSDT", "WLDUSDT", "PEPEUSDT",
            "ORDIUSDT", "BONKUSDT", "FLOKIUSDT", "WIFUSDT", "JUPUSDT"
        ])
        asset_layout.addWidget(self.analysis_asset_combo)
        
        self.analyze_button = QPushButton("Анализировать")
        self.analyze_button.clicked.connect(self._analyze_market)
        asset_layout.addWidget(self.analyze_button)
        
        asset_layout.addStretch()
        layout.addLayout(asset_layout)
        
        # Результаты анализа
        analysis_group = QGroupBox("Результаты анализа")
        analysis_layout = QGridLayout(analysis_group)
        
        # Технические индикаторы
        indicators_group = QGroupBox("Технические индикаторы")
        indicators_layout = QGridLayout(indicators_group)
        
        # RSI
        indicators_layout.addWidget(QLabel("RSI (14):"), 0, 0)
        self.rsi_label = QLabel("--")
        indicators_layout.addWidget(self.rsi_label, 0, 1)
        
        # MACD
        indicators_layout.addWidget(QLabel("MACD:"), 1, 0)
        self.macd_label = QLabel("--")
        indicators_layout.addWidget(self.macd_label, 1, 1)
        
        # Bollinger Bands
        indicators_layout.addWidget(QLabel("Bollinger %B:"), 2, 0)
        self.bb_label = QLabel("--")
        indicators_layout.addWidget(self.bb_label, 2, 1)
        
        # Moving Averages
        indicators_layout.addWidget(QLabel("MA(20):"), 0, 2)
        self.ma20_label = QLabel("--")
        indicators_layout.addWidget(self.ma20_label, 0, 3)
        
        indicators_layout.addWidget(QLabel("MA(50):"), 1, 2)
        self.ma50_label = QLabel("--")
        indicators_layout.addWidget(self.ma50_label, 1, 3)
        
        # Volume
        indicators_layout.addWidget(QLabel("Объем (24ч):"), 2, 2)
        self.volume_label = QLabel("--")
        indicators_layout.addWidget(self.volume_label, 2, 3)
        
        analysis_layout.addWidget(indicators_group, 0, 0)
        
        # Сигналы
        signals_group = QGroupBox("Торговые сигналы")
        signals_layout = QVBoxLayout(signals_group)
        
        self.signals_text = QTextEdit()
        self.signals_text.setReadOnly(True)
        self.signals_text.setMaximumHeight(150)
        signals_layout.addWidget(self.signals_text)
        
        analysis_layout.addWidget(signals_group, 0, 1)
        
        layout.addWidget(analysis_group)
        
        self.tab_widget.addTab(tab, "Анализ рынка")
    
    def _create_calculator_tab(self):
        """
        Создание вкладки калькулятора позиций
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Калькулятор позиций
        calc_group = QGroupBox("Калькулятор позиций и рисков")
        calc_layout = QFormLayout(calc_group)
        
        # Размер счета
        self.account_size_spin = QDoubleSpinBox()
        self.account_size_spin.setRange(100, 1000000)
        self.account_size_spin.setValue(0)
        self.account_size_spin.setSuffix(" USDT")
        self.account_size_spin.valueChanged.connect(self._calculate_position)
        calc_layout.addRow("Размер счета:", self.account_size_spin)
        
        # Риск на сделку
        self.risk_percent_spin = QDoubleSpinBox()
        self.risk_percent_spin.setRange(0.1, 20.0)
        self.risk_percent_spin.setValue(1.0)
        self.risk_percent_spin.setSuffix("%")
        self.risk_percent_spin.valueChanged.connect(self._calculate_position)
        calc_layout.addRow("Риск на сделку:", self.risk_percent_spin)
        
        # Цена входа
        self.entry_price_spin = QDoubleSpinBox()
        self.entry_price_spin.setRange(0.001, 1000000)
        self.entry_price_spin.setValue(0)
        self.entry_price_spin.valueChanged.connect(self._calculate_position)
        calc_layout.addRow("Цена входа:", self.entry_price_spin)
        
        # Стоп-лосс
        self.stop_loss_spin = QDoubleSpinBox()
        self.stop_loss_spin.setRange(0.001, 1000000)
        self.stop_loss_spin.setValue(0)
        self.stop_loss_spin.valueChanged.connect(self._calculate_position)
        calc_layout.addRow("Стоп-лосс:", self.stop_loss_spin)
        
        # Тейк-профит
        self.take_profit_spin = QDoubleSpinBox()
        self.take_profit_spin.setRange(0.001, 1000000)
        self.take_profit_spin.setValue(0)
        self.take_profit_spin.valueChanged.connect(self._calculate_position)
        calc_layout.addRow("Тейк-профит:", self.take_profit_spin)
        
        layout.addWidget(calc_group)
        
        # Результаты расчета
        results_group = QGroupBox("Результаты расчета")
        results_layout = QFormLayout(results_group)
        
        self.position_size_label = QLabel("--")
        results_layout.addRow("Размер позиции:", self.position_size_label)
        
        self.risk_amount_label = QLabel("--")
        results_layout.addRow("Сумма риска:", self.risk_amount_label)
        
        self.potential_profit_label = QLabel("--")
        results_layout.addRow("Потенциальная прибыль:", self.potential_profit_label)
        
        self.risk_reward_label = QLabel("--")
        results_layout.addRow("Соотношение риск/прибыль:", self.risk_reward_label)
        
        layout.addWidget(results_group)
        
        # Кнопка расчета
        calc_button = QPushButton("Пересчитать")
        calc_button.clicked.connect(self._calculate_position)
        layout.addWidget(calc_button)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Калькулятор")
    
    def _create_backtest_tab(self):
        """
        Создание вкладки бэктестинга
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Управление бэктестингом
        control_layout = QHBoxLayout()
        
        self.new_backtest_button = QPushButton("Новый бэктест")
        self.new_backtest_button.clicked.connect(self._new_backtest)
        control_layout.addWidget(self.new_backtest_button)
        
        control_layout.addStretch()
        
        self.export_backtest_button = QPushButton("Экспорт результатов")
        self.export_backtest_button.clicked.connect(self._export_backtest)
        control_layout.addWidget(self.export_backtest_button)
        
        layout.addLayout(control_layout)
        
        # Таблица результатов бэктестинга
        self.backtest_table = QTableWidget()
        self.backtest_table.setColumnCount(8)
        self.backtest_table.setHorizontalHeaderLabels([
            "Дата", "Стратегия", "Актив", "Период", "Доходность", "Макс. просадка", "Sharpe", "Сделок"
        ])
        
        # Настройка таблицы
        header = self.backtest_table.horizontalHeader()
        for i in range(8):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        self.backtest_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.backtest_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.backtest_table)
        
        # Детали выбранного бэктеста
        details_group = QGroupBox("Детали бэктеста")
        details_layout = QVBoxLayout(details_group)
        
        self.backtest_details = QTextEdit()
        self.backtest_details.setReadOnly(True)
        self.backtest_details.setMaximumHeight(150)
        details_layout.addWidget(self.backtest_details)
        
        layout.addWidget(details_group)
        
        self.tab_widget.addTab(tab, "Бэктестинг")
    
    def _create_alerts_tab(self):
        """
        Создание вкладки алертов
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Управление алертами
        control_layout = QHBoxLayout()
        
        self.new_alert_button = QPushButton("Создать алерт")
        self.new_alert_button.clicked.connect(self._create_alert)
        control_layout.addWidget(self.new_alert_button)
        
        control_layout.addStretch()
        
        self.delete_alert_button = QPushButton("Удалить")
        self.delete_alert_button.clicked.connect(self._delete_alert)
        control_layout.addWidget(self.delete_alert_button)
        
        layout.addLayout(control_layout)
        
        # Таблица алертов
        self.alerts_table = QTableWidget()
        self.alerts_table.setColumnCount(6)
        self.alerts_table.setHorizontalHeaderLabels([
            "Актив", "Тип", "Значение", "Статус", "Создан", "Сообщение"
        ])
        
        # Настройка таблицы
        header = self.alerts_table.horizontalHeader()
        for i in range(6):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        self.alerts_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.alerts_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.alerts_table)
        
        # История срабатываний
        history_group = QGroupBox("История срабатываний")
        history_layout = QVBoxLayout(history_group)
        
        self.alert_history = QTextEdit()
        self.alert_history.setReadOnly(True)
        self.alert_history.setMaximumHeight(150)
        history_layout.addWidget(self.alert_history)
        
        layout.addWidget(history_group)
        
        self.tab_widget.addTab(tab, "Алерты")
    
    def _create_export_tab(self):
        """
        Создание вкладки экспорта данных
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Экспорт торговых данных
        trade_group = QGroupBox("Экспорт торговых данных")
        trade_layout = QVBoxLayout(trade_group)
        
        # Период экспорта
        period_layout = QHBoxLayout()
        period_layout.addWidget(QLabel("Период:"))
        
        self.export_start_date = QDateEdit()
        self.export_start_date.setDate(QDate.currentDate().addDays(-30))
        period_layout.addWidget(self.export_start_date)
        
        period_layout.addWidget(QLabel("—"))
        
        self.export_end_date = QDateEdit()
        self.export_end_date.setDate(QDate.currentDate())
        period_layout.addWidget(self.export_end_date)
        
        period_layout.addStretch()
        trade_layout.addLayout(period_layout)
        
        # Типы данных для экспорта
        data_types_layout = QVBoxLayout()
        
        self.export_trades_check = QCheckBox("История сделок")
        self.export_trades_check.setChecked(True)
        data_types_layout.addWidget(self.export_trades_check)
        
        self.export_strategies_check = QCheckBox("Логи стратегий")
        data_types_layout.addWidget(self.export_strategies_check)
        
        self.export_market_data_check = QCheckBox("Рыночные данные")
        data_types_layout.addWidget(self.export_market_data_check)
        
        self.export_performance_check = QCheckBox("Показатели производительности")
        data_types_layout.addWidget(self.export_performance_check)
        
        trade_layout.addLayout(data_types_layout)
        
        # Кнопки экспорта
        export_buttons_layout = QHBoxLayout()
        
        self.export_csv_button = QPushButton("Экспорт в CSV")
        self.export_csv_button.clicked.connect(self._export_csv)
        export_buttons_layout.addWidget(self.export_csv_button)
        
        self.export_excel_button = QPushButton("Экспорт в Excel")
        self.export_excel_button.clicked.connect(self._export_excel)
        export_buttons_layout.addWidget(self.export_excel_button)
        
        self.export_pdf_button = QPushButton("Отчет в PDF")
        self.export_pdf_button.clicked.connect(self._export_pdf)
        export_buttons_layout.addWidget(self.export_pdf_button)
        
        trade_layout.addLayout(export_buttons_layout)
        
        layout.addWidget(trade_group)
        
        # Статус экспорта
        status_group = QGroupBox("Статус экспорта")
        status_layout = QVBoxLayout(status_group)
        
        self.export_progress = QProgressBar()
        status_layout.addWidget(self.export_progress)
        
        self.export_status_label = QLabel("Готов к экспорту")
        status_layout.addWidget(self.export_status_label)
        
        layout.addWidget(status_group)
        
        layout.addStretch()
        
        self.tab_widget.addTab(tab, "Экспорт данных")
    
    def _analyze_market(self):
        """
        Анализ рынка для выбранного актива
        """
        try:
            asset = self.analysis_asset_combo.currentText()
            
            # Симуляция анализа рынка
            import random
            
            # Обновляем индикаторы (симуляция)
            rsi = random.uniform(20, 80)
            self.rsi_label.setText(f"{rsi:.1f}")
            
            # Цвет RSI
            if rsi < 30:
                self.rsi_label.setStyleSheet("color: green; font-weight: bold;")
            elif rsi > 70:
                self.rsi_label.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.rsi_label.setStyleSheet("color: black;")
            
            macd = random.uniform(-0.5, 0.5)
            self.macd_label.setText(f"{macd:.3f}")
            
            bb_percent = random.uniform(0, 1)
            self.bb_label.setText(f"{bb_percent:.2f}")
            
            ma20 = random.uniform(45000, 55000)
            self.ma20_label.setText(f"${ma20:,.0f}")
            
            ma50 = random.uniform(40000, 50000)
            self.ma50_label.setText(f"${ma50:,.0f}")
            
            volume = random.uniform(1000000, 5000000)
            self.volume_label.setText(f"{volume:,.0f} BTC")
            
            # Генерируем торговые сигналы
            signals = []
            
            if rsi < 30:
                signals.append("🟢 RSI показывает перепроданность - возможность покупки")
            elif rsi > 70:
                signals.append("🔴 RSI показывает перекупленность - возможность продажи")
            
            if macd > 0:
                signals.append("🟢 MACD выше нуля - бычий сигнал")
            else:
                signals.append("🔴 MACD ниже нуля - медвежий сигнал")
            
            if ma20 > ma50:
                signals.append("🟢 MA20 выше MA50 - восходящий тренд")
            else:
                signals.append("🔴 MA20 ниже MA50 - нисходящий тренд")
            
            if not signals:
                signals.append("⚪ Нейтральные рыночные условия")
            
            self.signals_text.setText("\n".join(signals))
            
            self.logger.info(f"Анализ рынка выполнен для {asset}")
        
        except Exception as e:
            self.logger.error(f"Ошибка анализа рынка: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка анализа рынка: {e}")
    
    def _calculate_position(self):
        """
        Расчет размера позиции и рисков
        """
        try:
            account_size = self.account_size_spin.value()
            risk_percent = self.risk_percent_spin.value()
            entry_price = self.entry_price_spin.value()
            stop_loss = self.stop_loss_spin.value()
            take_profit = self.take_profit_spin.value()
            
            # Расчет суммы риска
            risk_amount = account_size * (risk_percent / 100)
            
            # Расчет размера позиции
            price_diff = abs(entry_price - stop_loss)
            if price_diff > 0:
                position_size = risk_amount / price_diff
            else:
                position_size = 0
            
            # Расчет потенциальной прибыли
            profit_diff = abs(take_profit - entry_price)
            potential_profit = position_size * profit_diff
            
            # Соотношение риск/прибыль
            if risk_amount > 0:
                risk_reward = potential_profit / risk_amount
            else:
                risk_reward = 0
            
            # Обновляем интерфейс
            self.position_size_label.setText(f"{position_size:.6f} BTC")
            self.risk_amount_label.setText(f"${risk_amount:.2f}")
            self.potential_profit_label.setText(f"${potential_profit:.2f}")
            self.risk_reward_label.setText(f"1:{risk_reward:.2f}")
            
            # Цветовая индикация соотношения риск/прибыль
            if risk_reward >= 2:
                self.risk_reward_label.setStyleSheet("color: green; font-weight: bold;")
            elif risk_reward >= 1:
                self.risk_reward_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self.risk_reward_label.setStyleSheet("color: red; font-weight: bold;")
        
        except Exception as e:
            self.logger.error(f"Ошибка расчета позиции: {e}")
    
    def _new_backtest(self):
        """
        Создание нового бэктеста
        """
        try:
            dialog = BacktestDialog(self)
            if dialog.exec() == QDialog.Accepted:
                config = dialog.get_config()
                
                # Реальный бэктестинг будет реализован позже
                QMessageBox.information(self, "Бэктестинг", "Функция бэктестинга будет реализована при подключении к API")
        
        except Exception as e:
            self.logger.error(f"Ошибка бэктестинга: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка бэктестинга: {e}")
    
    def _export_backtest(self):
        """
        Экспорт результатов бэктестинга
        """
        QMessageBox.information(self, "Экспорт", "Функция экспорта результатов бэктестинга будет реализована")
    
    def _create_alert(self):
        """
        Создание нового алерта
        """
        try:
            dialog = AlertDialog(self)
            if dialog.exec() == QDialog.Accepted:
                config = dialog.get_config()
                
                # Добавляем алерт в список
                from datetime import datetime
                alert = {
                    "id": len(self.active_alerts) + 1,
                    "created": datetime.now(),
                    **config
                }
                self.active_alerts.append(alert)
                
                # Обновляем таблицу
                self._update_alerts_table()
                
                QMessageBox.information(self, "Алерт", "Алерт создан успешно")
        
        except Exception as e:
            self.logger.error(f"Ошибка создания алерта: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка создания алерта: {e}")
    
    def _delete_alert(self):
        """
        Удаление выбранного алерта
        """
        try:
            current_row = self.alerts_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "Удаление", "Выберите алерт для удаления")
                return
            
            reply = QMessageBox.question(
                self, "Удаление алерта",
                "Вы уверены, что хотите удалить выбранный алерт?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Удаляем из списка
                if current_row < len(self.active_alerts):
                    del self.active_alerts[current_row]
                
                # Обновляем таблицу
                self._update_alerts_table()
        
        except Exception as e:
            self.logger.error(f"Ошибка удаления алерта: {e}")
    
    def _update_alerts_table(self):
        """
        Обновление таблицы алертов
        """
        try:
            self.alerts_table.setRowCount(len(self.active_alerts))
            
            for row, alert in enumerate(self.active_alerts):
                self.alerts_table.setItem(row, 0, QTableWidgetItem(alert['asset']))
                self.alerts_table.setItem(row, 1, QTableWidgetItem(alert['type']))
                self.alerts_table.setItem(row, 2, QTableWidgetItem(str(alert['value'])))
                self.alerts_table.setItem(row, 3, QTableWidgetItem("Активен"))
                self.alerts_table.setItem(row, 4, QTableWidgetItem(alert['created'].strftime("%Y-%m-%d %H:%M")))
                self.alerts_table.setItem(row, 5, QTableWidgetItem(alert['message']))
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления таблицы алертов: {e}")
    
    def _export_csv(self):
        """
        Экспорт данных в CSV
        """
        QMessageBox.information(self, "Экспорт", "Функция экспорта в CSV будет реализована")
    
    def _export_excel(self):
        """
        Экспорт данных в Excel
        """
        QMessageBox.information(self, "Экспорт", "Функция экспорта в Excel будет реализована")
    
    def _export_pdf(self):
        """
        Создание PDF отчета
        """
        QMessageBox.information(self, "Экспорт", "Функция создания PDF отчета будет реализована")
    
    def _update_data(self):
        """
        Обновление данных на вкладке
        """
        try:
            # Проверяем алерты (симуляция)
            import random
            
            for alert in self.active_alerts:
                # Симуляция срабатывания алерта
                if random.random() < 0.01:  # 1% вероятность срабатывания
                    from datetime import datetime
                    message = f"[{datetime.now().strftime('%H:%M:%S')}] Алерт сработал: {alert['message']}\n"
                    self.alert_history.append(message)
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления данных: {e}")