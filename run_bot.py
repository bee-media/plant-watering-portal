#!/usr/bin/env python3
"""
Скрипт для запуска Telegram бота отдельно от основного приложения
Используйте этот скрипт если хотите запустить бота в отдельном процессе
"""
import logging
import asyncio
from telegram_bot import telegram_notifier

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Запуск Telegram бота"""
    if not telegram_notifier.bot_token:
        logger.error("Telegram бот токен не настроен!")
        logger.error("Пожалуйста, установите TELEGRAM_BOT_TOKEN в файле .env")
        return
    
    logger.info("Запуск Telegram бота...")
    try:
        telegram_notifier.run_bot()
    except KeyboardInterrupt:
        logger.info("Остановка Telegram бота...")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)


if __name__ == '__main__':
    main()
