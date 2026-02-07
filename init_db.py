#!/usr/bin/env python3
"""
Скрипт для инициализации и проверки базы данных
"""
import pymysql
from config import Config


def create_database():
    """Создание базы данных если она не существует"""
    connection = pymysql.connect(
        host=Config.DB_CONFIG['host'],
        port=Config.DB_CONFIG['port'],
        user=Config.DB_CONFIG['user'],
        password=Config.DB_CONFIG['password']
    )
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_CONFIG['database']} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
            print(f"✅ База данных '{Config.DB_CONFIG['database']}' создана или уже существует")
    finally:
        connection.close()


def check_connection():
    """Проверка подключения к базе данных"""
    try:
        connection = pymysql.connect(**Config.DB_CONFIG)
        print("✅ Подключение к базе данных успешно")
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"✅ Версия MySQL: {version[0]}")
        
        connection.close()
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        return False


def check_tables():
    """Проверка наличия таблиц"""
    connection = pymysql.connect(**Config.DB_CONFIG)
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            if not tables:
                print("❌ Таблицы не найдены. Выполните файл database.sql")
                return False
            
            print(f"✅ Найдено таблиц: {len(tables)}")
            for table in tables:
                print(f"   - {table[0]}")
            
            return True
    finally:
        connection.close()


def check_users():
    """Проверка наличия пользователей"""
    connection = pymysql.connect(**Config.DB_CONFIG)
    
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = TRUE")
            result = cursor.fetchone()
            
            if result[0] == 0:
                print("⚠️  Пользователи не найдены")
                print("   Используйте скрипт manage_users.py для создания первого пользователя")
                return False
            else:
                print(f"✅ Найдено активных пользователей: {result[0]}")
                return True
    finally:
        connection.close()


def main():
    """Основная функция"""
    print("\n🌱 Инициализация базы данных для системы управления поливом растений\n")
    
    print("Шаг 1: Создание базы данных")
    try:
        create_database()
    except Exception as e:
        print(f"❌ Ошибка создания базы данных: {e}")
        return
    
    print("\nШаг 2: Проверка подключения")
    if not check_connection():
        print("\n❌ Инициализация прервана из-за ошибок подключения")
        return
    
    print("\nШаг 3: Проверка таблиц")
    if not check_tables():
        print("\n⚠️  Необходимо выполнить файл database.sql:")
        print("   mysql -u root -p plant_watering < database.sql")
        return
    
    print("\nШаг 4: Проверка пользователей")
    has_users = check_users()
    
    print("\n✅ Инициализация завершена успешно!")
    print("\n📝 Следующие шаги:")
    if not has_users:
        print("   1. Создайте первого пользователя: python manage_users.py")
        print("   2. Запустите приложение: python app.py")
        print("   3. Откройте браузер: http://localhost:5000")
        print("   4. Войдите с созданными данными")
    else:
        print("   1. Запустите приложение: python app.py")
        print("   2. Откройте браузер: http://localhost:5000")
        print("   3. Войдите с существующими данными")
    print("   5. Настройте Telegram бота в разделе 'Настройки'\n")


if __name__ == '__main__':
    main()
