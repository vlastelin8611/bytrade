from PySide6.QtCore import QObject, Signal
from .strategy_window import StrategyWindow
from typing import Dict, Optional

class StrategyWindowManager(QObject):
    """Менеджер для управления окнами стратегий"""
    
    # Сигналы
    strategy_started = Signal(str)  # strategy_name
    strategy_stopped = Signal(str)  # strategy_name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.strategy_windows: Dict[str, StrategyWindow] = {}
        
    def create_strategy_window(self, strategy_name: str, strategy_instance=None) -> StrategyWindow:
        """Создает новое окно для стратегии"""
        if strategy_name in self.strategy_windows:
            # Если окно уже существует, просто показываем его
            existing_window = self.strategy_windows[strategy_name]
            existing_window.show()
            existing_window.raise_()
            existing_window.activateWindow()
            return existing_window
            
        # Создаем новое окно
        window = StrategyWindow(strategy_name, strategy_instance)
        window.window_closed.connect(self._on_window_closed)
        
        # Сохраняем ссылку на окно
        self.strategy_windows[strategy_name] = window
        
        # Показываем окно
        window.show()
        
        return window
        
    def get_strategy_window(self, strategy_name: str) -> Optional[StrategyWindow]:
        """Возвращает окно стратегии по имени"""
        return self.strategy_windows.get(strategy_name)
        
    def close_strategy_window(self, strategy_name: str):
        """Закрывает окно стратегии"""
        if strategy_name in self.strategy_windows:
            window = self.strategy_windows[strategy_name]
            window.close()
            
    def close_all_windows(self):
        """Закрывает все окна стратегий"""
        for window in list(self.strategy_windows.values()):
            window.close()
            
    def get_active_strategies(self) -> Dict[str, dict]:
        """Возвращает информацию о всех активных стратегиях"""
        active_strategies = {}
        for name, window in self.strategy_windows.items():
            active_strategies[name] = window.get_strategy_status()
        return active_strategies
        
    def _on_window_closed(self, strategy_name: str):
        """Обработчик закрытия окна стратегии"""
        if strategy_name in self.strategy_windows:
            del self.strategy_windows[strategy_name]
            
    def add_log_to_strategy(self, strategy_name: str, message: str):
        """Добавляет лог-сообщение в окно стратегии"""
        if strategy_name in self.strategy_windows:
            self.strategy_windows[strategy_name].add_log_message(message)
            
    def add_human_message_to_strategy(self, strategy_name: str, message: str):
        """Добавляет человеческое объяснение в окно стратегии"""
        if strategy_name in self.strategy_windows:
            self.strategy_windows[strategy_name].add_human_message(message)
            
    def is_strategy_window_open(self, strategy_name: str) -> bool:
        """Проверяет, открыто ли окно стратегии"""
        return strategy_name in self.strategy_windows
        
    def get_window_count(self) -> int:
        """Возвращает количество открытых окон"""
        return len(self.strategy_windows)