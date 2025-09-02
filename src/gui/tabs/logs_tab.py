#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вкладка логов программы

Отображает технические логи и человеческие объяснения действий программы.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QTextEdit, QPlainTextEdit, QLabel, QComboBox, QPushButton,
    QCheckBox, QSpinBox, QGroupBox, QFormLayout,
    QSplitter, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor, QColor

from ...database.db_manager import DatabaseManager

class LogsWorker(QThread):
    """
    Воркер для получения логов из базы данных
    """
    logs_updated = Signal(list)  # Сигнал с новыми логами
    
    def __init__(self, db_manager: DatabaseManager):
        super().__init__()
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        self.running = True
        self.last_check = datetime.utcnow() - timedelta(hours=24)  # Последние 24 часа
        
    def run(self):
        """
        Основной цикл получения логов
        """
        while self.running:
            try:
                # Получаем новые логи из БД
                logs = self._get_recent_logs()
                if logs:
                    self.logs_updated.emit(logs)
                    
                self.msleep(1000)  # Проверяем каждую секунду
                
            except Exception as e:
                self.logger.error(f"Ошибка получения логов: {e}")
                self.msleep(5000)  # При ошибке ждем дольше
                
    def _get_recent_logs(self) -> List[Dict[str, Any]]:
        """
        Получение последних логов из базы данных
        """
        try:
            with self.db.get_session() as session:
                from ...database.db_manager import LogEntry
                
                # Получаем логи после последней проверки
                query = session.query(LogEntry).filter(
                    LogEntry.timestamp > self.last_check
                ).order_by(LogEntry.timestamp.desc()).limit(100)
                
                logs = []
                for entry in query:
                    logs.append({
                        'timestamp': entry.timestamp,
                        'level': entry.level,
                        'logger_name': entry.logger_name,
                        'module': entry.module or '',
                        'function': entry.function or '',
                        'message': entry.message,
                        'exception': entry.exception or ''
                    })
                
                if logs:
                    self.last_check = logs[0]['timestamp']
                    
                return logs
                
        except Exception as e:
            self.logger.error(f"Ошибка запроса логов: {e}")
            return []
            
    def stop(self):
        """
        Остановка воркера
        """
        self.running = False
        self.quit()
        self.wait()

