"""
Модуль планировщика задач для автоматической отправки уведомлений
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
import asyncio
from database import Plant, SystemSettings, NotificationLog
from telegram_bot import telegram_notifier

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
        
        # Проверка повторных уведомлений каждые 30 минут
        self.scheduler.add_job(
            self.check_retry_notifications,
            CronTrigger(minute='*/30', timezone='Europe/Moscow'),
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
    
    def check_and_send_notifications(self):
        """Проверить и отправить уведомления"""
        try:
            logger.info("Запуск проверки уведомлений")
            
            # Получаем настройки времени
            start_hour = int(SystemSettings.get('notification_start_hour', 8))
            end_hour = int(SystemSettings.get('notification_end_hour', 22))
            
            # Проверяем текущее время
            moscow_tz = pytz.timezone('Europe/Moscow')
            now = datetime.now(moscow_tz)
            current_hour = now.hour
            
            # Проверяем, попадаем ли в разрешенное время
            if current_hour < start_hour or current_hour >= end_hour:
                logger.info(f"Текущее время {current_hour}:00 вне диапазона уведомлений ({start_hour}:00 - {end_hour}:00)")
                return
            
            # Проверяем растения, требующие полива
            plants_to_water = Plant.get_plants_needing_water()
            for plant in plants_to_water:
                # Проверяем, есть ли уже активные уведомления
                pending = NotificationLog.get_pending_for_plant(plant['id'], 'watering')
                if not pending:
                    # Создаем новое уведомление
                    log_id = NotificationLog.create(plant['id'], 'watering')
                    # Отправляем уведомление
                    asyncio.run(telegram_notifier.send_watering_notification(plant, log_id))
                    logger.info(f"Отправлено уведомление о поливе для растения {plant['name']}")
            
            # Проверяем растения, требующие прикормки
            plants_to_fertilize = Plant.get_plants_needing_fertilizer()
            for plant in plants_to_fertilize:
                # Проверяем, есть ли уже активные уведомления
                pending = NotificationLog.get_pending_for_plant(plant['id'], 'fertilizer')
                if not pending:
                    # Создаем новое уведомление
                    log_id = NotificationLog.create(plant['id'], 'fertilizer')
                    # Отправляем уведомление
                    asyncio.run(telegram_notifier.send_fertilizer_notification(plant, log_id))
                    logger.info(f"Отправлено уведомление о прикормке для растения {plant['name']}")
            
            logger.info("Проверка уведомлений завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке уведомлений: {e}", exc_info=True)
    
    def check_retry_notifications(self):
        """Проверить и отправить повторные уведомления"""
        try:
            logger.info("Запуск проверки повторных уведомлений")
            
            # Получаем настройки
            start_hour = int(SystemSettings.get('notification_start_hour', 8))
            end_hour = int(SystemSettings.get('notification_end_hour', 22))
            retry_interval = int(SystemSettings.get('notification_retry_interval_minutes', 120))
            max_retries = int(SystemSettings.get('notification_max_retries', 3))
            
            # Проверяем текущее время
            moscow_tz = pytz.timezone('Europe/Moscow')
            now = datetime.now(moscow_tz)
            current_hour = now.hour
            
            # Проверяем, попадаем ли в разрешенное время
            if current_hour < start_hour or current_hour >= end_hour:
                logger.info(f"Текущее время {current_hour}:00 вне диапазона уведомлений ({start_hour}:00 - {end_hour}:00)")
                return
            
            # Получаем все активные растения
            plants = Plant.get_all()
            
            for plant in plants:
                # Проверяем незавершенные уведомления о поливе
                pending_water = NotificationLog.get_pending_for_plant(plant['id'], 'watering')
                for notification in pending_water:
                    if notification['attempt_number'] >= max_retries:
                        continue
                    
                    # Проверяем, прошло ли достаточно времени с последней попытки
                    sent_at = notification['sent_at']
                    if isinstance(sent_at, str):
                        sent_at = datetime.strptime(sent_at, '%Y-%m-%d %H:%M:%S')
                    
                    sent_at = moscow_tz.localize(sent_at) if sent_at.tzinfo is None else sent_at
                    time_diff = (now - sent_at).total_seconds() / 60  # в минутах
                    
                    if time_diff >= retry_interval:
                        # Увеличиваем счетчик попыток
                        NotificationLog.increment_attempt(notification['id'])
                        # Отправляем повторное уведомление
                        asyncio.run(telegram_notifier.send_watering_notification(plant, notification['id']))
                        logger.info(f"Отправлено повторное уведомление о поливе для растения {plant['name']} (попытка {notification['attempt_number'] + 1})")
                
                # Проверяем незавершенные уведомления о прикормке
                pending_fert = NotificationLog.get_pending_for_plant(plant['id'], 'fertilizer')
                for notification in pending_fert:
                    if notification['attempt_number'] >= max_retries:
                        continue
                    
                    # Проверяем, прошло ли достаточно времени с последней попытки
                    sent_at = notification['sent_at']
                    if isinstance(sent_at, str):
                        sent_at = datetime.strptime(sent_at, '%Y-%m-%d %H:%M:%S')
                    
                    sent_at = moscow_tz.localize(sent_at) if sent_at.tzinfo is None else sent_at
                    time_diff = (now - sent_at).total_seconds() / 60  # в минутах
                    
                    if time_diff >= retry_interval:
                        # Увеличиваем счетчик попыток
                        NotificationLog.increment_attempt(notification['id'])
                        # Отправляем повторное уведомление
                        asyncio.run(telegram_notifier.send_fertilizer_notification(plant, notification['id']))
                        logger.info(f"Отправлено повторное уведомление о прикормке для растения {plant['name']} (попытка {notification['attempt_number'] + 1})")
            
            logger.info("Проверка повторных уведомлений завершена")
            
        except Exception as e:
            logger.error(f"Ошибка при проверке повторных уведомлений: {e}", exc_info=True)
    
    def trigger_immediate_check(self):
        """Запустить немедленную проверку уведомлений (для тестирования)"""
        logger.info("Запуск немедленной проверки уведомлений")
        self.check_and_send_notifications()


# Глобальный экземпляр планировщика
notification_scheduler = NotificationScheduler()
