import json
import os
import logging

class ConfigManager:
    """Класс для управления конфигурацией приложения"""
    
    def __init__(self, config_file):
        """Инициализация менеджера конфигурации
        
        Args:
            config_file (str): Путь к файлу конфигурации
        """
        self.config_file = config_file
        self.config = {}
        self.logger = logging.getLogger('ConfigManager')
        
        # Загрузка конфигурации
        self.load()
    
    def load(self):
        """Загрузка конфигурации из файла"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                self.logger.info(f"Конфигурация загружена из {self.config_file}")
            else:
                self.logger.warning(f"Файл конфигурации {self.config_file} не найден. Используются значения по умолчанию.")
                self.config = self._get_default_config()
        except Exception as e:
            self.logger.error(f"Ошибка загрузки конфигурации: {e}")
            self.config = self._get_default_config()
    
    def save(self):
        """Сохранение конфигурации в файл"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            self.logger.info(f"Конфигурация сохранена в {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Ошибка сохранения конфигурации: {e}")
            return False
    
    def get(self, key, default=None):
        """Получение значения по ключу
        
        Args:
            key (str): Ключ в формате 'section.subsection.parameter'
            default: Значение по умолчанию, если ключ не найден
        
        Returns:
            Значение параметра или default, если ключ не найден
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key, value):
        """Установка значения по ключу
        
        Args:
            key (str): Ключ в формате 'section.subsection.parameter'
            value: Значение для установки
        """
        keys = key.split('.')
        config = self.config
        
        for i, k in enumerate(keys[:-1]):
            if k not in config:
                config[k] = {}
            elif not isinstance(config[k], dict):
                config[k] = {}
            config = config[k]
        
        config[keys[-1]] = value
    
    def get_api_credentials(self, environment):
        """Получение API ключей для указанного окружения
        
        Args:
            environment (str): Окружение ('testnet' или 'mainnet')
        
        Returns:
            dict: Словарь с API ключами
        """
        return self.get(f'api.{environment}', {'api_key': '', 'api_secret': ''})
    
    def set_api_credentials(self, environment, credentials):
        """Установка API ключей для указанного окружения
        
        Args:
            environment (str): Окружение ('testnet' или 'mainnet')
            credentials (dict): Словарь с API ключами
        """
        self.set(f'api.{environment}', credentials)
    
    def _get_default_config(self):
        """Получение конфигурации по умолчанию
        
        Returns:
            dict: Конфигурация по умолчанию
        """
        return {
            'trading': {
                'testnet': True,
                'auto_save': True,
                'auto_save_interval': 300  # 5 минут
            },
            'api': {
                'testnet': {
                    'api_key': '',
                    'api_secret': ''
                },
                'mainnet': {
                    'api_key': '',
                    'api_secret': ''
                }
            },
            'strategies': {
                'auto_start': False
            },
            'ui': {
                'theme': 'light',
                'language': 'ru'
            }
        }