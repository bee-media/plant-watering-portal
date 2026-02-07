#!/usr/bin/env python3
"""
Скрипт для создания нового пользователя в системе управления поливом растений
"""
import pymysql
import bcrypt
from config import Config


def create_user():
    """Создание нового пользователя"""
    print("\n🌱 Создание нового пользователя\n")
    
    # Подключение к базе данных
    try:
        db_config = Config.DB_CONFIG.copy()
        db_config['cursorclass'] = pymysql.cursors.Cursor  # Используем обычный курсор
        connection = pymysql.connect(**db_config)
        print("✅ Подключение к базе данных успешно\n")
    except Exception as e:
        print(f"❌ Ошибка подключения к базе данных: {e}")
        print("Убедитесь, что MySQL запущен и данные в .env файле корректны")
        return
    
    try:
        with connection.cursor() as cursor:
            # Ввод данных пользователя
            print("Введите данные нового пользователя:\n")
            
            # Имя
            while True:
                name = input("Имя и фамилия: ").strip()
                if name:
                    break
                print("❌ Имя не может быть пустым")
            
            # Логин
            while True:
                username = input("Логин (для входа в систему): ").strip().lower()
                if not username:
                    print("❌ Логин не может быть пустым")
                    continue
                
                # Проверка существования пользователя
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    print(f"❌ Пользователь с логином '{username}' уже существует")
                    continue
                
                break
            
            # Пароль
            print("\n⚠️  ВНИМАНИЕ: Пароль будет виден при вводе")
            while True:
                password = input("Пароль (минимум 6 символов): ").strip()
                if len(password) < 6:
                    print("❌ Пароль должен содержать минимум 6 символов")
                    continue
                
                password_confirm = input("Подтвердите пароль: ").strip()
                if password != password_confirm:
                    print("❌ Пароли не совпадают")
                    continue
                
                break
            
            # Telegram ID (опционально)
            print("\nTelegram ID (опционально):")
            print("Чтобы получить ID, отправьте /start вашему боту")
            telegram_id = input("Telegram ID (или Enter для пропуска): ").strip()
            if not telegram_id:
                telegram_id = None
            
            # Уведомления
            receive_notifications_input = input("Получать уведомления? (y/n, по умолчанию y): ").strip().lower()
            receive_notifications = receive_notifications_input != 'n'
            
            # Хеширование пароля
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Вставка пользователя
            cursor.execute(
                """
                INSERT INTO users (name, username, password_hash, telegram_id, receive_notifications)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (name, username, password_hash, telegram_id, receive_notifications)
            )
            connection.commit()
            
            print("\n✅ Пользователь успешно создан!")
            print(f"\n📝 Данные для входа:")
            print(f"   Логин: {username}")
            print(f"   Пароль: [указанный вами]")
            if telegram_id:
                print(f"   Telegram ID: {telegram_id}")
            print(f"   Уведомления: {'Включены' if receive_notifications else 'Выключены'}")
            print("\n🚀 Теперь вы можете войти в систему с этими данными\n")
            
    except Exception as e:
        print(f"\n❌ Ошибка при создании пользователя: {e}")
        connection.rollback()
    finally:
        connection.close()


def list_users():
    """Показать список существующих пользователей"""
    try:
        db_config = Config.DB_CONFIG.copy()
        db_config['cursorclass'] = pymysql.cursors.Cursor  # Используем обычный курсор
        connection = pymysql.connect(**db_config)
        
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, username, telegram_id, receive_notifications FROM users WHERE is_active = TRUE"
            )
            users = cursor.fetchall()
            
            if not users:
                print("\n📋 Пользователи не найдены\n")
                return
            
            print("\n📋 Существующие пользователи:\n")
            print(f"{'ID':<5} {'Имя':<25} {'Логин':<20} {'Telegram ID':<15} {'Уведомления'}")
            print("-" * 90)
            
            for user in users:
                notifications = "✅ Да" if user[4] else "❌ Нет"
                telegram = user[3] if user[3] else "—"
                print(f"{user[0]:<5} {user[1]:<25} {user[2]:<20} {telegram:<15} {notifications}")
            
            print()
            
    except Exception as e:
        print(f"\n❌ Ошибка при получении списка пользователей: {e}\n")
    finally:
        connection.close()


def delete_user():
    """Удаление пользователя"""
    print("\n🗑️  Удаление пользователя\n")
    
    try:
        db_config = Config.DB_CONFIG.copy()
        db_config['cursorclass'] = pymysql.cursors.Cursor  # Используем обычный курсор
        connection = pymysql.connect(**db_config)
        
        # Показываем список пользователей
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, username FROM users WHERE is_active = TRUE"
            )
            users = cursor.fetchall()
            
            if not users:
                print("📋 Пользователи не найдены\n")
                return
            
            print("📋 Существующие пользователи:\n")
            for user in users:
                print(f"  {user[0]}. {user[1]} ({user[2]})")
            
            print()
            
            # Выбор пользователя для удаления
            while True:
                try:
                    user_id = input("Введите ID пользователя для удаления (или 0 для отмены): ").strip()
                    user_id = int(user_id)
                    
                    if user_id == 0:
                        print("Отменено\n")
                        return
                    
                    # Находим пользователя
                    selected_user = None
                    for user in users:
                        if user[0] == user_id:
                            selected_user = user
                            break
                    
                    if not selected_user:
                        print(f"❌ Пользователь с ID {user_id} не найден")
                        continue
                    
                    # Подтверждение
                    confirm = input(f"⚠️  Удалить пользователя '{selected_user[1]}' ({selected_user[2]})? (yes/no): ").strip().lower()
                    
                    if confirm == 'yes':
                        cursor.execute("UPDATE users SET is_active = FALSE WHERE id = %s", (user_id,))
                        connection.commit()
                        print(f"\n✅ Пользователь '{selected_user[1]}' удален\n")
                    else:
                        print("Отменено\n")
                    
                    break
                    
                except ValueError:
                    print("❌ Введите корректный ID")
                    
    except Exception as e:
        print(f"\n❌ Ошибка при удалении пользователя: {e}\n")
        connection.rollback()
    finally:
        connection.close()


def reset_password():
    """Сброс пароля пользователя"""
    print("\n🔑 Сброс пароля пользователя\n")
    
    try:
        db_config = Config.DB_CONFIG.copy()
        db_config['cursorclass'] = pymysql.cursors.Cursor  # Используем обычный курсор
        connection = pymysql.connect(**db_config)
        
        # Показываем список пользователей
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, name, username FROM users WHERE is_active = TRUE"
            )
            users = cursor.fetchall()
            
            if not users:
                print("📋 Пользователи не найдены\n")
                return
            
            print("📋 Существующие пользователи:\n")
            for user in users:
                print(f"  {user[0]}. {user[1]} ({user[2]})")
            
            print()
            
            # Выбор пользователя
            while True:
                try:
                    user_id = input("Введите ID пользователя (или 0 для отмены): ").strip()
                    user_id = int(user_id)
                    
                    if user_id == 0:
                        print("Отменено\n")
                        return
                    
                    # Находим пользователя
                    selected_user = None
                    for user in users:
                        if user[0] == user_id:
                            selected_user = user
                            break
                    
                    if not selected_user:
                        print(f"❌ Пользователь с ID {user_id} не найден")
                        continue
                    
                    break
                    
                except ValueError:
                    print("❌ Введите корректный ID")
            
            # Новый пароль
            print("\n⚠️  ВНИМАНИЕ: Пароль будет виден при вводе")
            while True:
                new_password = input(f"\nНовый пароль для '{selected_user[1]}' (минимум 6 символов): ").strip()
                if len(new_password) < 6:
                    print("❌ Пароль должен содержать минимум 6 символов")
                    continue
                
                password_confirm = input("Подтвердите пароль: ").strip()
                if new_password != password_confirm:
                    print("❌ Пароли не совпадают")
                    continue
                
                break
            
            # Хеширование и обновление
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))
            connection.commit()
            
            print(f"\n✅ Пароль для пользователя '{selected_user[1]}' успешно изменен\n")
                    
    except Exception as e:
        print(f"\n❌ Ошибка при сбросе пароля: {e}\n")
        connection.rollback()
    finally:
        connection.close()


def main():
    """Главное меню"""
    while True:
        print("\n" + "="*50)
        print("🌱 Управление пользователями")
        print("="*50)
        print("\n1. Создать нового пользователя")
        print("2. Показать список пользователей")
        print("3. Удалить пользователя")
        print("4. Сбросить пароль пользователя")
        print("0. Выход")
        
        choice = input("\nВыберите действие: ").strip()
        
        if choice == '1':
            create_user()
        elif choice == '2':
            list_users()
        elif choice == '3':
            delete_user()
        elif choice == '4':
            reset_password()
        elif choice == '0':
            print("\n👋 До свидания!\n")
            break
        else:
            print("\n❌ Неверный выбор, попробуйте снова")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Прервано пользователем\n")
    except Exception as e:
        print(f"\n❌ Непредвиденная ошибка: {e}\n")
