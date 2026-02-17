# 🤖 Запуск Telegram бота отдельно

## Проблема решена!

Telegram бот теперь запускается **отдельно** от Flask приложения, как в вашей рабочей версии.

---

## 🚀 Как запустить

### Вариант 1: В двух терминалах (для разработки)

**Терминал 1 - Flask приложение:**
```bash
python app.py
```

**Терминал 2 - Telegram бот:**
```bash
python run_bot.py
```

---

### Вариант 2: Windows - запуск двух bat файлов

Создайте два файла:

**start_app.bat:**
```batch
@echo off
cd /d %~dp0
call venv\Scripts\activate
python app.py
pause
```

**start_bot.bat:**
```batch
@echo off
cd /d %~dp0
call venv\Scripts\activate
python run_bot.py
pause
```

Запустите оба файла двойным кликом.

---

### Вариант 3: Linux - systemd сервисы (рекомендуется для production)

**1. Создайте сервис для Flask:**

```bash
sudo nano /etc/systemd/system/plant-portal.service
```

Вставьте:
```ini
[Unit]
Description=Plant Watering Portal
After=network.target mysql.service

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/plant_watering_portal
Environment="PATH=/path/to/plant_watering_portal/venv/bin"
ExecStart=/path/to/plant_watering_portal/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=append:/path/to/plant_watering_portal/logs/portal.log
StandardError=append:/path/to/plant_watering_portal/logs/portal_error.log

[Install]
WantedBy=multi-user.target
```

**2. Создайте сервис для Telegram бота:**

```bash
sudo nano /etc/systemd/system/plant-bot.service
```

Вставьте:
```ini
[Unit]
Description=Plant Watering Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/plant_watering_portal
Environment="PATH=/path/to/plant_watering_portal/venv/bin"
ExecStart=/path/to/plant_watering_portal/venv/bin/python run_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/path/to/plant_watering_portal/logs/bot.log
StandardError=append:/path/to/plant_watering_portal/logs/bot_error.log

[Install]
WantedBy=multi-user.target
```

**3. Создайте директорию для логов:**
```bash
mkdir -p logs
```

**4. Включите и запустите сервисы:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable plant-portal plant-bot
sudo systemctl start plant-portal plant-bot
```

**5. Проверьте статус:**
```bash
sudo systemctl status plant-portal
sudo systemctl status plant-bot
```

**6. Просмотр логов:**
```bash
# Логи портала
sudo journalctl -u plant-portal -f

# Логи бота
sudo journalctl -u plant-bot -f

# Или файловые логи
tail -f logs/portal.log
tail -f logs/bot.log
```

---

## 📝 Важные замечания

### ⚠️ Что изменилось

1. **Бот НЕ запускается** из `app.py` автоматически
2. **Нужно запустить ДВА процесса** вместо одного
3. **Это правильный способ** - так работало в вашей рабочей версии

### ✅ Преимущества отдельного запуска

- ✅ Нет конфликтов с asyncio event loop
- ✅ Бот работает стабильно
- ✅ Можно перезапускать портал независимо от бота
- ✅ Проще отлаживать проблемы
- ✅ Лучше для production

### 🔧 Отладка

**Если бот не получает callback:**

1. Убедитесь что `run_bot.py` запущен:
   ```bash
   # Должно быть 2 процесса Python
   ps aux | grep python
   ```

2. Проверьте логи бота:
   ```bash
   tail -f telegram_bot.log
   ```

3. В логах должно быть:
   ```
   INFO - Application started
   INFO - Creating button with callback_data: detail_14
   INFO - Received callback query: detail_14  # <-- ЭТО ВАЖНО
   ```

---

## 🎯 Быстрый старт (Windows)

```bash
# Терминал 1
python app.py

# Терминал 2 (НОВЫЙ терминал)
python run_bot.py
```

**Теперь попробуйте команду `/plants` в боте - кнопки должны работать!** 🎉
