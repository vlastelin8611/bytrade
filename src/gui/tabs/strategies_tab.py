#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вкладка "Стратегии"

Управление торговыми стратегиями:
- Список доступных стратегий
- Настройка параметров стратегий
- Запуск/остановка стратегий
- Мониторинг активных стратегий
- Создание отдельных окон для каждой стратегии
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QPushButton, QTableWidget, QTableWidgetItem,
    QGroupBox, QLineEdit, QComboBox, QSplitter, QTabWidget,
    QHeaderView, QAbstractItemView, QMessageBox, QProgressBar,
    QCheckBox, QSpinBox, QDoubleSpinBox, QTextEdit, QDialog,
    QDialogButtonBox, QFormLayout, QSlider
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread
from PySide6.QtGui import QFont, QPixmap, QColor

# Импорт стратегий
from ...strategies import (
    StrategyEngine, AVAILABLE_STRATEGIES, STRATEGY_METADATA,
    get_strategy_class, get_strategy_metadata
)

# Импорт менеджера окон стратегий
from ..strategy_window_manager import StrategyWindowManager

# Импорт селектора активов
from ...utils.asset_selector import AssetSelector

# Старый класс StrategyWindow полностью удален - теперь используется из strategy_window.py

class StrategyConfigDialog(QDialog):
    """
    Диалог настройки стратегии
    """
    
    def __init__(self, strategy_name: str, parent=None):
        super().__init__(parent)
        
        self.strategy_name = strategy_name
        self.config = {}
        self.parent_tab = parent  # Сохраняем ссылку на родительскую вкладку
        
        self.setWindowTitle(f"Настройка стратегии: {strategy_name}")
        self.setMinimumSize(400, 500)
        
        self._init_ui()
    
    def _init_ui(self):
        """
        Инициализация интерфейса диалога
        """
        layout = QVBoxLayout(self)
        
        # Форма настроек
        form_layout = QFormLayout()
        
        # Автоматический выбор актива
        self.auto_asset_checkbox = QCheckBox("Автоматический выбор актива")
        self.auto_asset_checkbox.setChecked(True)
        form_layout.addRow("", self.auto_asset_checkbox)
        
        # Актив (скрыт при автоматическом выборе)
        self.asset_combo = QComboBox()
        self._populate_asset_combo()
        self.asset_combo.setEnabled(False)
        form_layout.addRow("Актив:", self.asset_combo)
        
        # Подключаем обработчик изменения чекбокса
        self.auto_asset_checkbox.stateChanged.connect(self._on_auto_asset_changed)
        
        # Размер позиции (%)
        self.position_size_spin = QDoubleSpinBox()
        self.position_size_spin.setRange(0.1, 20.0)
        self.position_size_spin.setValue(5.0)
        self.position_size_spin.setSuffix("%")
        form_layout.addRow("Размер позиции:", self.position_size_spin)
        
        # Стоп-лосс (%)
        self.stop_loss_spin = QDoubleSpinBox()
        self.stop_loss_spin.setRange(0.5, 40.0)
        self.stop_loss_spin.setValue(5.0)
        self.stop_loss_spin.setSuffix("%")
        form_layout.addRow("Стоп-лосс:", self.stop_loss_spin)
        
        # Тейк-профит (%)
        self.take_profit_spin = QDoubleSpinBox()
        self.take_profit_spin.setRange(1.0, 100.0)
        self.take_profit_spin.setValue(10.0)
        self.take_profit_spin.setSuffix("%")
        form_layout.addRow("Тейк-профит:", self.take_profit_spin)
        
        # Таймфрейм
        self.timeframe_combo = QComboBox()
        self.timeframe_combo.addItems(["1m", "5m", "15m", "1h", "4h", "1d"])
        self.timeframe_combo.setCurrentText("1h")
        form_layout.addRow("Таймфрейм:", self.timeframe_combo)
        
        # Специфичные настройки для адаптивной стратегии
        if "адаптивная" in self.strategy_name.lower():
            # Период анализа
            self.analysis_period_spin = QSpinBox()
            self.analysis_period_spin.setRange(30, 1095)  # от 30 дней до 3 лет
            self.analysis_period_spin.setValue(365)
            self.analysis_period_spin.setSuffix(" дней")
            form_layout.addRow("Период анализа:", self.analysis_period_spin)
            
            # Минимальная прибыль для входа
            self.min_profit_spin = QDoubleSpinBox()
            self.min_profit_spin.setRange(0.5, 10.0)
            self.min_profit_spin.setValue(2.0)
            self.min_profit_spin.setSuffix("%")
            form_layout.addRow("Мин. прибыль:", self.min_profit_spin)
            
            # Максимальный риск
            self.max_risk_spin = QDoubleSpinBox()
            self.max_risk_spin.setRange(1.0, 20.0)
            self.max_risk_spin.setValue(5.0)
            self.max_risk_spin.setSuffix("%")
            form_layout.addRow("Макс. риск:", self.max_risk_spin)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def _on_auto_asset_changed(self, state):
        """
        Обработчик изменения состояния автоматического выбора актива
        """
        auto_enabled = state == Qt.Checked
        self.asset_combo.setEnabled(not auto_enabled)
        
        if auto_enabled:
            # При включении автоматического режима можно показать подсказку
            self.asset_combo.setToolTip("Актив будет выбран автоматически на основе анализа рынка")
        else:
            self.asset_combo.setToolTip("Выберите актив для торговли вручную")
    
    def get_config(self) -> Dict[str, Any]:
        """
        Получение конфигурации стратегии
        """
        config = {
            "asset": self.asset_combo.currentText(),
            "position_size": self.position_size_spin.value(),
            "stop_loss": self.stop_loss_spin.value(),
            "take_profit": self.take_profit_spin.value(),
            "timeframe": self.timeframe_combo.currentText()
        }
        
        # Добавляем специфичные настройки для адаптивной стратегии
        if "адаптивная" in self.strategy_name.lower():
            config.update({
                "analysis_period": self.analysis_period_spin.value(),
                "min_profit": self.min_profit_spin.value(),
                "max_risk": self.max_risk_spin.value()
            })
        
        # Добавляем настройку автоматического выбора актива
        config["auto_asset_selection"] = self.auto_asset_checkbox.isChecked()
        
        return config
    
    def _populate_asset_combo(self):
        """
        Заполнение комбобокса активов динамическим списком
        """
        try:
            # Добавляем популярные активы по умолчанию
            default_assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "ADAUSDT", "DOGEUSDT", "BNBUSDT", "XRPUSDT", "MATICUSDT"]
            self.asset_combo.addItems(default_assets)
            
            # Если есть доступ к API через родительскую вкладку, получаем полный список
            if hasattr(self.parent_tab, 'api_client') and self.parent_tab.api_client:
                try:
                    import asyncio
                    from ...utils.asset_selector import AssetSelector
                    
                    # Создаем AssetSelector для получения списка активов
                    asset_selector = AssetSelector(self.parent_tab.api_client, self.parent_tab.db, self.parent_tab.config)
                    
                    # Получаем список активов асинхронно
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    try:
                        available_assets = loop.run_until_complete(asset_selector._get_available_assets())
                        
                        if available_assets:
                            # Очищаем комбобокс и добавляем все доступные активы
                            self.asset_combo.clear()
                            # Сортируем активы для удобства
                            available_assets.sort()
                            self.asset_combo.addItems(available_assets)
                            
                            # Устанавливаем BTCUSDT по умолчанию если он есть в списке
                            btc_index = self.asset_combo.findText("BTCUSDT")
                            if btc_index >= 0:
                                self.asset_combo.setCurrentIndex(btc_index)
                                
                    finally:
                        loop.close()
                        
                except Exception as e:
                    # В случае ошибки оставляем список по умолчанию
                    print(f"Ошибка получения списка активов: {e}")
                    
        except Exception as e:
            print(f"Ошибка заполнения списка активов: {e}")


