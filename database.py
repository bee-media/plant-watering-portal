"""
Модуль для работы с базой данных MySQL
"""
import pymysql
from pymysql.cursors import DictCursor
from contextlib import contextmanager
from config import Config
import logging

logger = logging.getLogger(__name__)


class Database:
    """Класс для работы с базой данных MySQL"""
    
    @staticmethod
    @contextmanager
    def get_connection():
        """Контекстный менеджер для получения соединения с БД"""
        connection = None
        try:
            connection = pymysql.connect(
                host=Config.DB_CONFIG['host'],
                port=Config.DB_CONFIG['port'],
                user=Config.DB_CONFIG['user'],
                password=Config.DB_CONFIG['password'],
                database=Config.DB_CONFIG['database'],
                charset=Config.DB_CONFIG['charset'],
                cursorclass=DictCursor
            )
            yield connection
        except pymysql.Error as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            raise
        finally:
            if connection:
                connection.close()
    
    @staticmethod
    @contextmanager
    def get_cursor(commit=False):
        """Контекстный менеджер для получения курсора БД"""
        with Database.get_connection() as connection:
            cursor = connection.cursor()
            try:
                yield cursor
                if commit:
                    connection.commit()
            except Exception as e:
                connection.rollback()
                logger.error(f"Ошибка выполнения запроса: {e}")
                raise
            finally:
                cursor.close()
    
    @staticmethod
    def execute_query(query, params=None, commit=False, fetch_one=False, fetch_all=False):
        """
        Выполнить SQL запрос
        
        Args:
            query: SQL запрос
            params: Параметры запроса
            commit: Выполнить коммит после запроса
            fetch_one: Получить одну запись
            fetch_all: Получить все записи
            
        Returns:
            Результат запроса или None
        """
        with Database.get_cursor(commit=commit) as cursor:
            cursor.execute(query, params or ())
            
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            elif commit:
                return cursor.lastrowid
            return None
    
    @staticmethod
    def execute_many(query, params_list):
        """
        Выполнить множественные вставки
        
        Args:
            query: SQL запрос
            params_list: Список параметров
            
        Returns:
            Количество затронутых строк
        """
        with Database.get_cursor(commit=True) as cursor:
            cursor.executemany(query, params_list)
            return cursor.rowcount


# Модели данных

class User:
    """Модель пользователя"""
    
    @staticmethod
    def get_by_id(user_id):
        """Получить пользователя по ID"""
        query = "SELECT * FROM users WHERE id = %s AND is_active = TRUE"
        return Database.execute_query(query, (user_id,), fetch_one=True)
    
    @staticmethod
    def get_by_username(username):
        """Получить пользователя по имени пользователя"""
        query = "SELECT * FROM users WHERE username = %s AND is_active = TRUE"
        return Database.execute_query(query, (username,), fetch_one=True)
    
    @staticmethod
    def get_all():
        """Получить всех активных пользователей"""
        query = "SELECT * FROM users WHERE is_active = TRUE ORDER BY name"
        return Database.execute_query(query, fetch_all=True)
    
    @staticmethod
    def create(name, username, password_hash, telegram_id=None, receive_notifications=True):
        """Создать нового пользователя"""
        query = """
            INSERT INTO users (name, username, password_hash, telegram_id, receive_notifications)
            VALUES (%s, %s, %s, %s, %s)
        """
        return Database.execute_query(
            query, 
            (name, username, password_hash, telegram_id, receive_notifications),
            commit=True
        )
    
    @staticmethod
    def update(user_id, name, username, telegram_id=None, receive_notifications=True):
        """Обновить данные пользователя"""
        query = """
            UPDATE users 
            SET name = %s, username = %s, telegram_id = %s, receive_notifications = %s
            WHERE id = %s
        """
        Database.execute_query(
            query,
            (name, username, telegram_id, receive_notifications, user_id),
            commit=True
        )
    
    @staticmethod
    def update_password(user_id, password_hash):
        """Обновить пароль пользователя"""
        query = "UPDATE users SET password_hash = %s WHERE id = %s"
        Database.execute_query(query, (password_hash, user_id), commit=True)
    
    @staticmethod
    def delete(user_id):
        """Удалить пользователя (мягкое удаление)"""
        query = "UPDATE users SET is_active = FALSE WHERE id = %s"
        Database.execute_query(query, (user_id,), commit=True)
    
    @staticmethod
    def get_users_for_notifications():
        """Получить пользователей для отправки уведомлений"""
        query = """
            SELECT * FROM users 
            WHERE is_active = TRUE 
            AND receive_notifications = TRUE 
            AND telegram_id IS NOT NULL 
            AND telegram_id != ''
        """
        return Database.execute_query(query, fetch_all=True)


