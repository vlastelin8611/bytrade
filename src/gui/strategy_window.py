from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTextEdit, QLabel, QSplitter, QPushButton, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont, QColor
from datetime import datetime
import logging

class StrategyWindow(QMainWindow):
    """Отдельное окно для мониторинга стратегии"""
    
    # Сигнал для закрытия окна
    window_closed = Signal(str)  # strategy_name
    
    def __init__(self, strategy_name, strategy_instance=None, parent=None):
        super().__init__(parent)
        self.strategy_name = strategy_name
        self.strategy_instance = strategy_instance
        self.is_running = False
        
        self.setWindowTitle(f"Стратегия: {strategy_name}")
        self.setGeometry(100, 100, 1000, 700)
        
        # Создаем центральный виджет
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QVBoxLayout(central_widget)
        
        # Заголовок
        self._create_header(main_layout)
        
        # Создаем сплиттер для разделения на две части
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Левая панель - детальные логи
        self._create_logs_panel(splitter)
        
        # Правая панель - человеческие объяснения
        self._create_human_panel(splitter)
        
        # Устанавливаем пропорции (60% логи, 40% объяснения)
        splitter.setSizes([600, 400])
        
        # Панель управления
        self._create_control_panel(main_layout)
        
        # Таймер для обновления данных
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_display)
        self.update_timer.start(1000)  # Обновление каждую секунду
        
    def _create_header(self, layout):
        """Создает заголовок окна"""
        header_frame = QFrame()
        header_frame.setFrameStyle(QFrame.StyledPanel)
        header_frame.setMaximumHeight(60)
        
        header_layout = QHBoxLayout(header_frame)
        
        # Название стратегии
        title_label = QLabel(f"Мониторинг стратегии: {self.strategy_name}")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        
        # Статус
        self.status_label = QLabel("Статус: Остановлена")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)
        
        layout.addWidget(header_frame)
        
    def _create_logs_panel(self, splitter):
        """Создает панель детальных логов"""
        logs_widget = QWidget()
        logs_layout = QVBoxLayout(logs_widget)
        
        # Заголовок панели логов
        logs_title = QLabel("Детальные логи стратегии")
        logs_title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        logs_layout.addWidget(logs_title)
        
        # Текстовое поле для логов
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setFont(QFont("Consolas", 9))
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #555;
            }
        """)
        logs_layout.addWidget(self.logs_text)
        
        splitter.addWidget(logs_widget)
        
    def _create_human_panel(self, splitter):
        """Создает панель человеческих объяснений"""
        human_widget = QWidget()
        human_layout = QVBoxLayout(human_widget)
        
        # Заголовок панели объяснений
        human_title = QLabel("Что делает бот (человеческим языком)")
        human_title.setStyleSheet("font-weight: bold; font-size: 12px; padding: 5px;")
        human_layout.addWidget(human_title)
        
        # Текстовое поле для объяснений
        self.human_text = QTextEdit()
        self.human_text.setReadOnly(True)
        self.human_text.setFont(QFont("Arial", 10))
        self.human_text.setStyleSheet("""
            QTextEdit {
                background-color: #f5f5f5;
                color: #333333;
                border: 1px solid #ccc;
                padding: 10px;
            }
        """)
        human_layout.addWidget(self.human_text)
        
        splitter.addWidget(human_widget)
        
    def _create_control_panel(self, layout):
        """Создает панель управления"""
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.StyledPanel)
        control_frame.setMaximumHeight(50)
        
        control_layout = QHBoxLayout(control_frame)
        
        # Кнопка старт/стоп
        self.start_stop_btn = QPushButton("Запустить")
        self.start_stop_btn.clicked.connect(self._toggle_strategy)
        self.start_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        # Кнопка очистки логов
        clear_btn = QPushButton("Очистить логи")
        clear_btn.clicked.connect(self._clear_logs)
        
        control_layout.addWidget(self.start_stop_btn)
        control_layout.addWidget(clear_btn)
        control_layout.addStretch()
        
        layout.addWidget(control_frame)
        
    def _toggle_strategy(self):
        """Переключает состояние стратегии"""
        if self.is_running:
            self._stop_strategy()
        else:
            self._start_strategy()
            
    def _start_strategy(self):
        """Запускает стратегию"""
        self.is_running = True
        self.status_label.setText("Статус: Активна")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")
        self.start_stop_btn.setText("Остановить")
        self.start_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """)
        
        self.add_human_message("🚀 Стратегия запущена! Начинаю анализ рынка...")
        self.add_log_message(f"[{datetime.now().strftime('%H:%M:%S')}] INFO: Strategy {self.strategy_name} started")
        
    def _stop_strategy(self):
        """Останавливает стратегию"""
        self.is_running = False
        self.status_label.setText("Статус: Остановлена")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        self.start_stop_btn.setText("Запустить")
        self.start_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        self.add_human_message("⏹️ Стратегия остановлена.")
        self.add_log_message(f"[{datetime.now().strftime('%H:%M:%S')}] INFO: Strategy {self.strategy_name} stopped")
        
    def _clear_logs(self):
        """Очищает логи"""
        self.logs_text.clear()
        self.human_text.clear()
        
    def _update_display(self):
        """Обновляет отображение данных"""
        if self.is_running and self.strategy_instance:
            # Здесь будет логика получения данных от стратегии
            pass
            
    def add_log_message(self, message):
        """Добавляет сообщение в панель логов"""
        self.logs_text.append(message)
        # Автопрокрутка вниз
        cursor = self.logs_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.logs_text.setTextCursor(cursor)
        
    def add_human_message(self, message):
        """Добавляет человеческое объяснение"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}"
        self.human_text.append(formatted_message)
        # Автопрокрутка вниз
        cursor = self.human_text.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.human_text.setTextCursor(cursor)
        
    def closeEvent(self, event):
        """Обработка закрытия окна"""
        if self.is_running:
            self._stop_strategy()
        self.window_closed.emit(self.strategy_name)
        event.accept()
        
    def get_strategy_status(self):
        """Возвращает текущий статус стратегии"""
        return {
            'name': self.strategy_name,
            'is_running': self.is_running,
            'window_open': True
        }