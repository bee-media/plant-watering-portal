"""
Модуль планировщика задач для автоматической отправки уведомлений
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
import asyncio
from database import Plant, SystemSettings, NotificationLog, User
from config import Config

logger = logging.getLogger(__name__)


class NotificationScheduler:
    """Класс для планирования уведомлений"""

    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone='Europe/Moscow')
        self.is_running = False

    def start(self):
        """Запустить планировщик"""
        if self.is_running:
            logger.warning("Планировщик уже запущен")
            return

        # Проверка уведомлений каждый час
        self.scheduler.add_job(
            self.check_and_send_notifications,
            CronTrigger(minute=0, timezone='Europe/Moscow'),
            id='check_notifications',
            name='Проверка и отправка уведомлений',
            replace_existing=True
        )

        # Проверка повторных уведомлений каждые 5 минут
        self.scheduler.add_job(
            self.check_retry_notifications,
            CronTrigger(minute='*/5', timezone='Europe/Moscow'),
            id='retry_notifications',
            name='Проверка повторных уведомлений',
            replace_existing=True
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("Планировщик уведомлений запущен")

    def stop(self):
        """Остановить планировщик"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Планировщик уведомлений остановлен")

    def _is_in_notification_window(self):
        """Проверить, находимся ли в разрешённом временном окне"""
        start_hour = int(SystemSettings.get('notification_start_hour', 8))
        end_hour = int(SystemSettings.get('notification_end_hour', 22))

        moscow_tz = pytz.timezone('Europe/Moscow')
        now = datetime.now(moscow_tz)
        current_hour = now.hour

        if current_hour < start_hour or current_hour >= end_hour:
            logger.info(f"Текущее время {current_hour}:00 вне диапазона уведомлений ({start_hour}:00 - {end_hour}:00)")
            return False, now
        return True, now

    def _get_moscow_time(self):
        """Получить текущее московское время"""
        moscow_tz = pytz.timezone('Europe/Moscow')
        return datetime.now(moscow_tz)

    def _send_notifications_sync(self, notifications_to_send):
        """Отправить все уведомления синхронно с новым ботом"""
        from telegram import Bot

        if not Config.TELEGRAM_BOT_TOKEN:
            logger.warning("Telegram бот не настроен")
            return

        users = User.get_users_for_notifications()
        if not users:
            logger.info("Нет пользователей для отправки уведомлений")
            return

        async def send_all():
            # Создаём новый экземпляр бота для этой сессии отправки
            bot = Bot(token=Config.TELEGRAM_BOT_TOKEN)

            async with bot:
                for notif in notifications_to_send:
                    plant = notif['plant']
                    attempt = notif['attempt']
                    log_id = notif['log_id']
                    notif_type = notif['type']

                    # Формируем сообщение
                    message = self._format_notification_message(plant, notif_type, attempt)

                    # Формируем кнопку
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    if notif_type == 'watering':
                        keyboard = [[InlineKeyboardButton("✅ Я полью", callback_data=f"water_{plant['id']}_{log_id}")]]
                    else:
                        keyboard = [[InlineKeyboardButton("✅ Я прикормлю", callback_data=f"fert_{plant['id']}_{log_id}")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    # Отправляем всем пользователям
                    for user in users:
                        try:
                            await bot.send_message(
                                chat_id=user['telegram_id'],
                                text=message,
                                reply_markup=reply_markup,
                                parse_mode='Markdown'
                            )
                            logger.info(f"Отправлено уведомление пользователю {user['name']}")
                        except Exception as e:
                            logger.error(f"Ошибка отправки уведомления пользователю {user['name']}: {e}")

                        # Небольшая задержка между отправками
                        await asyncio.sleep(0.1)

        # Запускаем в новом event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(send_all())
        finally:
            loop.close()

    def _format_notification_message(self, plant, notif_type, attempt):
        """Форматировать сообщение уведомления"""
        if attempt > 0:
            retry_message = SystemSettings.get(f'retry_message_{attempt}', '')
            if retry_message:
                if notif_type == 'fertilizer':
                    retry_message = retry_message.replace('полив', 'прикормк')
                    retry_message = retry_message.replace('Полейте', 'Прикормите')
                    retry_message = retry_message.replace('вод', 'удобрен')
                header = f"{retry_message}\n\n"
            else:
                action = "полива" if notif_type == 'watering' else "прикормки"
                header = f"⚠️ Напоминание #{attempt}: растение всё ещё ждёт {action}!\n\n"
        else:
            if notif_type == 'watering':
                header = "💧 **Время полить растение!**\n\n"
            else:
                header = "🌱 **Время прикормить растение!**\n\n"

        message = f"{header}🌿 Растение: **{plant['name']}**\n"

        if plant.get('location'):
            message += f"📍 Местоположение: {plant['location']}\n"

        if plant.get('description'):
            message += f"ℹ️ {plant['description']}\n"

        message += f"\n⏰ Дата уведомления: {self._get_moscow_time().strftime('%d.%m.%Y %H:%M')}"

        return message

    def check_and_send_notifications(self):
        """Проверить и отправить ПЕРВИЧНЫЕ уведомления"""
        try:
            logger.info("Запуск проверки уведомлений")

            in_window, now = self._is_in_notification_window()
            if not in_window:
                return

            moscow_tz = pytz.timezone('Europe/Moscow')
            notifications_to_send = []

            # === ПОЛИВ ===
            plants_to_water = Plant.get_plants_needing_water()
            logger.info(f"Найдено растений для полива: {len(plants_to_water)}")

            for plant in plants_to_water:
                logger.info(f"Проверка растения: {plant['name']} (ID: {plant['id']})")

                pending = NotificationLog.get_pending_for_plant(plant['id'], 'watering')

                today_sent = False
                if pending:
                    for notif in pending:
                        sent_at = notif['sent_at']
                        if isinstance(sent_at, str):
                            sent_at = datetime.strptime(sent_at, '%Y-%m-%d %H:%M:%S')
                        if sent_at.tzinfo is None:
                            sent_at = moscow_tz.localize(sent_at)

                        if sent_at.date() == now.date():
                            today_sent = True
                            logger.info(f"Уведомление для {plant['name']} уже отправлено сегодня")
                            break

                if not today_sent:
                    log_id = NotificationLog.create(plant['id'], 'watering')
                    logger.info(f"Создано уведомление ID: {log_id} для растения {plant['name']}")
                    notifications_to_send.append({
                        'type': 'watering',
                        'plant': plant,
                        'log_id': log_id,
                        'attempt': 0
                    })

            # === ПРИКОРМКА ===
            plants_to_fertilize = Plant.get_plants_needing_fertilizer()
            logger.info(f"Найдено растений для прикормки: {len(plants_to_fertilize)}")

            for plant in plants_to_fertilize:
                pending = NotificationLog.get_pending_for_plant(plant['id'], 'fertilizer')

                today_sent = False
                if pending:
                    for notif in pending:
                        sent_at = notif['sent_at']
                        if isinstance(sent_at, str):
                            sent_at = datetime.strptime(sent_at, '%Y-%m-%d %H:%M:%S')
                        if sent_at.tzinfo is None:
                            sent_at = moscow_tz.localize(sent_at)

                        if sent_at.date() == now.date():
                            today_sent = True
                            break

                if not today_sent:
                    log_id = NotificationLog.create(plant['id'], 'fertilizer')
                    notifications_to_send.append({
                        'type': 'fertilizer',
                        'plant': plant,
                        'log_id': log_id,
                        'attempt': 0
                    })

            # Отправляем все уведомления
            if notifications_to_send:
                logger.info(f"Отправка {len(notifications_to_send)} уведомлений...")
                self._send_notifications_sync(notifications_to_send)

            logger.info("Проверка уведомлений завершена")

        except Exception as e:
            logger.error(f"Ошибка при проверке уведомлений: {e}", exc_info=True)

    def check_retry_notifications(self):
        """Проверить и отправить ПОВТОРНЫЕ уведомления"""
        try:
            logger.info("Запуск проверки повторных уведомлений")

            in_window, now = self._is_in_notification_window()
            if not in_window:
                return

            retry_interval = int(SystemSettings.get('notification_retry_interval_minutes', 30))
            max_retries = int(SystemSettings.get('notification_max_retries', 5))

            moscow_tz = pytz.timezone('Europe/Moscow')
            notifications_to_send = []

            pending_notifications = NotificationLog.get_all_pending()
            logger.info(f"Найдено незавершённых уведомлений: {len(pending_notifications) if pending_notifications else 0}")

            for notification in (pending_notifications or []):
                if notification['attempt_number'] >= max_retries:
                    logger.info(f"Уведомление ID {notification['id']} достигло максимума попыток ({max_retries})")
                    continue

                last_attempt_at = notification.get('last_attempt_at') or notification['sent_at']
                if isinstance(last_attempt_at, str):
                    last_attempt_at = datetime.strptime(last_attempt_at, '%Y-%m-%d %H:%M:%S')
                if last_attempt_at.tzinfo is None:
                    last_attempt_at = moscow_tz.localize(last_attempt_at)

                time_diff = (now - last_attempt_at).total_seconds() / 60

                logger.info(f"Уведомление ID {notification['id']}: попытка {notification['attempt_number']}, "
                           f"прошло {time_diff:.1f} мин, интервал {retry_interval} мин")

                if time_diff >= retry_interval:
                    plant = Plant.get_by_id(notification['plant_id'])
                    if not plant:
                        logger.warning(f"Растение ID {notification['plant_id']} не найдено")
                        continue

                    NotificationLog.increment_attempt(notification['id'])
                    attempt_num = notification['attempt_number'] + 1

                    notifications_to_send.append({
                        'type': notification['notification_type'],
                        'plant': plant,
                        'log_id': notification['id'],
                        'attempt': attempt_num
                    })

            # Отправляем все уведомления
            if notifications_to_send:
                logger.info(f"Отправка {len(notifications_to_send)} повторных уведомлений...")
                self._send_notifications_sync(notifications_to_send)

            logger.info("Проверка повторных уведомлений завершена")

        except Exception as e:
            logger.error(f"Ошибка при проверке повторных уведомлений: {e}", exc_info=True)

    def trigger_immediate_check(self):
        """Запустить немедленную проверку уведомлений (для тестирования)"""
        logger.info("Запуск немедленной проверки уведомлений")
        self.check_and_send_notifications()


# Глобальный экземпляр планировщика
notification_scheduler = NotificationScheduler()