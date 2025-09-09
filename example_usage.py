# Пример использования автоматической торговли с настройкой параметров

import sys
from PyQt5.QtWidgets import QApplication
from restore_interface import RestoreInterface
from config_manager import ConfigManager

def main():
    # Инициализация приложения
    app = QApplication(sys.argv)
    
    # Создание менеджера конфигурации
    config = ConfigManager('config.json')
    
    # Настройка API ключей для тестовой сети
    config.set('trading.testnet', True)  # Используем тестовую сеть для безопасности
    config.set_api_credentials('testnet', {
        'api_key': 'ваш_тестовый_api_ключ',
        'api_secret': 'ваш_тестовый_api_секрет'
    })
    
    # Настройка автозапуска стратегий
    config.set('strategies.auto_start', True)
    
    # Сохранение конфигурации
    config.save()
    
    # Создание и отображение главного окна
    main_window = RestoreInterface(config)
    main_window.show()
    
    # Добавление примера стратегии
    main_window.add_strategy()
    
    # Запуск приложения
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()