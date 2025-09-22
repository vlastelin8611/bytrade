#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для запуска отдельного приложения просмотра тикеров Bybit
"""

import sys
import tkinter as tk
from pathlib import Path
import logging

# Импортируем TickerViewerApp из модуля ticker_viewer_gui
from src.tools.ticker_viewer_gui import TickerViewerApp
from src.utils.log_handler import TerminalLogHandler

def main():
    """Основная функция для запуска приложения тикеров"""
    # Инициализация логирования
    terminal_logger = TerminalLogHandler(log_dir='logs', filename_prefix='ticker_viewer_log')
    logging.getLogger().addHandler(terminal_logger)
    logging.getLogger().setLevel(logging.INFO)
    logging.info("Запуск программы просмотра тикеров")
    
    try:
        root = tk.Tk()
        app = TickerViewerApp(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        logging.info("Интерфейс программы просмотра тикеров инициализирован")
        root.mainloop()
    finally:
        # Закрываем логгер при завершении программы
        logging.info("Завершение программы просмотра тикеров")
        terminal_logger.close()

if __name__ == "__main__":
    main()