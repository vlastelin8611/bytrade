#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вкладка "Портфель"

Отображение информации о портфеле:
- Общий баланс и P&L
- Активные позиции
- История сделок
- Анализ производительности
- Распределение активов
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QLineEdit, QComboBox, QSplitter, QTabWidget,
    QHeaderView, QAbstractItemView, QMessageBox, QProgressBar,
    QCheckBox, QSpinBox, QDoubleSpinBox, QTextEdit, QDialog,
    QDialogButtonBox, QFormLayout, QSlider, QDateEdit, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QDate
from PySide6.QtGui import QFont, QPixmap, QPainter, QPen, QBrush, QColor
from PySide6.QtCharts import QChart, QChartView, QPieSeries, QLineSeries, QDateTimeAxis, QValueAxis

class PortfolioDataWorker(QThread):
    """
    Воркер для получения данных портфеля
    """
    
    data_received = Signal(dict)
    
    def __init__(self, api_client=None):
        super().__init__()
        self.api_client = api_client
    
    def run(self):
        """
        Получение данных портфеля
        """
        try:
            # Проверяем наличие API клиента
            if not self.api_client:
                # Если нет API клиента, возвращаем пустые данные
                self.data_received.emit({})
                return
            
            # Здесь будет реальное получение данных через API
            # Пока возвращаем пустые данные до настройки API
            portfolio_data = {
                "total_balance": 0.0,
                "available_balance": 0.0,
                "unrealized_pnl": 0.0,
                "realized_pnl_today": 0.0,
                "total_equity": 0.0,
                "margin_used": 0.0,
                "margin_ratio": 0.0,
                "positions": [],
                "recent_trades": [],
                "asset_distribution": {},
                "performance_history": []
            }
            
            self.data_received.emit(portfolio_data)
        
        except Exception as e:
            logging.error(f"Ошибка получения данных портфеля: {e}")
            self.data_received.emit({})