class LogsTab(QWidget):
    """
    Вкладка логов программы
    """
    
    def __init__(self, config_manager, db_manager):
        super().__init__()
        
        self.config = config_manager
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        
        # Воркер для получения логов
        self.logs_worker = None
        
        # Инициализация UI
        self._init_ui()
        
        # Запуск воркера
        self._start_logs_worker()
        
        self.logger.info("Вкладка логов инициализирована")
    
    def update_database_reference(self, new_db_manager):
        """
        Обновление ссылки на базу данных при переключении режима
        
        Args:
            new_db_manager: Новый менеджер базы данных
        """
        try:
            # Останавливаем текущий воркер
            if self.logs_worker:
                self.logs_worker.stop()
                self.logs_worker = None
            
            # Обновляем ссылку на БД
            self.db = new_db_manager
            
            # Очищаем текущие логи
            self.technical_logs.clear()
            self.human_logs.clear()
            self.system_logs.clear()
            
            # Перезапускаем воркер с новой БД
            self._start_logs_worker()
            
            self.logger.info(f"База данных логов обновлена на {new_db_manager.get_environment()}")
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления БД в LogsTab: {e}")
        
    def _init_ui(self):
        """
        Инициализация пользовательского интерфейса
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Заголовок
        title_label = QLabel("Логи программы")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Панель управления
        self._create_control_panel(layout)
        
        # Создаем вкладки для разных типов логов
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Вкладка технических логов
        self._create_technical_logs_tab()
        
        # Вкладка человеческих объяснений
        self._create_human_logs_tab()
        
        # Вкладка системных логов
        self._create_system_logs_tab()
        
    def _create_control_panel(self, layout):
        """
        Создание панели управления логами
        """
        control_group = QGroupBox("Управление логами")
        control_layout = QHBoxLayout(control_group)
        
        # Фильтр по уровню
        level_label = QLabel("Уровень:")
        control_layout.addWidget(level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItems(["Все", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.setCurrentText("INFO")
        self.level_combo.currentTextChanged.connect(self._filter_logs)
        control_layout.addWidget(self.level_combo)
        
        control_layout.addSpacing(20)
        
        # Автопрокрутка
        self.auto_scroll_check = QCheckBox("Автопрокрутка")
        self.auto_scroll_check.setChecked(True)
        control_layout.addWidget(self.auto_scroll_check)
        
        control_layout.addSpacing(20)
        
        # Максимальное количество строк
        max_lines_label = QLabel("Макс. строк:")
        control_layout.addWidget(max_lines_label)
        
        self.max_lines_spin = QSpinBox()
        self.max_lines_spin.setRange(100, 10000)
        self.max_lines_spin.setValue(1000)
        self.max_lines_spin.valueChanged.connect(self._update_max_lines)
        control_layout.addWidget(self.max_lines_spin)
        
        control_layout.addStretch()
        
        # Кнопки управления
        self.clear_button = QPushButton("Очистить")
        self.clear_button.clicked.connect(self._clear_logs)
        control_layout.addWidget(self.clear_button)
        
        self.export_button = QPushButton("Экспорт")
        self.export_button.clicked.connect(self._export_logs)
        control_layout.addWidget(self.export_button)
        
        layout.addWidget(control_group)
        
    def _create_technical_logs_tab(self):
        """
        Создание вкладки технических логов
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Описание
        desc_label = QLabel("Технические логи системы (DEBUG, INFO, WARNING, ERROR)")
        desc_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(desc_label)
        
        # Текстовое поле для технических логов
        self.technical_logs = QPlainTextEdit()
        self.technical_logs.setReadOnly(True)
        self.technical_logs.setMaximumBlockCount(1000)
        
        # Настройка шрифта для логов
        log_font = QFont("Consolas", 9)
        log_font.setStyleHint(QFont.Monospace)
        self.technical_logs.setFont(log_font)
        
        layout.addWidget(self.technical_logs)
        
        self.tab_widget.addTab(tab, "Технические логи")
        
    def _create_human_logs_tab(self):
        """
        Создание вкладки человеческих объяснений
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Описание
        desc_label = QLabel("Объяснения действий программы на человеческом языке")
        desc_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(desc_label)
        
        # Текстовое поле для человеческих объяснений
        self.human_logs = QTextEdit()
        self.human_logs.setReadOnly(True)
        
        layout.addWidget(self.human_logs)
        
        self.tab_widget.addTab(tab, "Человеческие объяснения")
        
    def _create_system_logs_tab(self):
        """
        Создание вкладки системных логов
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Описание
        desc_label = QLabel("Системные события и статистика")
        desc_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(desc_label)
        
        # Разделитель на две части
        splitter = QSplitter(Qt.Vertical)
        
        # Верхняя часть - системные логи
        self.system_logs = QPlainTextEdit()
        self.system_logs.setReadOnly(True)
        self.system_logs.setMaximumBlockCount(500)
        
        system_font = QFont("Consolas", 9)
        self.system_logs.setFont(system_font)
        
        splitter.addWidget(self.system_logs)
        
        # Нижняя часть - статистика
        stats_widget = QWidget()
        stats_layout = QFormLayout(stats_widget)
        
        self.total_logs_label = QLabel("0")
        self.errors_count_label = QLabel("0")
        self.warnings_count_label = QLabel("0")
        self.last_error_label = QLabel("Нет")
        
        stats_layout.addRow("Всего логов:", self.total_logs_label)
        stats_layout.addRow("Ошибок:", self.errors_count_label)
        stats_layout.addRow("Предупреждений:", self.warnings_count_label)
        stats_layout.addRow("Последняя ошибка:", self.last_error_label)
        
        splitter.addWidget(stats_widget)
        splitter.setSizes([300, 100])
        
        layout.addWidget(splitter)
        
        self.tab_widget.addTab(tab, "Системные логи")
        
    def _start_logs_worker(self):
        """
        Запуск воркера для получения логов
        """
        if self.logs_worker:
            self.logs_worker.stop()
            
        self.logs_worker = LogsWorker(self.db)
        self.logs_worker.logs_updated.connect(self._update_logs)
        self.logs_worker.start()
        
    def _update_logs(self, logs: List[Dict[str, Any]]):
        """
        Обновление отображения логов
        """
        for log_entry in reversed(logs):  # Показываем в хронологическом порядке
            self._add_log_entry(log_entry)
            
    def _add_log_entry(self, log_entry: Dict[str, Any]):
        """
        Добавление записи лога
        """
        timestamp = log_entry['timestamp'].strftime('%H:%M:%S')
        level = log_entry['level']
        message = log_entry['message']
        module = log_entry['module']
        
        # Фильтрация по уровню
        current_filter = self.level_combo.currentText()
        if current_filter != "Все" and level != current_filter:
            return
            
        # Форматирование для технических логов
        if level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            formatted_message = f"[{timestamp}] [{level}] {module}: {message}"
            self.technical_logs.appendPlainText(formatted_message)
            
            # Автопрокрутка
            if self.auto_scroll_check.isChecked():
                cursor = self.technical_logs.textCursor()
                cursor.movePosition(QTextCursor.End)
                self.technical_logs.setTextCursor(cursor)
                
        # Системные логи
        if level in ['ERROR', 'CRITICAL', 'WARNING']:
            system_message = f"[{timestamp}] {level}: {message}"
            self.system_logs.appendPlainText(system_message)
            
        # Человеческие объяснения (для определенных событий)
        human_message = self._generate_human_explanation(log_entry)
        if human_message:
            formatted_human = f"<p><b>{timestamp}</b>: {human_message}</p>"
            self.human_logs.append(formatted_human)
            
        # Обновление статистики
        self._update_statistics(log_entry)
        
    def _generate_human_explanation(self, log_entry: Dict[str, Any]) -> Optional[str]:
        """
        Генерация человеческого объяснения для лога
        """
        message = log_entry['message'].lower()
        level = log_entry['level']
        
        # Объяснения для разных типов событий
        if 'стратегия' in message and 'запущена' in message:
            return "🚀 Торговая стратегия была успешно запущена и начала анализ рынка"
        elif 'стратегия' in message and 'остановлена' in message:
            return "⏹️ Торговая стратегия была остановлена пользователем или системой"
        elif 'сделка' in message and 'открыта' in message:
            return "💰 Открыта новая торговая позиция на основе сигналов стратегии"
        elif 'сделка' in message and 'закрыта' in message:
            return "✅ Торговая позиция была закрыта, результат зафиксирован"
        elif 'api' in message and 'ошибка' in message:
            return "⚠️ Возникла проблема с подключением к бирже, проверьте интернет и API ключи"
        elif level == 'ERROR':
            return f"❌ Произошла ошибка в системе: {log_entry['message']}"
        elif level == 'WARNING':
            return f"⚠️ Внимание: {log_entry['message']}"
        elif 'инициализирован' in message:
            return "✅ Компонент системы успешно загружен и готов к работе"
            
        return None
        
    def _update_statistics(self, log_entry: Dict[str, Any]):
        """
        Обновление статистики логов
        """
        # Здесь можно добавить подсчет статистики
        pass
        
    def _filter_logs(self):
        """
        Фильтрация логов по уровню
        """
        # Очищаем и перезагружаем логи с новым фильтром
        self.technical_logs.clear()
        self.system_logs.clear()
        self.human_logs.clear()
        
    def _update_max_lines(self):
        """
        Обновление максимального количества строк
        """
        max_lines = self.max_lines_spin.value()
        self.technical_logs.setMaximumBlockCount(max_lines)
        self.system_logs.setMaximumBlockCount(max_lines // 2)
        
    def _clear_logs(self):
        """
        Очистка всех логов
        """
        self.technical_logs.clear()
        self.human_logs.clear()
        self.system_logs.clear()
        
        # Сброс статистики
        self.total_logs_label.setText("0")
        self.errors_count_label.setText("0")
        self.warnings_count_label.setText("0")
        self.last_error_label.setText("Нет")
        
    def _export_logs(self):
        """
        Экспорт логов в файл
        """
        from PySide6.QtWidgets import QFileDialog
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Экспорт логов", "logs_export.txt", "Text files (*.txt)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("=== ТЕХНИЧЕСКИЕ ЛОГИ ===\n")
                    f.write(self.technical_logs.toPlainText())
                    f.write("\n\n=== ЧЕЛОВЕЧЕСКИЕ ОБЪЯСНЕНИЯ ===\n")
                    f.write(self.human_logs.toPlainText())
                    f.write("\n\n=== СИСТЕМНЫЕ ЛОГИ ===\n")
                    f.write(self.system_logs.toPlainText())
                    
                self.logger.info(f"Логи экспортированы в файл: {filename}")
                
            except Exception as e:
                self.logger.error(f"Ошибка экспорта логов: {e}")
                
    def closeEvent(self, event):
        """
        Обработка закрытия вкладки
        """
        if self.logs_worker:
            self.logs_worker.stop()
        event.accept()