class Plant:
    """Модель растения"""
    
    @staticmethod
    def get_by_id(plant_id):
        """Получить растение по ID"""
        query = "SELECT * FROM plants WHERE id = %s"
        return Database.execute_query(query, (plant_id,), fetch_one=True)
    
    @staticmethod
    def get_all(include_inactive=False):
        """Получить все растения"""
        query = "SELECT * FROM plants"
        if not include_inactive:
            query += " WHERE is_active = TRUE"
        query += " ORDER BY name"
        return Database.execute_query(query, fetch_all=True)
    
    @staticmethod
    def create(name, watering_interval_days, fertilizer_interval_days=None, 
               description=None, location=None, image_url=None):
        """Создать новое растение"""
        from datetime import datetime, timedelta
        
        now = datetime.now()
        next_watering = now + timedelta(days=watering_interval_days)
        next_fertilizer = None
        if fertilizer_interval_days:
            next_fertilizer = now + timedelta(days=fertilizer_interval_days)
        
        query = """
            INSERT INTO plants 
            (name, watering_interval_days, fertilizer_interval_days, description, 
             location, image_url, next_watering_date, next_fertilizer_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        return Database.execute_query(
            query,
            (name, watering_interval_days, fertilizer_interval_days, description,
             location, image_url, next_watering.date(), 
             next_fertilizer.date() if next_fertilizer else None),
            commit=True
        )
    
    @staticmethod
    def update(plant_id, name, watering_interval_days, fertilizer_interval_days=None,
               description=None, location=None, image_url=None):
        """Обновить данные растения"""
        query = """
            UPDATE plants 
            SET name = %s, watering_interval_days = %s, fertilizer_interval_days = %s,
                description = %s, location = %s, image_url = %s
            WHERE id = %s
        """
        Database.execute_query(
            query,
            (name, watering_interval_days, fertilizer_interval_days, description,
             location, image_url, plant_id),
            commit=True
        )
    
    @staticmethod
    def delete(plant_id):
        """Удалить растение (мягкое удаление)"""
        query = "UPDATE plants SET is_active = FALSE WHERE id = %s"
        Database.execute_query(query, (plant_id,), commit=True)
    
    @staticmethod
    def update_watering(plant_id, user_id):
        """Обновить данные о поливе"""
        from datetime import datetime, timedelta
        
        # Получаем растение
        plant = Plant.get_by_id(plant_id)
        if not plant:
            return False
        
        now = datetime.now()
        next_watering = now + timedelta(days=plant['watering_interval_days'])
        
        # Обновляем растение
        query = """
            UPDATE plants 
            SET last_watered_at = %s, next_watering_date = %s
            WHERE id = %s
        """
        Database.execute_query(query, (now, next_watering.date(), plant_id), commit=True)
        
        # Закрываем все активные уведомления о поливе для этого растения
        close_query = """
            UPDATE notification_log 
            SET is_completed = TRUE, completed_by_user_id = %s, completed_at = %s
            WHERE plant_id = %s AND notification_type = 'watering' AND is_completed = FALSE
        """
        Database.execute_query(close_query, (user_id, now, plant_id), commit=True)
        
        # Добавляем в историю
        WateringHistory.add(plant_id, user_id, 'watering')
        
        return True
    
    @staticmethod
    def update_fertilizer(plant_id, user_id):
        """Обновить данные о прикормке"""
        from datetime import datetime, timedelta
        
        # Получаем растение
        plant = Plant.get_by_id(plant_id)
        if not plant or not plant['fertilizer_interval_days']:
            return False
        
        now = datetime.now()
        next_fertilizer = now + timedelta(days=plant['fertilizer_interval_days'])
        
        # Обновляем растение
        query = """
            UPDATE plants 
            SET last_fertilized_at = %s, next_fertilizer_date = %s
            WHERE id = %s
        """
        Database.execute_query(query, (now, next_fertilizer.date(), plant_id), commit=True)
        
        # Закрываем все активные уведомления о прикормке для этого растения
        close_query = """
            UPDATE notification_log 
            SET is_completed = TRUE, completed_by_user_id = %s, completed_at = %s
            WHERE plant_id = %s AND notification_type = 'fertilizer' AND is_completed = FALSE
        """
        Database.execute_query(close_query, (user_id, now, plant_id), commit=True)
        
        # Добавляем в историю
        WateringHistory.add(plant_id, user_id, 'fertilizer')
        
        return True
    
    @staticmethod
    def get_plants_needing_water():
        """Получить растения, которые нужно полить сегодня"""
        from datetime import datetime
        today = datetime.now().date()
        
        query = """
            SELECT * FROM plants 
            WHERE is_active = TRUE 
            AND next_watering_date <= %s
            ORDER BY next_watering_date
        """
        return Database.execute_query(query, (today,), fetch_all=True)
    
    @staticmethod
    def get_plants_needing_fertilizer():
        """Получить растения, которые нужно прикормить сегодня"""
        from datetime import datetime
        today = datetime.now().date()
        
        query = """
            SELECT * FROM plants 
            WHERE is_active = TRUE 
            AND fertilizer_interval_days IS NOT NULL
            AND next_fertilizer_date <= %s
            ORDER BY next_fertilizer_date
        """
        return Database.execute_query(query, (today,), fetch_all=True)


class WateringHistory:
    """Модель истории полива"""
    
    @staticmethod
    def add(plant_id, user_id, action_type, notes=None):
        """Добавить запись в историю"""
        query = """
            INSERT INTO watering_history (plant_id, user_id, action_type, notes)
            VALUES (%s, %s, %s, %s)
        """
        return Database.execute_query(
            query,
            (plant_id, user_id, action_type, notes),
            commit=True
        )
    
    @staticmethod
    def get_by_plant(plant_id, limit=10):
        """Получить историю для растения"""
        query = """
            SELECT wh.*, u.name as user_name, p.name as plant_name
            FROM watering_history wh
            JOIN users u ON wh.user_id = u.id
            JOIN plants p ON wh.plant_id = p.id
            WHERE wh.plant_id = %s
            ORDER BY wh.watered_at DESC
            LIMIT %s
        """
        return Database.execute_query(query, (plant_id, limit), fetch_all=True)
    
    @staticmethod
    def get_recent(limit=20):
        """Получить последние записи истории"""
        query = """
            SELECT wh.*, u.name as user_name, p.name as plant_name
            FROM watering_history wh
            JOIN users u ON wh.user_id = u.id
            JOIN plants p ON wh.plant_id = p.id
            ORDER BY wh.watered_at DESC
            LIMIT %s
        """
        return Database.execute_query(query, (limit,), fetch_all=True)


class SystemSettings:
    """Модель настроек системы"""
    
    @staticmethod
    def get(key, default=None):
        """Получить значение настройки"""
        query = "SELECT setting_value FROM system_settings WHERE setting_key = %s"
        result = Database.execute_query(query, (key,), fetch_one=True)
        return result['setting_value'] if result else default
    
    @staticmethod
    def set(key, value):
        """Установить значение настройки"""
        query = """
            INSERT INTO system_settings (setting_key, setting_value)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE setting_value = %s
        """
        Database.execute_query(query, (key, value, value), commit=True)
    
    @staticmethod
    def get_all():
        """Получить все настройки"""
        query = "SELECT * FROM system_settings ORDER BY setting_key"
        return Database.execute_query(query, fetch_all=True)


class NotificationLog:
    """Модель журнала уведомлений"""
    
    @staticmethod
    def create(plant_id, notification_type):
        """Создать запись об уведомлении"""
        query = """
            INSERT INTO notification_log (plant_id, notification_type)
            VALUES (%s, %s)
        """
        return Database.execute_query(query, (plant_id, notification_type), commit=True)
    
    @staticmethod
    def mark_completed(log_id, user_id):
        """Отметить уведомление как выполненное"""
        from datetime import datetime
        query = """
            UPDATE notification_log 
            SET is_completed = TRUE, completed_by_user_id = %s, completed_at = %s
            WHERE id = %s
        """
        Database.execute_query(query, (user_id, datetime.now(), log_id), commit=True)
    
    @staticmethod
    def get_pending_for_plant(plant_id, notification_type):
        """Получить незавершенные уведомления для растения"""
        query = """
            SELECT * FROM notification_log 
            WHERE plant_id = %s 
            AND notification_type = %s 
            AND is_completed = FALSE
            ORDER BY sent_at DESC
        """
        return Database.execute_query(query, (plant_id, notification_type), fetch_all=True)
    
    @staticmethod
    def increment_attempt(log_id):
        """Увеличить счетчик попыток"""
        query = "UPDATE notification_log SET attempt_number = attempt_number + 1 WHERE id = %s"
        Database.execute_query(query, (log_id,), commit=True)