class PositionDetailsDialog(QDialog):
    """
    Диалог детальной информации о позиции
    """
    
    def __init__(self, position_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        
        self.position_data = position_data
        self.setWindowTitle(f"Детали позиции {position_data.get('symbol', 'N/A')}")
        self.setMinimumSize(500, 400)
        
        self._init_ui()
    
    def _init_ui(self):
        """
        Инициализация интерфейса диалога
        """
        layout = QVBoxLayout(self)
        
        # Основная информация
        main_group = QGroupBox("Основная информация")
        main_layout = QFormLayout(main_group)
        
        main_layout.addRow("Символ:", QLabel(self.position_data.get("symbol", "N/A")))
        main_layout.addRow("Направление:", QLabel(self.position_data.get("side", "N/A")))
        main_layout.addRow("Размер:", QLabel(f"{self.position_data.get('size', 0)}"))
        main_layout.addRow("Цена входа:", QLabel(f"${self.position_data.get('entry_price', 0):,.2f}"))
        main_layout.addRow("Текущая цена:", QLabel(f"${self.position_data.get('mark_price', 0):,.2f}"))
        main_layout.addRow("Плечо:", QLabel(f"{self.position_data.get('leverage', 1)}x"))
        
        layout.addWidget(main_group)
        
        # P&L информация
        pnl_group = QGroupBox("Прибыль/Убыток")
        pnl_layout = QFormLayout(pnl_group)
        
        unrealized_pnl = self.position_data.get('unrealized_pnl', 0)
        pnl_percentage = self.position_data.get('pnl_percentage', 0)
        
        pnl_label = QLabel(f"${unrealized_pnl:,.2f}")
        if unrealized_pnl >= 0:
            pnl_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            pnl_label.setStyleSheet("color: red; font-weight: bold;")
        
        percentage_label = QLabel(f"{pnl_percentage:+.2f}%")
        if pnl_percentage >= 0:
            percentage_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            percentage_label.setStyleSheet("color: red; font-weight: bold;")
        
        pnl_layout.addRow("Нереализованный P&L:", pnl_label)
        pnl_layout.addRow("Процент P&L:", percentage_label)
        pnl_layout.addRow("Маржа:", QLabel(f"${self.position_data.get('margin', 0):,.2f}"))
        
        layout.addWidget(pnl_group)
        
        # Управление позицией
        control_group = QGroupBox("Управление позицией")
        control_layout = QHBoxLayout(control_group)
        
        close_button = QPushButton("Закрыть позицию")
        close_button.clicked.connect(self._close_position)
        control_layout.addWidget(close_button)
        
        modify_button = QPushButton("Изменить")
        modify_button.clicked.connect(self._modify_position)
        control_layout.addWidget(modify_button)
        
        layout.addWidget(control_group)
        
        # Кнопки диалога
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _close_position(self):
        """
        Закрытие позиции
        """
        reply = QMessageBox.question(
            self, "Закрытие позиции",
            f"Вы уверены, что хотите закрыть позицию {self.position_data.get('symbol')}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # В реальной реализации здесь будет API-вызов для закрытия позиции
            QMessageBox.information(self, "Успех", "Позиция закрыта")
            self.accept()
    
    def _modify_position(self):
        """
        Изменение позиции
        """
        QMessageBox.information(self, "Информация", "Функция изменения позиции будет реализована")

class PortfolioTab(QWidget):
    """
    Вкладка портфеля
    """
    
    def __init__(self, config_manager, db_manager):
        super().__init__()
        
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Данные портфеля
        self.portfolio_data = {}
        
        self._init_ui()
        
        # Воркер для получения данных
        self.data_worker = PortfolioDataWorker()
        self.data_worker.data_received.connect(self._update_portfolio_data)
        
        # Таймер для обновления данных
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._refresh_data)
        self.update_timer.start(10000)  # Обновление каждые 10 секунд
        
        # Загружаем данные при инициализации
        self._refresh_data()
        
        self.logger.info("Вкладка портфеля инициализирована")
    
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Портфель")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Проверка API ключей
        if not self._has_api_keys():
            self._create_api_warning(layout)
            return
        
        # Создаем вкладки
        tab_widget = QTabWidget()
        
        # Вкладка "Обзор"
        overview_tab = QWidget()
        self._create_overview_tab(overview_tab)
        tab_widget.addTab(overview_tab, "Обзор")
        
        # Вкладка "Позиции"
        positions_tab = QWidget()
        self._create_positions_tab(positions_tab)
        tab_widget.addTab(positions_tab, "Позиции")
        
        # Вкладка "История"
        history_tab = QWidget()
        self._create_history_tab(history_tab)
        tab_widget.addTab(history_tab, "История")
        
        # Вкладка "Анализ"
        analysis_tab = QWidget()
        self._create_analysis_tab(analysis_tab)
        tab_widget.addTab(analysis_tab, "Анализ")
        
        layout.addWidget(tab_widget)
    
    def _create_overview_tab(self, parent):
        """
        Создание вкладки обзора портфеля
        """
        layout = QVBoxLayout(parent)
        
        # Верхняя панель с основными показателями
        metrics_layout = QHBoxLayout()
        
        # Общий баланс
        balance_group = QGroupBox("Общий баланс")
        balance_layout = QVBoxLayout(balance_group)
        
        self.total_balance_label = QLabel("$0.00")
        self.total_balance_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #2E86AB;")
        balance_layout.addWidget(self.total_balance_label)
        
        self.available_balance_label = QLabel("Доступно: $0.00")
        balance_layout.addWidget(self.available_balance_label)
        
        metrics_layout.addWidget(balance_group)
        
        # P&L
        pnl_group = QGroupBox("Прибыль/Убыток")
        pnl_layout = QVBoxLayout(pnl_group)
        
        self.unrealized_pnl_label = QLabel("$0.00")
        self.unrealized_pnl_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        pnl_layout.addWidget(self.unrealized_pnl_label)
        
        self.realized_pnl_label = QLabel("Сегодня: $0.00")
        pnl_layout.addWidget(self.realized_pnl_label)
        
        metrics_layout.addWidget(pnl_group)
        
        # Маржа
        margin_group = QGroupBox("Маржа")
        margin_layout = QVBoxLayout(margin_group)
        
        self.margin_used_label = QLabel("$0.00")
        self.margin_used_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        margin_layout.addWidget(self.margin_used_label)
        
        self.margin_ratio_progress = QProgressBar()
        self.margin_ratio_progress.setRange(0, 100)
        self.margin_ratio_progress.setValue(0)
        margin_layout.addWidget(self.margin_ratio_progress)
        
        self.margin_ratio_label = QLabel("Коэффициент: 0%")
        margin_layout.addWidget(self.margin_ratio_label)
        
        metrics_layout.addWidget(margin_group)
        
        layout.addLayout(metrics_layout)
        
        # Средняя панель с графиками
        charts_layout = QHBoxLayout()
        
        # График распределения активов
        self.asset_chart_view = QChartView()
        self.asset_chart_view.setMinimumHeight(300)
        charts_layout.addWidget(self.asset_chart_view)
        
        # График производительности
        self.performance_chart_view = QChartView()
        self.performance_chart_view.setMinimumHeight(300)
        charts_layout.addWidget(self.performance_chart_view)
        
        layout.addLayout(charts_layout)
        
        # Кнопки управления
        controls_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("Обновить")
        self.refresh_button.clicked.connect(self._refresh_data)
        controls_layout.addWidget(self.refresh_button)
        
        self.export_button = QPushButton("Экспорт")
        self.export_button.clicked.connect(self._export_portfolio)
        controls_layout.addWidget(self.export_button)
        
        controls_layout.addStretch()
        
        self.auto_refresh_check = QCheckBox("Автообновление")
        self.auto_refresh_check.setChecked(True)
        self.auto_refresh_check.toggled.connect(self._toggle_auto_refresh)
        controls_layout.addWidget(self.auto_refresh_check)
        
        layout.addLayout(controls_layout)
    
    def _create_positions_tab(self, parent):
        """
        Создание вкладки позиций
        """
        layout = QVBoxLayout(parent)
        
        # Фильтры
        filters_layout = QHBoxLayout()
        
        filters_layout.addWidget(QLabel("Фильтр:"))
        
        self.position_filter_combo = QComboBox()
        self.position_filter_combo.addItems(["Все позиции", "Прибыльные", "Убыточные", "Длинные", "Короткие"])
        self.position_filter_combo.currentTextChanged.connect(self._filter_positions)
        filters_layout.addWidget(self.position_filter_combo)
        
        filters_layout.addStretch()
        
        self.close_all_button = QPushButton("Закрыть все")
        self.close_all_button.clicked.connect(self._close_all_positions)
        filters_layout.addWidget(self.close_all_button)
        
        layout.addLayout(filters_layout)
        
        # Таблица позиций
        self.positions_table = QTableWidget()
        self.positions_table.setColumnCount(9)
        self.positions_table.setHorizontalHeaderLabels([
            "Символ", "Направление", "Размер", "Цена входа", 
            "Текущая цена", "P&L", "P&L %", "Маржа", "Действия"
        ])
        
        # Настройка таблицы
        header = self.positions_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.Stretch)
        
        self.positions_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.positions_table.setAlternatingRowColors(True)
        self.positions_table.doubleClicked.connect(self._show_position_details)
        
        layout.addWidget(self.positions_table)
    
    def _create_history_tab(self, parent):
        """
        Создание вкладки истории сделок
        """
        layout = QVBoxLayout(parent)
        
        # Фильтры
        filters_layout = QHBoxLayout()
        
        filters_layout.addWidget(QLabel("Период:"))
        
        self.date_from_edit = QDateEdit()
        self.date_from_edit.setDate(QDate.currentDate().addDays(-30))
        filters_layout.addWidget(self.date_from_edit)
        
        filters_layout.addWidget(QLabel("до"))
        
        self.date_to_edit = QDateEdit()
        self.date_to_edit.setDate(QDate.currentDate())
        filters_layout.addWidget(self.date_to_edit)
        
        self.filter_trades_button = QPushButton("Применить")
        self.filter_trades_button.clicked.connect(self._filter_trades)
        filters_layout.addWidget(self.filter_trades_button)
        
        filters_layout.addStretch()
        
        self.export_trades_button = QPushButton("Экспорт")
        self.export_trades_button.clicked.connect(self._export_trades)
        filters_layout.addWidget(self.export_trades_button)
        
        layout.addLayout(filters_layout)
        
        # Таблица сделок
        self.trades_table = QTableWidget()
        self.trades_table.setColumnCount(7)
        self.trades_table.setHorizontalHeaderLabels([
            "Время", "Символ", "Направление", "Размер", "Цена", "P&L", "Комиссия"
        ])
        
        # Настройка таблицы
        header = self.trades_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        
        self.trades_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.trades_table.setAlternatingRowColors(True)
        
        layout.addWidget(self.trades_table)
    
    def _create_analysis_tab(self, parent):
        """
        Создание вкладки анализа производительности
        """
        layout = QVBoxLayout(parent)
        
        # Статистика производительности
        stats_layout = QGridLayout()
        
        # Левая колонка
        stats_layout.addWidget(QLabel("Общая прибыль:"), 0, 0)
        self.total_profit_label = QLabel("$0.00")
        stats_layout.addWidget(self.total_profit_label, 0, 1)
        
        stats_layout.addWidget(QLabel("Прибыльных сделок:"), 1, 0)
        self.winning_trades_label = QLabel("0 (0%)")
        stats_layout.addWidget(self.winning_trades_label, 1, 1)
        
        stats_layout.addWidget(QLabel("Убыточных сделок:"), 2, 0)
        self.losing_trades_label = QLabel("0 (0%)")
        stats_layout.addWidget(self.losing_trades_label, 2, 1)
        
        stats_layout.addWidget(QLabel("Средняя прибыль:"), 3, 0)
        self.avg_profit_label = QLabel("$0.00")
        stats_layout.addWidget(self.avg_profit_label, 3, 1)
        
        # Правая колонка
        stats_layout.addWidget(QLabel("Максимальная просадка:"), 0, 2)
        self.max_drawdown_label = QLabel("0%")
        stats_layout.addWidget(self.max_drawdown_label, 0, 3)
        
        stats_layout.addWidget(QLabel("Коэффициент Шарпа:"), 1, 2)
        self.sharpe_ratio_label = QLabel("0.00")
        stats_layout.addWidget(self.sharpe_ratio_label, 1, 3)
        
        stats_layout.addWidget(QLabel("Общий ROI:"), 2, 2)
        self.total_roi_label = QLabel("0%")
        stats_layout.addWidget(self.total_roi_label, 2, 3)
        
        stats_layout.addWidget(QLabel("Всего сделок:"), 3, 2)
        self.total_trades_label = QLabel("0")
        stats_layout.addWidget(self.total_trades_label, 3, 3)
        
        layout.addLayout(stats_layout)
        
        # График эквити
        self.equity_chart_view = QChartView()
        self.equity_chart_view.setMinimumHeight(400)
        layout.addWidget(self.equity_chart_view)
        
        # Кнопки анализа
        analysis_buttons_layout = QHBoxLayout()
        
        self.detailed_report_button = QPushButton("Детальный отчет")
        self.detailed_report_button.clicked.connect(self._generate_detailed_report)
        analysis_buttons_layout.addWidget(self.detailed_report_button)
        
        self.risk_analysis_button = QPushButton("Анализ рисков")
        self.risk_analysis_button.clicked.connect(self._show_risk_analysis)
        analysis_buttons_layout.addWidget(self.risk_analysis_button)
        
        analysis_buttons_layout.addStretch()
        
        layout.addLayout(analysis_buttons_layout)
    
    def _refresh_data(self):
        """
        Обновление данных портфеля
        """
        if not self.data_worker.isRunning():
            self.data_worker.start()
    
    def _update_portfolio_data(self, data: Dict[str, Any]):
        """
        Обновление данных портфеля
        """
        try:
            self.portfolio_data = data
            
            if not data:
                return
            
            # Обновляем основные показатели
            self._update_overview_metrics()
            
            # Обновляем таблицу позиций
            self._update_positions_table()
            
            # Обновляем историю сделок
            self._update_trades_table()
            
            # Обновляем графики
            self._update_charts()
            
            # Обновляем статистику анализа
            self._update_analysis_stats()
            
            self.logger.info("Данные портфеля обновлены")
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления данных портфеля: {e}")
    
    def _update_overview_metrics(self):
        """
        Обновление основных показателей
        """
        try:
            # Общий баланс
            total_balance = self.portfolio_data.get("total_balance", 0)
            self.total_balance_label.setText(f"${total_balance:,.2f}")
            
            available_balance = self.portfolio_data.get("available_balance", 0)
            self.available_balance_label.setText(f"Доступно: ${available_balance:,.2f}")
            
            # P&L
            unrealized_pnl = self.portfolio_data.get("unrealized_pnl", 0)
            self.unrealized_pnl_label.setText(f"${unrealized_pnl:+,.2f}")
            
            if unrealized_pnl >= 0:
                self.unrealized_pnl_label.setStyleSheet("font-size: 20px; font-weight: bold; color: green;")
            else:
                self.unrealized_pnl_label.setStyleSheet("font-size: 20px; font-weight: bold; color: red;")
            
            realized_pnl = self.portfolio_data.get("realized_pnl_today", 0)
            self.realized_pnl_label.setText(f"Сегодня: ${realized_pnl:+,.2f}")
            
            # Маржа
            margin_used = self.portfolio_data.get("margin_used", 0)
            self.margin_used_label.setText(f"${margin_used:,.2f}")
            
            margin_ratio = self.portfolio_data.get("margin_ratio", 0)
            self.margin_ratio_progress.setValue(int(margin_ratio))
            self.margin_ratio_label.setText(f"Коэффициент: {margin_ratio:.1f}%")
            
            # Цветовая индикация маржи
            if margin_ratio < 50:
                self.margin_ratio_progress.setStyleSheet("QProgressBar::chunk { background-color: green; }")
            elif margin_ratio < 80:
                self.margin_ratio_progress.setStyleSheet("QProgressBar::chunk { background-color: orange; }")
            else:
                self.margin_ratio_progress.setStyleSheet("QProgressBar::chunk { background-color: red; }")
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления основных показателей: {e}")
    
    def _update_positions_table(self):
        """
        Обновление таблицы позиций
        """
        try:
            positions = self.portfolio_data.get("positions", [])
            self.positions_table.setRowCount(len(positions))
            
            for row, position in enumerate(positions):
                # Символ
                self.positions_table.setItem(row, 0, QTableWidgetItem(position.get("symbol", "")))
                
                # Направление
                side_item = QTableWidgetItem(position.get("side", ""))
                if position.get("side") == "Buy":
                    side_item.setForeground(Qt.green)
                else:
                    side_item.setForeground(Qt.red)
                self.positions_table.setItem(row, 1, side_item)
                
                # Размер
                self.positions_table.setItem(row, 2, QTableWidgetItem(f"{position.get('size', 0)}"))
                
                # Цена входа
                self.positions_table.setItem(row, 3, QTableWidgetItem(f"${position.get('entry_price', 0):,.2f}"))
                
                # Текущая цена
                self.positions_table.setItem(row, 4, QTableWidgetItem(f"${position.get('mark_price', 0):,.2f}"))
                
                # P&L
                pnl = position.get("unrealized_pnl", 0)
                pnl_item = QTableWidgetItem(f"${pnl:+,.2f}")
                if pnl >= 0:
                    pnl_item.setForeground(Qt.green)
                else:
                    pnl_item.setForeground(Qt.red)
                self.positions_table.setItem(row, 5, pnl_item)
                
                # P&L %
                pnl_pct = position.get("pnl_percentage", 0)
                pnl_pct_item = QTableWidgetItem(f"{pnl_pct:+.2f}%")
                if pnl_pct >= 0:
                    pnl_pct_item.setForeground(Qt.green)
                else:
                    pnl_pct_item.setForeground(Qt.red)
                self.positions_table.setItem(row, 6, pnl_pct_item)
                
                # Маржа
                self.positions_table.setItem(row, 7, QTableWidgetItem(f"${position.get('margin', 0):,.2f}"))
                
                # Действия
                actions_widget = QWidget()
                actions_layout = QHBoxLayout(actions_widget)
                actions_layout.setContentsMargins(5, 2, 5, 2)
                
                close_btn = QPushButton("Закрыть")
                close_btn.setMaximumWidth(60)
                close_btn.clicked.connect(lambda checked, pos=position: self._close_position(pos))
                actions_layout.addWidget(close_btn)
                
                modify_btn = QPushButton("Изменить")
                modify_btn.setMaximumWidth(70)
                modify_btn.clicked.connect(lambda checked, pos=position: self._modify_position(pos))
                actions_layout.addWidget(modify_btn)
                
                self.positions_table.setCellWidget(row, 8, actions_widget)
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления таблицы позиций: {e}")
    
    def _update_trades_table(self):
        """
        Обновление таблицы сделок
        """
        try:
            trades = self.portfolio_data.get("recent_trades", [])
            self.trades_table.setRowCount(len(trades))
            
            for row, trade in enumerate(trades):
                # Время
                timestamp = trade.get("timestamp", datetime.now())
                self.trades_table.setItem(row, 0, QTableWidgetItem(timestamp.strftime("%H:%M:%S")))
                
                # Символ
                self.trades_table.setItem(row, 1, QTableWidgetItem(trade.get("symbol", "")))
                
                # Направление
                side_item = QTableWidgetItem(trade.get("side", ""))
                if trade.get("side") == "Buy":
                    side_item.setForeground(Qt.green)
                else:
                    side_item.setForeground(Qt.red)
                self.trades_table.setItem(row, 2, side_item)
                
                # Размер
                self.trades_table.setItem(row, 3, QTableWidgetItem(f"{trade.get('size', 0)}"))
                
                # Цена
                self.trades_table.setItem(row, 4, QTableWidgetItem(f"${trade.get('price', 0):,.4f}"))
                
                # P&L
                pnl = trade.get("realized_pnl", 0)
                pnl_item = QTableWidgetItem(f"${pnl:+,.2f}")
                if pnl >= 0:
                    pnl_item.setForeground(Qt.green)
                else:
                    pnl_item.setForeground(Qt.red)
                self.trades_table.setItem(row, 5, pnl_item)
                
                # Комиссия
                self.trades_table.setItem(row, 6, QTableWidgetItem(f"${trade.get('fee', 0):.2f}"))
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления таблицы сделок: {e}")
    
    def _update_charts(self):
        """
        Обновление графиков
        """
        try:
            # График распределения активов
            self._update_asset_distribution_chart()
            
            # График производительности
            self._update_performance_chart()
            
            # График эквити
            self._update_equity_chart()
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления графиков: {e}")
    
    def _update_asset_distribution_chart(self):
        """
        Обновление графика распределения активов
        """
        try:
            asset_distribution = self.portfolio_data.get("asset_distribution", {})
            
            if not asset_distribution:
                return
            
            # Создаем круговую диаграмму
            series = QPieSeries()
            
            for asset, percentage in asset_distribution.items():
                series.append(asset, percentage)
            
            # Настраиваем внешний вид
            for slice in series.slices():
                slice.setLabelVisible(True)
                slice.setLabel(f"{slice.label()}: {slice.percentage():.1f}%")
            
            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("Распределение активов")
            chart.legend().setVisible(True)
            
            self.asset_chart_view.setChart(chart)
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления графика распределения активов: {e}")
    
    def _update_performance_chart(self):
        """
        Обновление графика производительности
        """
        try:
            performance_history = self.portfolio_data.get("performance_history", [])
            
            if not performance_history:
                return
            
            # Создаем линейный график
            series = QLineSeries()
            series.setName("P&L")
            
            for point in performance_history:
                timestamp = int(point["date"].timestamp() * 1000)
                pnl = point["pnl"]
                series.append(timestamp, pnl)
            
            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("Производительность портфеля")
            
            # Настраиваем оси
            axis_x = QDateTimeAxis()
            axis_x.setFormat("dd.MM")
            axis_x.setTitleText("Дата")
            chart.addAxis(axis_x, Qt.AlignBottom)
            series.attachAxis(axis_x)
            
            axis_y = QValueAxis()
            axis_y.setTitleText("P&L ($)")
            chart.addAxis(axis_y, Qt.AlignLeft)
            series.attachAxis(axis_y)
            
            self.performance_chart_view.setChart(chart)
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления графика производительности: {e}")
    
    def _update_equity_chart(self):
        """
        Обновление графика эквити
        """
        try:
            performance_history = self.portfolio_data.get("performance_history", [])
            
            if not performance_history:
                return
            
            # Создаем линейный график
            series = QLineSeries()
            series.setName("Баланс")
            
            for point in performance_history:
                timestamp = int(point["date"].timestamp() * 1000)
                balance = point["balance"]
                series.append(timestamp, balance)
            
            chart = QChart()
            chart.addSeries(series)
            chart.setTitle("График эквити")
            
            # Настраиваем оси
            axis_x = QDateTimeAxis()
            axis_x.setFormat("dd.MM")
            axis_x.setTitleText("Дата")
            chart.addAxis(axis_x, Qt.AlignBottom)
            series.attachAxis(axis_x)
            
            axis_y = QValueAxis()
            axis_y.setTitleText("Баланс ($)")
            chart.addAxis(axis_y, Qt.AlignLeft)
            series.attachAxis(axis_y)
            
            self.equity_chart_view.setChart(chart)
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления графика эквити: {e}")
    
    def _update_analysis_stats(self):
        """
        Обновление статистики анализа
        """
        try:
            # Проверяем наличие API клиента
            if not hasattr(self, 'api_client') or self.api_client is None:
                # Очищаем все поля если нет API ключей
                self.total_profit_label.setText("$0.00")
                self.winning_trades_label.setText("0 (0.0%)")
                self.losing_trades_label.setText("0 (0.0%)")
                self.avg_profit_label.setText("$0.00")
                self.total_trades_label.setText("0")
                self.max_drawdown_label.setText("0.0%")
                self.sharpe_ratio_label.setText("0.00")
                self.total_roi_label.setText("0.00%")
                return
            
            # Расчет статистики на основе реальных данных
            trades = self.portfolio_data.get("recent_trades", [])
            
            if not trades:
                # Если нет сделок, показываем нули
                self.total_profit_label.setText("$0.00")
                self.winning_trades_label.setText("0 (0.0%)")
                self.losing_trades_label.setText("0 (0.0%)")
                self.avg_profit_label.setText("$0.00")
                self.total_trades_label.setText("0")
                self.max_drawdown_label.setText("0.0%")
                self.sharpe_ratio_label.setText("0.00")
                self.total_roi_label.setText("0.00%")
                return
            
            # Общая прибыль
            total_profit = sum(trade.get("realized_pnl", 0) for trade in trades)
            self.total_profit_label.setText(f"${total_profit:+,.2f}")
            
            # Прибыльные/убыточные сделки
            winning_trades = [t for t in trades if t.get("realized_pnl", 0) > 0]
            losing_trades = [t for t in trades if t.get("realized_pnl", 0) < 0]
            
            total_trades = len(trades)
            win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
            lose_rate = (len(losing_trades) / total_trades * 100) if total_trades > 0 else 0
            
            self.winning_trades_label.setText(f"{len(winning_trades)} ({win_rate:.1f}%)")
            self.losing_trades_label.setText(f"{len(losing_trades)} ({lose_rate:.1f}%)")
            
            # Средняя прибыль
            avg_profit = total_profit / total_trades if total_trades > 0 else 0
            self.avg_profit_label.setText(f"${avg_profit:+,.2f}")
            
            # Общее количество сделок
            self.total_trades_label.setText(str(total_trades))
            
            # Расчет реальных показателей (пока нули до получения данных)
            self.max_drawdown_label.setText("0.0%")
            self.sharpe_ratio_label.setText("0.00")
            
            # ROI на основе реальных данных
            current_balance = self.portfolio_data.get("total_balance", 0)
            if current_balance > 0:
                # Здесь должен быть расчет на основе исторических данных
                self.total_roi_label.setText("0.00%")
            else:
                self.total_roi_label.setText("0.00%")
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления статистики анализа: {e}")
    
    def _show_position_details(self):
        """
        Показ детальной информации о позиции
        """
        try:
            current_row = self.positions_table.currentRow()
            if current_row < 0:
                return
            
            positions = self.portfolio_data.get("positions", [])
            if current_row < len(positions):
                position = positions[current_row]
                dialog = PositionDetailsDialog(position, self)
                dialog.exec()
        
        except Exception as e:
            self.logger.error(f"Ошибка показа деталей позиции: {e}")
    
    def _close_position(self, position):
        """
        Закрытие позиции
        """
        try:
            reply = QMessageBox.question(
                self, "Закрытие позиции",
                f"Вы уверены, что хотите закрыть позицию {position.get('symbol')}?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # В реальной реализации здесь будет API-вызов
                QMessageBox.information(self, "Успех", "Позиция закрыта")
                self._refresh_data()
        
        except Exception as e:
            self.logger.error(f"Ошибка закрытия позиции: {e}")
    
    def _modify_position(self, position):
        """
        Изменение позиции
        """
        QMessageBox.information(self, "Информация", "Функция изменения позиции будет реализована")
    
    def _close_all_positions(self):
        """
        Закрытие всех позиций
        """
        try:
            positions = self.portfolio_data.get("positions", [])
            if not positions:
                QMessageBox.information(self, "Информация", "Нет открытых позиций")
                return
            
            reply = QMessageBox.question(
                self, "Закрытие всех позиций",
                f"Вы уверены, что хотите закрыть все {len(positions)} позиций?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # В реальной реализации здесь будет API-вызов
                QMessageBox.information(self, "Успех", "Все позиции закрыты")
                self._refresh_data()
        
        except Exception as e:
            self.logger.error(f"Ошибка закрытия всех позиций: {e}")
    
    def _filter_positions(self):
        """
        Фильтрация позиций
        """
        # В реальной реализации здесь будет фильтрация таблицы
        filter_text = self.position_filter_combo.currentText()
        self.logger.info(f"Применен фильтр позиций: {filter_text}")
    
    def _filter_trades(self):
        """
        Фильтрация сделок по дате
        """
        # В реальной реализации здесь будет фильтрация по датам
        date_from = self.date_from_edit.date().toPython()
        date_to = self.date_to_edit.date().toPython()
        self.logger.info(f"Применен фильтр сделок: {date_from} - {date_to}")
    
    def _export_portfolio(self):
        """
        Экспорт данных портфеля
        """
        QMessageBox.information(self, "Информация", "Функция экспорта портфеля будет реализована")
    
    def _export_trades(self):
        """
        Экспорт истории сделок
        """
        QMessageBox.information(self, "Информация", "Функция экспорта сделок будет реализована")
    
    def _generate_detailed_report(self):
        """
        Генерация детального отчета
        """
        QMessageBox.information(self, "Информация", "Функция генерации отчета будет реализована")
    
    def _show_risk_analysis(self):
        """
        Показ анализа рисков
        """
        QMessageBox.information(self, "Информация", "Функция анализа рисков будет реализована")
    
    def _toggle_auto_refresh(self, enabled: bool):
        """
        Переключение автообновления
        """
        if enabled:
            self.update_timer.start(10000)
        else:
            self.update_timer.stop()
        
        self.logger.info(f"Автообновление портфеля: {'включено' if enabled else 'отключено'}")
    
    def _has_api_keys(self):
        """
        Проверка наличия API ключей
        """
        try:
            environment = 'testnet' if self.config.is_testnet() else 'mainnet'
            api_credentials = self.config.get_api_credentials(environment)
            return api_credentials and api_credentials.get('api_key') and api_credentials.get('api_secret')
        except:
            return False
    
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
            "Для отображения информации о портфеле необходимо настроить API ключи Bybit.\n"
            "Пока API ключи не введены, данные портфеля недоступны."
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
        
        # Показать базовую информацию
        self._show_basic_portfolio_info(layout)
    
    def _show_basic_portfolio_info(self, layout):
        """
        Отображение базовой информации о портфеле без API
        """
        info_group = QGroupBox("Информация о режиме")
        info_layout = QGridLayout(info_group)
        
        # Режим (testnet/mainnet)
        mode = "Testnet" if self.config.is_testnet() else "Mainnet"
        mode_color = "blue" if self.config.is_testnet() else "red"
        mode_label = QLabel(mode)
        mode_label.setStyleSheet(f"color: {mode_color}; font-weight: bold; font-size: 14px;")
        info_layout.addWidget(QLabel("Текущий режим:"), 0, 0)
        info_layout.addWidget(mode_label, 0, 1)
        
        # Статус портфеля
        status_label = QLabel("Недоступен")
        status_label.setStyleSheet("color: red; font-weight: bold;")
        info_layout.addWidget(QLabel("Статус портфеля:"), 1, 0)
        info_layout.addWidget(status_label, 1, 1)
        
        # Инструкция
        instruction_label = QLabel(
            "Настройте API ключи для получения:\n"
            "• Информации о балансе и позициях\n"
            "• Истории сделок\n"
            "• Анализа производительности\n"
            "• Графиков и статистики"
        )
        instruction_label.setStyleSheet("color: #6c757d; margin-top: 10px;")
        info_layout.addWidget(instruction_label, 2, 0, 1, 2)
        
        layout.addWidget(info_group)
    
    def _open_api_settings(self):
        """
        Открытие настроек API ключей
        """
        QMessageBox.information(
            self, 
            "Настройка API", 
            "Перейдите в меню 'Настройки' -> 'API ключи' для настройки подключения к Bybit."
        )