class StrategiesTab(QWidget):
    """
    Вкладка управления стратегиями
    """
    
    def __init__(self, config_manager, db_manager, api_client=None):
        super().__init__()
        
        self.config = config_manager
        self.db = db_manager
        self.api_client = api_client
        self.logger = logging.getLogger(__name__)
        
        # Инициализация движка стратегий
        if api_client:
            self.strategy_engine = StrategyEngine(api_client, db_manager, config_manager)
        else:
            self.strategy_engine = None
            self.logger.warning("API клиент не предоставлен, стратегии будут работать в демо-режиме")
        
        # Активные стратегии и менеджер окон
        self.active_strategies: Dict[str, Dict[str, Any]] = {}
        self.window_manager = StrategyWindowManager()
        
        # Доступные стратегии из модуля стратегий
        self.available_strategies = self._build_available_strategies_dict()
        
        # Таймер для обновления статуса стратегий
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_strategies_status)
        self.update_timer.start(5000)  # Обновление каждые 5 секунд
        
        self._init_ui()
        
        self.logger.info("Вкладка стратегий инициализирована")
    
    def _build_available_strategies_dict(self) -> Dict[str, Dict[str, Any]]:
        """
        Построение словаря доступных стратегий из метаданных
        """
        strategies_dict = {}
        
        # Маппинг имен стратегий для отображения
        name_mapping = {
            'moving_averages': 'Скользящие средние (MA)',
            'rsi_macd': 'RSI + MACD',
            'bollinger_bands': 'Bollinger Bands',
            'momentum_trading': 'Momentum Trading',
            'grid_trading': 'Grid Trading',
            'adaptive_ml': 'Адаптивная ML стратегия'
        }
        
        # Маппинг уровней риска
        risk_mapping = {
            'Low': 'Низкий',
            'Medium': 'Средний', 
            'High': 'Высокий'
        }
        
        for strategy_key, metadata in STRATEGY_METADATA.items():
            display_name = name_mapping.get(strategy_key, metadata['name'])
            risk_level = risk_mapping.get(metadata['risk_level'], metadata['risk_level'])
            
            strategies_dict[display_name] = {
                'description': metadata['description'],
                'risk_level': risk_level,
                'popularity': 'Высокая' if strategy_key in ['moving_averages', 'rsi_macd'] else 'Средняя',
                'effectiveness': '85%' if strategy_key == 'adaptive_ml' else '75%',
                'strategy_key': strategy_key  # Добавляем ключ для связи с классом стратегии
            }
        
        return strategies_dict
    
    def _update_strategies_status(self):
        """
        Обновление статуса активных стратегий
        """
        if not self.strategy_engine:
            return
            
        try:
            # Получаем статус всех стратегий от движка
            strategies_status = self.strategy_engine.get_strategies_status()
            
            # Обновляем локальную информацию
            for strategy_id, status in strategies_status.items():
                if strategy_id in self.active_strategies:
                    # Преобразуем состояние стратегии в читаемый статус
                    state = status.get('state', 'UNKNOWN')
                    if state == 'StrategyState.RUNNING':
                        display_status = 'RUNNING'
                    elif state == 'StrategyState.PAUSED':
                        display_status = 'PAUSED'
                    elif state == 'StrategyState.STOPPED':
                        display_status = 'STOPPED'
                    elif state == 'StrategyState.ERROR':
                        display_status = 'ERROR'
                    else:
                        display_status = str(state).replace('StrategyState.', '')
                    
                    self.active_strategies[strategy_id].update({
                        'status': display_status,
                        'pnl': status.get('total_pnl', 0.0),
                        'trades_count': status.get('trades_count', 0)
                    })
            
            # Обновляем таблицу
            self._update_active_strategies_table()
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса стратегий: {e}")
    
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Управление торговыми стратегиями")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Основной сплиттер
        main_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(main_splitter)
        
        # Левая панель - доступные стратегии
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        self._create_available_strategies(left_layout)
        main_splitter.addWidget(left_widget)
        
        # Правая панель - активные стратегии
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        self._create_active_strategies(right_layout)
        main_splitter.addWidget(right_widget)
        
        # Установка пропорций
        main_splitter.setSizes([500, 500])
        
        # Кнопки управления
        self._create_control_buttons(layout)
    
    def _create_available_strategies(self, layout):
        """
        Создание списка доступных стратегий
        """
        group = QGroupBox("Доступные стратегии")
        group_layout = QVBoxLayout(group)
        
        # Таблица стратегий
        self.strategies_table = QTableWidget()
        self.strategies_table.setColumnCount(4)
        self.strategies_table.setHorizontalHeaderLabels([
            "Стратегия", "Риск", "Популярность", "Эффективность"
        ])
        
        # Настройка таблицы
        header = self.strategies_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 4):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        self.strategies_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.strategies_table.setAlternatingRowColors(True)
        
        # Заполнение таблицы
        self._populate_strategies_table()
        
        group_layout.addWidget(self.strategies_table)
        
        # Описание выбранной стратегии
        desc_group = QGroupBox("Описание стратегии")
        desc_layout = QVBoxLayout(desc_group)
        
        self.strategy_description = QTextEdit()
        self.strategy_description.setReadOnly(True)
        self.strategy_description.setMaximumHeight(100)
        desc_layout.addWidget(self.strategy_description)
        
        group_layout.addWidget(desc_group)
        
        # Кнопки для работы со стратегиями
        button_layout = QHBoxLayout()
        
        self.configure_button = QPushButton("Настроить")
        self.configure_button.clicked.connect(self._configure_strategy)
        button_layout.addWidget(self.configure_button)
        
        self.start_button = QPushButton("Запустить")
        self.start_button.clicked.connect(self._start_strategy)
        button_layout.addWidget(self.start_button)
        
        group_layout.addLayout(button_layout)
        
        # Обработчик выбора стратегии
        self.strategies_table.itemSelectionChanged.connect(self._on_strategy_selected)
        
        layout.addWidget(group)
    
    def _create_active_strategies(self, layout):
        """
        Создание списка активных стратегий
        """
        group = QGroupBox("Активные стратегии")
        group_layout = QVBoxLayout(group)
        
        # Таблица активных стратегий
        self.active_table = QTableWidget()
        self.active_table.setColumnCount(5)
        self.active_table.setHorizontalHeaderLabels([
            "Стратегия", "Актив", "Статус", "P&L", "Время работы"
        ])
        
        # Настройка таблицы
        header = self.active_table.horizontalHeader()
        for i in range(5):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        self.active_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.active_table.setAlternatingRowColors(True)
        
        group_layout.addWidget(self.active_table)
        
        # Кнопки управления активными стратегиями
        active_button_layout = QHBoxLayout()
        
        self.show_window_button = QPushButton("Показать окно")
        self.show_window_button.clicked.connect(self._show_strategy_window)
        active_button_layout.addWidget(self.show_window_button)
        
        self.pause_button = QPushButton("Пауза")
        self.pause_button.clicked.connect(self._pause_strategy)
        active_button_layout.addWidget(self.pause_button)
        
        self.stop_strategy_button = QPushButton("Остановить")
        self.stop_strategy_button.clicked.connect(self._stop_strategy)
        active_button_layout.addWidget(self.stop_strategy_button)
        
        group_layout.addLayout(active_button_layout)
        
        layout.addWidget(group)
    
    def _create_control_buttons(self, layout):
        """
        Создание кнопок управления
        """
        button_layout = QHBoxLayout()
        
        # Кнопка остановки всех стратегий
        self.stop_all_button = QPushButton("Остановить все")
        self.stop_all_button.clicked.connect(self._stop_all_strategies)
        button_layout.addWidget(self.stop_all_button)
        
        # Кнопка экстренной остановки
        self.emergency_stop_button = QPushButton("ЭКСТРЕННАЯ ОСТАНОВКА")
        self.emergency_stop_button.setStyleSheet("background-color: red; color: white; font-weight: bold;")
        self.emergency_stop_button.clicked.connect(self._emergency_stop)
        button_layout.addWidget(self.emergency_stop_button)
        
        button_layout.addStretch()
        
        # Кнопка экспорта отчета
        self.export_report_button = QPushButton("Экспорт отчета")
        self.export_report_button.clicked.connect(self._export_report)
        button_layout.addWidget(self.export_report_button)
        
        layout.addLayout(button_layout)
    
    def _populate_strategies_table(self):
        """
        Заполнение таблицы доступных стратегий
        """
        self.strategies_table.setRowCount(len(self.available_strategies))
        
        for row, (name, info) in enumerate(self.available_strategies.items()):
            # Название стратегии
            self.strategies_table.setItem(row, 0, QTableWidgetItem(name))
            
            # Уровень риска
            risk_item = QTableWidgetItem(info['risk_level'])
            risk_colors = {"Низкий": Qt.green, "Средний": QColor(255, 165, 0), "Высокий": Qt.red, "Переменный": Qt.blue}
            if info['risk_level'] in risk_colors:
                risk_item.setForeground(risk_colors[info['risk_level']])
            self.strategies_table.setItem(row, 1, risk_item)
            
            # Популярность
            self.strategies_table.setItem(row, 2, QTableWidgetItem(info['popularity']))
            
            # Эффективность
            self.strategies_table.setItem(row, 3, QTableWidgetItem(info['effectiveness']))
    
    def _on_strategy_selected(self):
        """
        Обработчик выбора стратегии
        """
        try:
            current_row = self.strategies_table.currentRow()
            if current_row >= 0:
                strategy_name = self.strategies_table.item(current_row, 0).text()
                strategy_info = self.available_strategies.get(strategy_name, {})
                description = strategy_info.get('description', 'Описание недоступно')
                self.strategy_description.setText(description)
        
        except Exception as e:
            self.logger.error(f"Ошибка выбора стратегии: {e}")
    
    def _configure_strategy(self):
        """
        Настройка стратегии
        """
        try:
            current_row = self.strategies_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "Настройка", "Выберите стратегию для настройки")
                return
            
            strategy_name = self.strategies_table.item(current_row, 0).text()
            
            dialog = StrategyConfigDialog(strategy_name, self)
            if dialog.exec() == QDialog.Accepted:
                config = dialog.get_config()
                QMessageBox.information(self, "Настройка", f"Стратегия '{strategy_name}' настроена")
        
        except Exception as e:
            self.logger.error(f"Ошибка настройки стратегии: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка настройки стратегии: {e}")
    
    def _start_strategy(self):
        """
        Запуск стратегии
        """
        try:
            current_row = self.strategies_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "Запуск", "Выберите стратегию для запуска")
                return

            strategy_name = self.strategies_table.item(current_row, 0).text()
            
            # Проверяем, не запущена ли уже эта стратегия
            if strategy_name in self.active_strategies:
                QMessageBox.information(self, "Запуск", f"Стратегия '{strategy_name}' уже активна")
                return

            # Диалог настройки
            dialog = StrategyConfigDialog(strategy_name, self)
            if dialog.exec() != QDialog.Accepted:
                return

            config = dialog.get_config()
            
            # Автоматический выбор актива если включен
            if config.get('auto_asset_selection', True):
                selected_asset = self._select_best_asset_for_strategy(strategy_name)
                if selected_asset:
                    config['asset'] = selected_asset
                    self.logger.info(f"Автоматически выбран актив {selected_asset} для стратегии {strategy_name}")
                else:
                    QMessageBox.warning(self, "Предупреждение", "Не удалось автоматически выбрать актив. Используется актив по умолчанию.")
            
            # Получаем ключ стратегии для создания экземпляра
            strategy_info = self.available_strategies.get(strategy_name, {})
            strategy_key = strategy_info.get('strategy_key')
            
            if not strategy_key:
                QMessageBox.critical(self, "Ошибка", "Не удалось определить тип стратегии")
                return
            
            # Создаем уникальный ID для стратегии
            import uuid
            strategy_id = f"{strategy_key}_{uuid.uuid4().hex[:8]}"
            
            if self.strategy_engine:
                # Получаем класс стратегии
                strategy_class = get_strategy_class(strategy_key)
                if not strategy_class:
                    QMessageBox.critical(self, "Ошибка", f"Класс стратегии '{strategy_key}' не найден")
                    return
                
                # Создаем экземпляр стратегии
                try:
                    strategy_instance = strategy_class(
                        symbol=config.get('asset', 'BTCUSDT'),
                        api_client=self.api_client,
                        db_manager=self.db,
                        config=config
                    )
                    
                    # Регистрируем стратегию в движке
                    if self.strategy_engine.register_strategy(strategy_id, strategy_instance):
                        # Запускаем стратегию
                        if self.strategy_engine.start_strategy(strategy_id):
                            success = True
                        else:
                            success = False
                            self.strategy_engine.unregister_strategy(strategy_id)
                    else:
                        success = False
                        
                except Exception as e:
                    self.logger.error(f"Ошибка создания стратегии: {e}")
                    QMessageBox.critical(self, "Ошибка", f"Ошибка создания стратегии: {e}")
                    return
            else:
                # Демо-режим без реального API
                success = True
                self.logger.info(f"Стратегия '{strategy_name}' запущена в демо-режиме")
            
            if success:
                # Добавляем в активные стратегии
                from datetime import datetime
                self.active_strategies[strategy_id] = {
                    "name": strategy_name,
                    "config": config,
                    "status": "Активна",
                    "start_time": datetime.now(),
                    "pnl": 0.0,
                    "trades_count": 0
                }
                
                # Создаем окно стратегии через менеджер
                window = self.window_manager.create_strategy_window(strategy_name)
                window.show()
                
                # Добавляем начальные логи
                self.window_manager.add_log_to_strategy(strategy_name, f"[INFO] Стратегия '{strategy_name}' запущена")
                self.window_manager.add_human_message_to_strategy(strategy_name, f"Стратегия '{strategy_name}' успешно активирована и начинает работу")
                
                # Обновляем таблицу активных стратегий
                self._update_active_strategies_table()
                
                self.logger.info(f"Стратегия '{strategy_name}' успешно запущена с ID: {strategy_id}")
                QMessageBox.information(self, "Запуск", f"Стратегия '{strategy_name}' успешно запущена")
            else:
                QMessageBox.critical(self, "Ошибка", f"Не удалось запустить стратегию '{strategy_name}'")
        
        except Exception as e:
            self.logger.error(f"Ошибка запуска стратегии: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка запуска стратегии: {e}")
    
    def _select_best_asset_for_strategy(self, strategy_name: str) -> Optional[str]:
        """
        Автоматический выбор лучшего актива для стратегии
        
        Args:
            strategy_name: Название стратегии
            
        Returns:
            Символ выбранного актива или None
        """
        try:
            if not self.api_client:
                self.logger.warning("API клиент недоступен для автоматического выбора активов")
                return None
            
            # Создаем AssetSelector
            asset_selector = AssetSelector(self.api_client, self.db, self.config)
            
            # Запускаем асинхронный выбор активов
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            try:
                # Выбираем лучший актив для данной стратегии
                best_assets = loop.run_until_complete(
                    asset_selector.select_best_assets(strategy_type=strategy_name, count=1)
                )
                
                if best_assets:
                    return best_assets[0]
                else:
                    return None
                    
            finally:
                loop.close()
                
        except Exception as e:
            self.logger.error(f"Ошибка автоматического выбора актива: {e}")
            return None
    
    def _update_active_strategies_table(self):
        """
        Обновление таблицы активных стратегий
        """
        try:
            self.active_table.setRowCount(len(self.active_strategies))
            
            for row, (strategy_id, info) in enumerate(self.active_strategies.items()):
                # Название стратегии
                strategy_name = info.get('name', strategy_id)
                self.active_table.setItem(row, 0, QTableWidgetItem(strategy_name))
                
                # Актив
                asset = info['config'].get('asset', 'N/A')
                self.active_table.setItem(row, 1, QTableWidgetItem(asset))
                
                # Статус
                status = info['status']
                status_item = QTableWidgetItem(status)
                status_colors = {
                    "Активна": Qt.green, "RUNNING": Qt.green,
                    "На паузе": QColor(255, 165, 0), "PAUSED": QColor(255, 165, 0),
                    "Остановлена": Qt.red, "STOPPED": Qt.red, "ERROR": Qt.red,
                    "UNKNOWN": Qt.gray
                }
                if status in status_colors:
                    status_item.setForeground(status_colors[status])
                self.active_table.setItem(row, 2, status_item)
                
                # P&L
                pnl = info.get('pnl', 0.0)
                pnl_item = QTableWidgetItem(f"${pnl:+.2f}")
                pnl_color = "green" if pnl >= 0 else "red"
                pnl_item.setForeground(Qt.GlobalColor.__dict__[pnl_color])
                self.active_table.setItem(row, 3, pnl_item)
                
                # Время работы
                from datetime import datetime
                runtime = datetime.now() - info['start_time']
                runtime_str = str(runtime).split('.')[0]  # Убираем микросекунды
                self.active_table.setItem(row, 4, QTableWidgetItem(runtime_str))
                
                # Сохраняем ID стратегии в данных строки для последующего использования
                self.active_table.item(row, 0).setData(Qt.UserRole, strategy_id)
        
        except Exception as e:
            self.logger.error(f"Ошибка обновления таблицы активных стратегий: {e}")
    
    def _show_strategy_window(self):
        """
        Показать окно стратегии
        """
        try:
            current_row = self.active_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "Окно стратегии", "Выберите активную стратегию")
                return
            
            # Получаем название стратегии из таблицы
            strategy_name = self.active_table.item(current_row, 0).text()
            
            # Создаем или показываем окно стратегии через менеджер
            window = self.window_manager.create_strategy_window(strategy_name)
            window.show()
            window.raise_()
            window.activateWindow()
            
            # Добавляем тестовые логи
            self.window_manager.add_log_to_strategy(strategy_name, "[INFO] Окно стратегии открыто")
            self.window_manager.add_human_message_to_strategy(strategy_name, "Окно мониторинга стратегии активировано")
        
        except Exception as e:
            self.logger.error(f"Ошибка показа окна стратегии: {e}")
    
    def _pause_strategy(self):
        """
        Пауза стратегии
        """
        try:
            current_row = self.active_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "Пауза стратегии", "Выберите активную стратегию")
                return
            
            # Получаем ID стратегии из данных строки
            strategy_id = self.active_table.item(current_row, 0).data(Qt.UserRole)
            strategy_name = self.active_table.item(current_row, 0).text()
            
            if strategy_id in self.active_strategies:
                current_status = self.active_strategies[strategy_id]['status']
                
                if hasattr(self, 'strategy_engine') and self.strategy_engine:
                    # Используем StrategyEngine для управления стратегией
                    if current_status in ["Активна", "RUNNING"]:
                        success = self.strategy_engine.pause_strategy(strategy_id)
                        if success:
                            self.active_strategies[strategy_id]['status'] = "PAUSED"
                            QMessageBox.information(self, "Пауза стратегии", f"Стратегия '{strategy_name}' приостановлена")
                        else:
                            QMessageBox.warning(self, "Ошибка", "Не удалось приостановить стратегию")
                    elif current_status in ["На паузе", "PAUSED"]:
                        success = self.strategy_engine.resume_strategy(strategy_id)
                        if success:
                            self.active_strategies[strategy_id]['status'] = "RUNNING"
                            QMessageBox.information(self, "Возобновление стратегии", f"Стратегия '{strategy_name}' возобновлена")
                        else:
                            QMessageBox.warning(self, "Ошибка", "Не удалось возобновить стратегию")
                    else:
                        QMessageBox.warning(self, "Ошибка", "Нельзя приостановить остановленную стратегию")
                else:
                    # Демо режим - просто меняем статус
                    if current_status in ["Активна", "RUNNING"]:
                        self.active_strategies[strategy_id]['status'] = "На паузе"
                        QMessageBox.information(self, "Пауза стратегии", f"Стратегия '{strategy_name}' приостановлена (демо)")
                    elif current_status in ["На паузе", "PAUSED"]:
                        self.active_strategies[strategy_id]['status'] = "Активна"
                        QMessageBox.information(self, "Возобновление стратегии", f"Стратегия '{strategy_name}' возобновлена (демо)")
                    else:
                        QMessageBox.warning(self, "Ошибка", "Нельзя приостановить остановленную стратегию")
                
                self._update_active_strategies_table()
            else:
                QMessageBox.warning(self, "Ошибка", "Стратегия не найдена")
        
        except Exception as e:
            self.logger.error(f"Ошибка паузы стратегии: {e}")
    
    def _stop_strategy(self):
        """
        Остановка выбранной стратегии
        """
        try:
            current_row = self.active_table.currentRow()
            if current_row < 0:
                QMessageBox.information(self, "Остановка", "Выберите стратегию для остановки")
                return
            
            # Получаем ID стратегии из данных строки
            strategy_id = self.active_table.item(current_row, 0).data(Qt.UserRole)
            strategy_name = self.active_table.item(current_row, 0).text()
            
            reply = QMessageBox.question(
                self, "Остановка стратегии",
                f"Вы уверены, что хотите остановить стратегию '{strategy_name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Останавливаем стратегию через движок
                if hasattr(self, 'strategy_engine') and self.strategy_engine:
                    success = self.strategy_engine.stop_strategy(strategy_id)
                    if success:
                        self.strategy_engine.unregister_strategy(strategy_id)
                    else:
                        QMessageBox.warning(self, "Ошибка", "Не удалось остановить стратегию")
                        return
                
                # Удаляем из активных стратегий
                if strategy_id in self.active_strategies:
                    del self.active_strategies[strategy_id]
                
                # Закрываем окно стратегии
                if strategy_id in self.strategy_windows:
                    self.strategy_windows[strategy_id].close()
                    del self.strategy_windows[strategy_id]
                
                self._update_active_strategies_table()
                self.logger.info(f"Стратегия '{strategy_name}' остановлена")
        
        except Exception as e:
            self.logger.error(f"Ошибка остановки стратегии: {e}")
    
    def _stop_all_strategies(self):
        """
        Остановка всех стратегий
        """
        try:
            if not self.active_strategies:
                QMessageBox.information(self, "Остановка", "Нет активных стратегий")
                return
            
            reply = QMessageBox.question(
                self, "Остановка всех стратегий",
                "Вы уверены, что хотите остановить ВСЕ активные стратегии?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Останавливаем все стратегии через движок
                if hasattr(self, 'strategy_engine') and self.strategy_engine:
                    for strategy_id in list(self.active_strategies.keys()):
                        self.strategy_engine.stop_strategy(strategy_id)
                        self.strategy_engine.unregister_strategy(strategy_id)
                
                # Закрываем все окна стратегий
                for window in self.strategy_windows.values():
                    window.close()
                
                # Очищаем все активные стратегии
                self.active_strategies.clear()
                self.strategy_windows.clear()
                
                self._update_active_strategies_table()
                self.logger.info("Все стратегии остановлены")
                QMessageBox.information(self, "Остановка", "Все стратегии остановлены")
        
        except Exception as e:
            self.logger.error(f"Ошибка остановки всех стратегий: {e}")
    
    def _emergency_stop(self):
        """
        Экстренная остановка всех стратегий
        """
        try:
            reply = QMessageBox.critical(
                self, "ЭКСТРЕННАЯ ОСТАНОВКА",
                "ВНИМАНИЕ! Это экстренная остановка всех торговых операций.\n\n"
                "Все активные стратегии будут немедленно остановлены,\n"
                "все открытые позиции будут закрыты по рыночной цене.\n\n"
                "Продолжить?",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Экстренная остановка всех стратегий через движок
                if hasattr(self, 'strategy_engine') and self.strategy_engine:
                    self.strategy_engine.emergency_stop()
                
                # Экстренная остановка всех стратегий
                for window in self.strategy_windows.values():
                    window.close()
                
                self.active_strategies.clear()
                self.strategy_windows.clear()
                self._update_active_strategies_table()
                
                self.logger.critical("ЭКСТРЕННАЯ ОСТАНОВКА: Все стратегии остановлены")
                QMessageBox.information(self, "Экстренная остановка", "Все стратегии экстренно остановлены")
        
        except Exception as e:
            self.logger.error(f"Ошибка экстренной остановки: {e}")
    
    def _export_report(self):
        """
        Экспорт отчета по стратегиям
        """
        try:
            QMessageBox.information(self, "Экспорт", "Функция экспорта отчета будет реализована")
        
        except Exception as e:
            self.logger.error(f"Ошибка экспорта отчета: {e}")
    
    def closeEvent(self, event):
        """
        Обработчик закрытия вкладки
        """
        try:
            # Останавливаем все стратегии через движок
            if hasattr(self, 'strategy_engine') and self.strategy_engine:
                for strategy_id in list(self.active_strategies.keys()):
                    self.strategy_engine.stop_strategy(strategy_id)
                    self.strategy_engine.unregister_strategy(strategy_id)
            
            # Закрываем все окна стратегий через менеджер
            self.window_manager.close_all_windows()
            
            # Останавливаем таймер обновления
            if hasattr(self, 'update_timer'):
                self.update_timer.stop()
            
            event.accept()
        
        except Exception as e:
            self.logger.error(f"Ошибка закрытия вкладки стратегий: {e}")
            event.accept()