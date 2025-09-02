#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурационный менеджер для Bybit Trading Bot

Обеспечивает безопасное хранение и управление конфигурацией приложения,
включая API ключи, настройки торговли и параметры риск-менеджмента.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet
import keyring

class ConfigManager:
    """
    Менеджер конфигурации с шифрованием чувствительных данных
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        
        # Определяем директорию конфигурации
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = Path.home() / ".bybit_trading_bot"
        
        self.config_dir.mkdir(exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        
        # Инициализация шифрования
        self._init_encryption()
        
        # Загрузка конфигурации
        self.config = self._load_config()
        
        # Загрузка API ключей из файла keys.txt
        self._load_api_keys()
        
    def _init_encryption(self):
        """
        Инициализация системы шифрования для чувствительных данных
        """
        try:
            # Попытка получить ключ из keyring
            key = keyring.get_password("bybit_trading_bot", "encryption_key")
            
            if not key:
                # Генерируем новый ключ
                key = Fernet.generate_key().decode()
                keyring.set_password("bybit_trading_bot", "encryption_key", key)
                self.logger.info("Создан новый ключ шифрования")
            
            self.cipher = Fernet(key.encode())
            
        except Exception as e:
            self.logger.warning(f"Не удалось инициализировать шифрование: {e}")
            self.cipher = None
    
    def _encrypt_data(self, data: str) -> str:
        """
        Шифрование чувствительных данных
        """
        if self.cipher:
            try:
                return self.cipher.encrypt(data.encode()).decode()
            except Exception as e:
                self.logger.error(f"Ошибка шифрования: {e}")
        return data
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """
        Расшифровка чувствительных данных
        """
        if self.cipher:
            try:
                return self.cipher.decrypt(encrypted_data.encode()).decode()
            except Exception as e:
                self.logger.error(f"Ошибка расшифровки: {e}")
        return encrypted_data
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Загрузка конфигурации из файла
        """
        default_config = {
            "app": {
                "version": "1.0.0",
                "debug": False,
                "auto_save": True,
                "language": "ru"
            },
            "trading": {
                "testnet": True,
                "default_category": "linear",
                "max_daily_balance_usage": 0.20,  # 20%
                "max_stop_loss": 0.40,  # 40%
                "consecutive_loss_limit": 3,
                "pause_after_losses_days": 2,
                "position_size_auto": True
            },
            "risk_management": {
                "enabled": True,
                "max_positions": 10,
                "diversification_limit": 0.15,  # 15% на один актив
                "volatility_threshold": 0.05
            },
            "strategies": {
                "enabled_strategies": [],
                "adaptive_learning": True,
                "historical_data_days": 1095  # 3 года
            },
            "notifications": {
                "telegram_enabled": True,
                "email_enabled": False,
                "trade_notifications": True,
                "error_notifications": True
            },
            "database": {
                "path": str(self.config_dir / "trading_bot.db"),
                "backup_enabled": True,
                "backup_interval_hours": 24
            },
            "logging": {
                "level": "INFO",
                "file_enabled": True,
                "max_file_size_mb": 10,
                "backup_count": 5
            }
        }
        
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # Объединяем с дефолтной конфигурацией
                    self._merge_configs(default_config, loaded_config)
                    return default_config
            except Exception as e:
                self.logger.error(f"Ошибка загрузки конфигурации: {e}")
        
        # Сохраняем дефолтную конфигурацию
        self._save_config(default_config)
        return default_config
    
    def _merge_configs(self, default: Dict, loaded: Dict):
        """
        Рекурсивное объединение конфигураций
        """
        for key, value in loaded.items():
            if key in default:
                if isinstance(value, dict) and isinstance(default[key], dict):
                    self._merge_configs(default[key], value)
                else:
                    default[key] = value
            else:
                default[key] = value
    
    def _load_api_keys(self):
        """
        Загрузка API ключей из файла keys в корне проекта
        """
        keys_file = Path("keys")
        
        if not keys_file.exists():
            self.logger.warning("Файл keys не найден. Создаю шаблон.")
            self._create_keys_template()
            return
        
        try:
            with open(keys_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Проверяем, зашифрован ли файл
            if content.startswith('encrypted:'):
                try:
                    encrypted_content = content[10:]  # Убираем префикс 'encrypted:'
                    content = self._decrypt_data(encrypted_content)
                except Exception as e:
                    self.logger.error(f"Ошибка расшифровки файла keys: {e}")
                    return
            
            lines = content.split('\n')
            keys_data = {}
            
            for line in lines:
                line = line.strip()
                if line and '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    keys_data[key.strip()] = value.strip().strip('"\'')
            
            # Инициализируем структуру api_keys если её нет
            if 'api_keys' not in self.config:
                self.config['api_keys'] = {
                    "testnet": {},
                    "mainnet": {},
                    "telegram": {}
                }
            
            # Обновляем конфигурацию с ключами
            self.config['api_keys']['mainnet'].update({
                'api_key': keys_data.get('BYBIT_API_KEY', ''),
                'api_secret': keys_data.get('BYBIT_API_SECRET', '')
            })
            
            self.config['api_keys']['testnet'].update({
                'api_key': keys_data.get('BYBIT_TESTNET_API_KEY', ''),
                'api_secret': keys_data.get('BYBIT_TESTNET_API_SECRET', '')
            })
            
            self.config['api_keys']['telegram'].update({
                'bot_token': keys_data.get('TELEGRAM_BOT_TOKEN', ''),
                'chat_id': keys_data.get('TELEGRAM_CHAT_ID', '')
            })
            
            self.logger.info("API ключи загружены из файла keys")
            
        except Exception as e:
            self.logger.error(f"Ошибка загрузки файла keys: {e}")
    
    def _create_keys_template(self):
        """
        Создание шаблона файла keys
        """
        template = """# Файл с API ключами для Bybit Trading Bot
# ВАЖНО: Не делитесь этим файлом и не загружайте в публичные репозитории!

# Bybit API ключи для mainnet
BYBIT_API_KEY=your_mainnet_api_key_here
BYBIT_API_SECRET=your_mainnet_api_secret_here

# Bybit API ключи для testnet
BYBIT_TESTNET_API_KEY=your_testnet_api_key_here
BYBIT_TESTNET_API_SECRET=your_testnet_api_secret_here

# Telegram бот
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
"""
        
        try:
            with open("keys", 'w', encoding='utf-8') as f:
                f.write(template)
            self.logger.info("Создан шаблон файла keys")
        except Exception as e:
            self.logger.error(f"Ошибка создания файла keys: {e}")
    
    def _save_config(self, config: Dict[str, Any]):
        """
        Сохранение конфигурации в файл
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.logger.debug("Конфигурация сохранена")
        except Exception as e:
            self.logger.error(f"Ошибка сохранения конфигурации: {e}")
    
    def get(self, key_path: str, default=None):
        """
        Получение значения конфигурации по пути (например: 'trading.testnet')
        """
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any):
        """
        Установка значения конфигурации по пути
        """
        keys = key_path.split('.')
        config = self.config
        
        # Навигация до предпоследнего ключа
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # Установка значения
        config[keys[-1]] = value
        
        # Автосохранение если включено
        if self.get('app.auto_save', True):
            self.save()
    
    def save(self):
        """
        Сохранение текущей конфигурации
        """
        self._save_config(self.config)
    
    def set_value(self, key_path: str, value: Any):
        """
        Алиас для метода set для совместимости с GUI
        """
        self.set(key_path, value)
    
    def get_api_credentials(self, environment: str = 'testnet') -> Dict[str, str]:
        """
        Получение API учетных данных для указанной среды
        """
        api_keys = self.get('api_keys', {})
        return api_keys.get(environment, {})
    
    def get_telegram_config(self) -> Dict[str, str]:
        """
        Получение конфигурации Telegram бота
        """
        api_keys = self.get('api_keys', {})
        return api_keys.get('telegram', {})
    
    def set_api_credentials(self, environment: str, api_key: str, api_secret: str):
        """
        Установка API учетных данных для указанной среды
        """
        if 'api_keys' not in self.config:
            self.config['api_keys'] = {
                "testnet": {},
                "mainnet": {},
                "telegram": {}
            }
        
        self.config['api_keys'][environment] = {
            'api_key': api_key,
            'api_secret': api_secret
        }
        
        # Сохранение в файл keys
        self._save_api_keys_to_file()
        
        # Автосохранение конфигурации
        if self.get('app.auto_save', True):
            self.save()
    
    def set_testnet(self, testnet: bool):
        """
        Установка режима testnet
        """
        self.set('trading.testnet', testnet)
    
    def _save_api_keys_to_file(self):
        """
        Сохранение API ключей в файл keys
        """
        try:
            keys_file = Path("keys")
            api_keys = self.get('api_keys', {})
            
            content_lines = [
                "# Bybit API Keys",
                "# Mainnet keys",
                f"BYBIT_API_KEY={api_keys.get('mainnet', {}).get('api_key', 'your_mainnet_api_key_here')}",
                f"BYBIT_API_SECRET={api_keys.get('mainnet', {}).get('api_secret', 'your_mainnet_api_secret_here')}",
                "",
                "# Testnet keys", 
                f"BYBIT_TESTNET_API_KEY={api_keys.get('testnet', {}).get('api_key', 'your_testnet_api_key_here')}",
                f"BYBIT_TESTNET_API_SECRET={api_keys.get('testnet', {}).get('api_secret', 'your_testnet_api_secret_here')}",
                "",
                "# Telegram Bot",
                f"TELEGRAM_BOT_TOKEN={api_keys.get('telegram', {}).get('bot_token', 'your_telegram_bot_token_here')}",
                f"TELEGRAM_CHAT_ID={api_keys.get('telegram', {}).get('chat_id', 'your_telegram_chat_id_here')}"
            ]
            
            content = '\n'.join(content_lines)
            
            with open(keys_file, 'w', encoding='utf-8') as f:
                f.write(content)
                
            self.logger.info("API ключи сохранены в файл keys")
            
        except Exception as e:
            self.logger.error(f"Ошибка сохранения API ключей: {e}")
    
    def is_testnet(self) -> bool:
        """
        Проверка, используется ли testnet
        """
        return self.get('trading.testnet', True)
    
    def get_risk_limits(self) -> Dict[str, float]:
        """
        Получение настроек риск-менеджмента согласно новым требованиям
        """
        return {
            'max_daily_balance_usage': self.get('trading.max_daily_balance_usage', 0.20),  # 20% от баланса в день
            'max_consecutive_losses': self.get('trading.consecutive_loss_limit', 3),
            'consecutive_loss_pause_days': self.get('trading.pause_after_losses_days', 2),
            'max_stop_loss_percent': self.get('trading.max_stop_loss', 0.40),  # 40%
            'min_order_size': self.get('trading.min_order_size', 10.0),
            'max_order_size': self.get('trading.max_order_size', 1000.0)
        }
    
    def save_keys_encrypted(self):
        """
        Сохранение файла keys в зашифрованном виде
        """
        keys_file = Path("keys")
        
        if not keys_file.exists():
            self.logger.warning("Файл keys не найден для шифрования")
            return
        
        try:
            with open(keys_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            
            # Если уже зашифрован, пропускаем
            if content.startswith('encrypted:'):
                self.logger.info("Файл keys уже зашифрован")
                return
            
            # Шифруем содержимое
            encrypted_content = self._encrypt_data(content)
            
            # Сохраняем зашифрованный файл
            with open(keys_file, 'w', encoding='utf-8') as f:
                f.write(f"encrypted:{encrypted_content}")
            
            self.logger.info("Файл keys зашифрован")
            
        except Exception as e:
            self.logger.error(f"Ошибка шифрования файла keys: {e}")
    
    def validate_configuration(self) -> Dict[str, list]:
        """
        Валидация конфигурации согласно новым требованиям
        """
        errors = {
            'api_keys': [],
            'trading': [],
            'telegram': []
        }
        
        # Проверка API ключей
        environment = 'testnet' if self.is_testnet() else 'mainnet'
        bybit_config = self.get_api_credentials(environment)
        if not bybit_config.get('api_key') or not bybit_config.get('api_secret'):
            errors['api_keys'].append(f'Отсутствуют Bybit API ключи для {environment}')
        
        # Проверка Telegram
        telegram_config = self.get_telegram_config()
        if not telegram_config.get('bot_token') or not telegram_config.get('chat_id'):
            errors['telegram'].append('Отсутствуют данные Telegram бота')
        
        # Проверка торговых настроек
        risk_limits = self.get_risk_limits()
        if risk_limits['max_daily_balance_usage'] > 1.0 or risk_limits['max_daily_balance_usage'] <= 0:
            errors['trading'].append('Максимальное использование баланса должно быть от 0 до 1')
        
        if risk_limits['max_stop_loss_percent'] > 1.0 or risk_limits['max_stop_loss_percent'] <= 0:
            errors['trading'].append('Максимальный стоп-лосс должен быть от 0 до 1')
        
        return {k: v for k, v in errors.items() if v}
    
    def get_adaptive_strategy_config(self) -> Dict[str, Any]:
        """
        Получение конфигурации для адаптивной стратегии
        """
        return {
            'max_historical_days': self.get('strategies.historical_data_days', 1095),  # 3 года
            'min_historical_days': self.get('strategies.min_historical_days', 1),  # 1 день
            'learning_rate': self.get('strategies.learning_rate', 0.01),
            'confidence_threshold': self.get('strategies.confidence_threshold', 0.7),
            'rebalance_frequency': self.get('strategies.rebalance_frequency', 24),  # часы
            'risk_tolerance': self.get('strategies.risk_tolerance', 'medium')
        }
    
    def update_strategy_performance(self, strategy_name: str, performance_data: Dict[str, Any]):
        """
        Обновление данных о производительности стратегии
        """
        strategy_path = f'strategies.performance.{strategy_name}'
        current_data = self.get(strategy_path, {})
        current_data.update(performance_data)
        self.set(strategy_path, current_data)
        self.save()