"""
Модуль для работы с Telegram ботом для отправки уведомлений о поливе
"""
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes
import asyncio
from config import Config
from database import User, Plant, NotificationLog

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Класс для работы с Telegram уведомлениями"""
    
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.bot = None
        self.application = None
        
        if self.bot_token:
            self.bot = Bot(token=self.bot_token)
            self.application = Application.builder().token(self.bot_token).build()
            self._setup_handlers()
    
    def _setup_handlers(self):
        """Настройка обработчиков команд и callback'ов"""
        if not self.application:
            return
        
        # Обработчик команды /start
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        
        # Обработчик команды /plants - список растений
        self.application.add_handler(CommandHandler("plants", self.cmd_plants))
        
        # Обработчик команды /status - статус всех растений
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        
        # Обработчик команды /help - справка
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        
        # Обработчик кнопок полива
        self.application.add_handler(CallbackQueryHandler(self.handle_watering_callback, pattern=r'^water_'))
        self.application.add_handler(CallbackQueryHandler(self.handle_fertilizer_callback, pattern=r'^fert_'))
        
        # Обработчик кнопок для просмотра деталей растения
        self.application.add_handler(CallbackQueryHandler(self.handle_plant_detail_callback, pattern=r'^detail_'))
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        chat_id = update.effective_chat.id
        
        message = (
            "🌱 Добро пожаловать в систему управления поливом растений!\n\n"
            f"Ваш Telegram ID: `{chat_id}`\n\n"
            "Скопируйте этот ID и добавьте его в настройки своего профиля на портале, "
            "чтобы получать уведомления о поливе растений.\n\n"
            "📋 Доступные команды:\n"
            "/plants - Список всех растений\n"
            "/status - Статус растений (требуют полива)\n"
            "/help - Справка по командам"
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def cmd_plants(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /plants - показать список растений"""
        user_telegram_id = str(update.effective_user.id)
        
        # Проверяем, авторизован ли пользователь
        users = User.get_all()
        authorized = False
        for u in users:
            if u['telegram_id'] == user_telegram_id:
                authorized = True
                break
        
        if not authorized:
            await update.message.reply_text(
                "❌ Вы не авторизованы в системе.\n\n"
                "Добавьте ваш Telegram ID в профиль на портале для доступа к этой команде."
            )
            return
        
        # Получаем все растения
        plants = Plant.get_all()
        
        if not plants:
            await update.message.reply_text("🌱 В системе пока нет растений")
            return
        
        # Формируем сообщение со списком
        message = "🌿 **Список растений:**\n\n"
        
        for plant in plants:
            message += f"🌱 **{plant['name']}**\n"
            
            if plant['location']:
                message += f"📍 {plant['location']}\n"
            
            # Создаем кнопку для просмотра деталей
            keyboard = [[
                InlineKeyboardButton(
                    "📊 Подробнее", 
                    callback_data=f"detail_{plant['id']}"
                )
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            message = ""  # Очищаем для следующего растения
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /status - показать статус растений"""
        user_telegram_id = str(update.effective_user.id)
        
        # Проверяем, авторизован ли пользователь
        users = User.get_all()
        authorized = False
        for u in users:
            if u['telegram_id'] == user_telegram_id:
                authorized = True
                break
        
        if not authorized:
            await update.message.reply_text(
                "❌ Вы не авторизованы в системе.\n\n"
                "Добавьте ваш Telegram ID в профиль на портале для доступа к этой команде."
            )
            return
        
        # Получаем все растения
        plants = Plant.get_all()
        
        if not plants:
            await update.message.reply_text("🌱 В системе пока нет растений")
            return
        
        from datetime import datetime, timedelta
        today = datetime.now().date()
        
        # Разделяем растения на категории
        need_water = []
        need_fertilizer = []
        ok_plants = []
        
        for plant in plants:
            needs_water = plant['next_watering_date'] and plant['next_watering_date'] <= today
            needs_fert = (plant['fertilizer_interval_days'] and 
                         plant['next_fertilizer_date'] and 
                         plant['next_fertilizer_date'] <= today)
            
            if needs_water:
                need_water.append(plant)
            elif needs_fert:
                need_fertilizer.append(plant)
            else:
                ok_plants.append(plant)
        
        # Формируем сообщение
        message = "📊 **Статус растений**\n\n"
        
        if need_water:
            message += "💧 **Требуют полива:**\n"
            for plant in need_water:
                days_overdue = (today - plant['next_watering_date']).days if plant['next_watering_date'] else 0
                if days_overdue > 0:
                    message += f"  🔴 {plant['name']} (просрочено {days_overdue} дн.)\n"
                else:
                    message += f"  ⚠️ {plant['name']} (сегодня)\n"
            message += "\n"
        
        if need_fertilizer:
            message += "🌱 **Требуют прикормки:**\n"
            for plant in need_fertilizer:
                days_overdue = (today - plant['next_fertilizer_date']).days if plant['next_fertilizer_date'] else 0
                if days_overdue > 0:
                    message += f"  🟡 {plant['name']} (просрочено {days_overdue} дн.)\n"
                else:
                    message += f"  ⚠️ {plant['name']} (сегодня)\n"
            message += "\n"
        
        if ok_plants:
            message += "✅ **В порядке:**\n"
            for plant in ok_plants:
                if plant['next_watering_date']:
                    days_left = (plant['next_watering_date'] - today).days
                    message += f"  🟢 {plant['name']} (полив через {days_left} дн.)\n"
                else:
                    message += f"  🟢 {plant['name']}\n"
        
        if not need_water and not need_fertilizer:
            message += "\n🎉 Все растения в порядке!"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help - справка"""
        message = (
            "🌱 **Справка по командам**\n\n"
            "📋 **Доступные команды:**\n\n"
            "/start - Получить ваш Telegram ID\n"
            "/plants - Показать список всех растений\n"
            "/status - Показать статус растений (какие требуют ухода)\n"
            "/help - Показать эту справку\n\n"
            "💡 **Как это работает:**\n"
            "• Система автоматически отправит уведомление, когда растение нужно полить\n"
            "• Нажмите кнопку '✅ Я полью' после полива\n"
            "• Другие пользователи получат уведомление о выполненном поливе\n"
            "• Используйте /plants для просмотра всех растений\n"
            "• Используйте /status для проверки текущего состояния\n\n"
            "❓ Вопросы? Обратитесь к администратору системы."
        )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def handle_plant_detail_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки просмотра деталей растения"""
        query = update.callback_query
        await query.answer()
        
        # Парсим ID растения
        plant_id = int(query.data.split('_')[1])
        
        # Получаем растение
        plant = Plant.get_by_id(plant_id)
        if not plant:
            await query.edit_message_text("❌ Растение не найдено")
            return
        
        # Получаем историю
        from database import WateringHistory
        history = WateringHistory.get_by_plant(plant_id, limit=5)
        
        from datetime import datetime
        today = datetime.now().date()
        
        # Формируем детальное сообщение
        message = f"🌿 **{plant['name']}**\n\n"
        
        if plant['description']:
            message += f"ℹ️ {plant['description']}\n\n"
        
        if plant['location']:
            message += f"📍 Местоположение: {plant['location']}\n"
        
        message += f"💧 Интервал полива: {plant['watering_interval_days']} дней\n"
        
        if plant['fertilizer_interval_days']:
            message += f"🌱 Интервал прикормки: {plant['fertilizer_interval_days']} дней\n"
        
        message += "\n"
        
        # Следующий полив
        if plant['next_watering_date']:
            days_until = (plant['next_watering_date'] - today).days
            if days_until < 0:
                message += f"💧 **Полив просрочен на {abs(days_until)} дн.**\n"
            elif days_until == 0:
                message += f"💧 **Полить сегодня**\n"
            else:
                message += f"💧 Следующий полив: через {days_until} дн. ({plant['next_watering_date'].strftime('%d.%m.%Y')})\n"
        
        # Следующая прикормка
        if plant['next_fertilizer_date']:
            days_until = (plant['next_fertilizer_date'] - today).days
            if days_until < 0:
                message += f"🌱 **Прикормка просрочена на {abs(days_until)} дн.**\n"
            elif days_until == 0:
                message += f"🌱 **Прикормить сегодня**\n"
            else:
                message += f"🌱 Следующая прикормка: через {days_until} дн. ({plant['next_fertilizer_date'].strftime('%d.%m.%Y')})\n"
        
        # История
        if history:
            message += "\n📜 **Последние действия:**\n"
            for entry in history[:3]:  # Показываем только 3 последних
                action_icon = "💧" if entry['action_type'] == 'watering' else "🌱"
                action_text = "полил(а)" if entry['action_type'] == 'watering' else "прикормил(а)"
                date_str = entry['watered_at'].strftime('%d.%m.%Y')
                message += f"{action_icon} {entry['user_name']} {action_text} ({date_str})\n"
        else:
            message += "\n📜 История пока пуста\n"
        
        await query.edit_message_text(message, parse_mode='Markdown')
    
    async def handle_watering_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатия кнопки полива"""
        query = update.callback_query
        await query.answer()
        
        # Парсим данные из callback
        data = query.data.split('_')
        if len(data) < 3:
            return
        
        plant_id = int(data[1])
        log_id = int(data[2])
        user_telegram_id = str(query.from_user.id)
        
        # Находим пользователя по Telegram ID
        users = User.get_all()
        user = None
        for u in users:
            if u['telegram_id'] == user_telegram_id:
                user = u
                break
        
        if not user:
            await query.edit_message_text(
                "❌ Пользователь не найден. Убедитесь, что ваш Telegram ID добавлен в профиль."
            )
            return
        
        # Получаем растение
        plant = Plant.get_by_id(plant_id)
        if not plant:
            await query.edit_message_text("❌ Растение не найдено.")
            return
        
        # Обновляем полив
        success = Plant.update_watering(plant_id, user['id'])
        
        if success:
            # Отмечаем уведомление как выполненное
            NotificationLog.mark_completed(log_id, user['id'])
            
            # Обновляем сообщение
            await query.edit_message_text(
                f"✅ {user['name']} полил(а) растение **{plant['name']}**\n"
                f"Дата: {self._get_moscow_time().strftime('%d.%m.%Y %H:%M')}",
                parse_mode='Markdown'
            )
            
            # Уведомляем других пользователей
            await self.notify_watering_completed(plant, user)
        else:
            await query.edit_message_text("❌ Ошибка при обновлении данных о поливе.")
    
    async def handle_fertilizer_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик нажатия кнопки прикормки"""
        query = update.callback_query
        await query.answer()
        
        # Парсим данные из callback
        data = query.data.split('_')
        if len(data) < 3:
            return
        
        plant_id = int(data[1])
        log_id = int(data[2])
        user_telegram_id = str(query.from_user.id)
        
        # Находим пользователя по Telegram ID
        users = User.get_all()
        user = None
        for u in users:
            if u['telegram_id'] == user_telegram_id:
                user = u
                break
        
        if not user:
            await query.edit_message_text(
                "❌ Пользователь не найден. Убедитесь, что ваш Telegram ID добавлен в профиль."
            )
            return
        
        # Получаем растение
        plant = Plant.get_by_id(plant_id)
        if not plant:
            await query.edit_message_text("❌ Растение не найдено.")
            return
        
        # Обновляем прикормку
        success = Plant.update_fertilizer(plant_id, user['id'])
        
        if success:
            # Отмечаем уведомление как выполненное
            NotificationLog.mark_completed(log_id, user['id'])
            
            # Обновляем сообщение
            await query.edit_message_text(
                f"✅ {user['name']} прикормил(а) растение **{plant['name']}**\n"
                f"Дата: {self._get_moscow_time().strftime('%d.%m.%Y %H:%M')}",
                parse_mode='Markdown'
            )
            
            # Уведомляем других пользователей
            await self.notify_fertilizer_completed(plant, user)
        else:
            await query.edit_message_text("❌ Ошибка при обновлении данных о прикормке.")
    
    def _get_moscow_time(self):
        """Получить текущее московское время"""
        from datetime import datetime
        import pytz
        moscow_tz = pytz.timezone('Europe/Moscow')
        return datetime.now(moscow_tz)
    
    async def send_watering_notification(self, plant, log_id):
        """Отправить уведомление о необходимости полива"""
        if not self.bot:
            logger.warning("Telegram бот не инициализирован")
            return
        
        users = User.get_users_for_notifications()
        
        if not users:
            logger.info("Нет пользователей для отправки уведомлений")
            return
        
        # Формируем сообщение
        message = (
            f"💧 **Время полить растение!**\n\n"
            f"🌿 Растение: **{plant['name']}**\n"
        )
        
        if plant['location']:
            message += f"📍 Местоположение: {plant['location']}\n"
        
        if plant['description']:
            message += f"ℹ️ {plant['description']}\n"
        
        message += f"\n⏰ Дата уведомления: {self._get_moscow_time().strftime('%d.%m.%Y %H:%M')}"
        
        # Создаем кнопку
        keyboard = [[InlineKeyboardButton("✅ Я полью", callback_data=f"water_{plant['id']}_{log_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем всем пользователям
        for user in users:
            try:
                await self.bot.send_message(
                    chat_id=user['telegram_id'],
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                logger.info(f"Отправлено уведомление о поливе пользователю {user['name']}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления пользователю {user['name']}: {e}")
    
    async def send_fertilizer_notification(self, plant, log_id):
        """Отправить уведомление о необходимости прикормки"""
        if not self.bot:
            logger.warning("Telegram бот не инициализирован")
            return
        
        users = User.get_users_for_notifications()
        
        if not users:
            logger.info("Нет пользователей для отправки уведомлений")
            return
        
        # Формируем сообщение
        message = (
            f"🌱 **Время прикормить растение!**\n\n"
            f"🌿 Растение: **{plant['name']}**\n"
        )
        
        if plant['location']:
            message += f"📍 Местоположение: {plant['location']}\n"
        
        if plant['description']:
            message += f"ℹ️ {plant['description']}\n"
        
        message += f"\n⏰ Дата уведомления: {self._get_moscow_time().strftime('%d.%m.%Y %H:%M')}"
        
        # Создаем кнопку
        keyboard = [[InlineKeyboardButton("✅ Я прикормлю", callback_data=f"fert_{plant['id']}_{log_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Отправляем всем пользователям
        for user in users:
            try:
                await self.bot.send_message(
                    chat_id=user['telegram_id'],
                    text=message,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                logger.info(f"Отправлено уведомление о прикормке пользователю {user['name']}")
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления пользователю {user['name']}: {e}")
    
    async def notify_watering_completed(self, plant, completed_by_user):
        """Уведомить других пользователей о выполненном поливе"""
        if not self.bot:
            return
        
        users = User.get_users_for_notifications()
        
        message = (
            f"ℹ️ **Информация о поливе**\n\n"
            f"👤 {completed_by_user['name']} полил(а) растение **{plant['name']}**\n"
            f"⏰ {self._get_moscow_time().strftime('%d.%m.%Y %H:%M')}"
        )
        
        for user in users:
            if user['id'] != completed_by_user['id']:  # Не отправляем тому, кто полил
                try:
                    await self.bot.send_message(
                        chat_id=user['telegram_id'],
                        text=message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user['name']}: {e}")
    
    async def notify_fertilizer_completed(self, plant, completed_by_user):
        """Уведомить других пользователей о выполненной прикормке"""
        if not self.bot:
            return
        
        users = User.get_users_for_notifications()
        
        message = (
            f"ℹ️ **Информация о прикормке**\n\n"
            f"👤 {completed_by_user['name']} прикормил(а) растение **{plant['name']}**\n"
            f"⏰ {self._get_moscow_time().strftime('%d.%m.%Y %H:%M')}"
        )
        
        for user in users:
            if user['id'] != completed_by_user['id']:  # Не отправляем тому, кто прикормил
                try:
                    await self.bot.send_message(
                        chat_id=user['telegram_id'],
                        text=message,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Ошибка отправки уведомления пользователю {user['name']}: {e}")
    
    def run_bot(self):
        """Запустить бота"""
        if self.application:
            self.application.run_polling()


# Глобальный экземпляр уведомителя
telegram_notifier = TelegramNotifier()
