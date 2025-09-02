# 📋 Команды запуска для всех случаев

## Windows

### PowerShell / Command Prompt
```powershell
# Основной запуск
python main.py

# Если Python не найден
py main.py

# Или с полным путем
C:\Python39\python.exe main.py

# Запуск с логированием
python main.py > app.log 2>&1

# Запуск в фоновом режиме
start /B python main.py
```

### Через проводник Windows
1. Откройте папку проекта
2. Shift + Правый клик → "Открыть окно PowerShell здесь"
3. Введите: `python main.py`

## Linux / macOS

```bash
# Основной запуск
python3 main.py

# Или
./main.py  # (если есть shebang)

# С виртуальным окружением
source venv/bin/activate
python main.py

# Запуск в фоне
nohup python3 main.py &

# С логированием
python3 main.py 2>&1 | tee app.log
```

## Альтернативные способы

### Через модуль
```bash
# Из корневой папки
python -m src.gui.main_window

# Или
python -c "from src.gui.main_window import main; main()"
```

### Прямой запуск файлов
```bash
# Главное окно
python src/gui/main_window.py

# Тесты
python test_strategies_integration.py
python api_integration_test.py
```

## Запуск с параметрами

```bash
# Режим отладки
python main.py --debug

# Тестовый режим
python main.py --testnet

# Конфигурационный файл
python main.py --config config/custom.json

# Без GUI (консольный режим)
python console_test.py
```

## Автоматический запуск

### Windows (bat файл)
Создайте `start_bot.bat`:
```batch
@echo off
cd /d "C:\path\to\crypto"
python main.py
pause
```

### Linux (shell скрипт)
Создайте `start_bot.sh`:
```bash
#!/bin/bash
cd /path/to/crypto
python3 main.py
```

### Планировщик задач Windows
1. Win + R → `taskschd.msc`
2. Создать задачу
3. Действие: `python.exe`
4. Аргументы: `main.py`
5. Рабочая папка: путь к проекту

## Решение проблем запуска

### Python не найден
```bash
# Проверить установку
python --version
py --version
python3 --version

# Найти Python
where python     # Windows
which python3    # Linux/macOS
```

### Модули не найдены
```bash
# Переустановить зависимости
pip install -r requirements.txt --force-reinstall

# Проверить установленные пакеты
pip list

# Обновить pip
python -m pip install --upgrade pip
```

### Права доступа (Linux/macOS)
```bash
# Сделать исполняемым
chmod +x main.py

# Или запустить с sudo (не рекомендуется)
sudo python3 main.py
```

### Проблемы с GUI
```bash
# Установить tkinter (если нужно)
sudo apt-get install python3-tk  # Ubuntu/Debian
brew install python-tk           # macOS

# Проверить дисплей (Linux)
echo $DISPLAY
export DISPLAY=:0
```

## Мониторинг работы

```bash
# Просмотр логов в реальном времени
tail -f strategy_test.log

# Проверка процессов
ps aux | grep python    # Linux/macOS
tasklist | findstr python  # Windows

# Остановка процесса
kill -9 <PID>          # Linux/macOS
taskkill /F /PID <PID> # Windows
```

## Быстрые команды

```bash
# Полная переустановка
pip uninstall -r requirements.txt -y
pip install -r requirements.txt

# Очистка кэша Python
find . -name "__pycache__" -exec rm -rf {} +  # Linux/macOS
for /d /r . %d in (__pycache__) do @if exist "%d" rd /s /q "%d"  # Windows

# Проверка синтаксиса
python -m py_compile main.py
```