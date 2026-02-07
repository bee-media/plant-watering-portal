"""
Главное приложение Flask для портала управления поливом растений
"""
import os
import logging
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import bcrypt
from werkzeug.utils import secure_filename
from config import Config
from database import User, Plant, WateringHistory, SystemSettings
from scheduler import notification_scheduler
import threading

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание приложения Flask
app = Flask(__name__)
app.config.from_object(Config)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'


class UserLogin(UserMixin):
    """Класс пользователя для Flask-Login"""
    
    def __init__(self, user_data):
        self.id = user_data['id']
        self.name = user_data['name']
        self.username = user_data['username']
        self.telegram_id = user_data.get('telegram_id')
        self.receive_notifications = user_data.get('receive_notifications', True)


@login_manager.user_loader
def load_user(user_id):
    """Загрузка пользователя для Flask-Login"""
    user_data = User.get_by_id(int(user_id))
    if user_data:
        return UserLogin(user_data)
    return None


# Вспомогательные функции

def allowed_file(filename):
    """Проверка допустимого расширения файла"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS


def save_plant_image(file):
    """Сохранение изображения растения"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Добавляем timestamp к имени файла для уникальности
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{timestamp}{ext}"
        
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(filepath)
        return f"/static/uploads/{filename}"
    return None


# Маршруты приложения

@app.route('/')
@login_required
def index():
    """Главная страница - дашборд"""
    plants = Plant.get_all()
    recent_history = WateringHistory.get_recent(limit=10)
    
    # Подсчет статистики
    today = datetime.now().date()
    plants_needing_water = sum(1 for p in plants if p['next_watering_date'] and p['next_watering_date'] <= today)
    plants_needing_fertilizer = sum(1 for p in plants if p['fertilizer_interval_days'] and 
                                   p['next_fertilizer_date'] and p['next_fertilizer_date'] <= today)
    
    return render_template('dashboard.html',
                          plants=plants,
                          recent_history=recent_history,
                          plants_needing_water=plants_needing_water,
                          plants_needing_fertilizer=plants_needing_fertilizer,
                          today=today)


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Страница входа"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user_data = User.get_by_username(username)
        
        if user_data and bcrypt.checkpw(password.encode('utf-8'), user_data['password_hash'].encode('utf-8')):
            user = UserLogin(user_data)
            login_user(user, remember=True)
            
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('Неверное имя пользователя или пароль', 'error')
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Выход из системы"""
    logout_user()
    flash('Вы успешно вышли из системы', 'success')
    return redirect(url_for('login'))


@app.route('/users')
@login_required
def users_list():
    """Список пользователей"""
    users = User.get_all()
    return render_template('users.html', users=users)


@app.route('/users/add', methods=['GET', 'POST'])
@login_required
def add_user():
    """Добавление пользователя"""
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')
        telegram_id = request.form.get('telegram_id')
        receive_notifications = request.form.get('receive_notifications') == 'on'
        
        # Проверка существования пользователя
        existing_user = User.get_by_username(username)
        if existing_user:
            flash('Пользователь с таким именем уже существует', 'error')
            return redirect(url_for('add_user'))
        
        # Хеширование пароля
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
        # Создание пользователя
        User.create(name, username, password_hash, telegram_id, receive_notifications)
        flash(f'Пользователь {name} успешно создан', 'success')
        return redirect(url_for('users_list'))
    
    return render_template('user_form.html', action='add')


@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """Редактирование пользователя"""
    user = User.get_by_id(user_id)
    if not user:
        flash('Пользователь не найден', 'error')
        return redirect(url_for('users_list'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        telegram_id = request.form.get('telegram_id')
        receive_notifications = request.form.get('receive_notifications') == 'on'
        new_password = request.form.get('new_password')
        
        # Обновление пользователя
        User.update(user_id, name, username, telegram_id, receive_notifications)
        
        # Обновление пароля, если указан
        if new_password:
            password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            User.update_password(user_id, password_hash)
        
        flash(f'Данные пользователя {name} обновлены', 'success')
        return redirect(url_for('users_list'))
    
    return render_template('user_form.html', action='edit', user=user)


@app.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Удаление пользователя"""
    if user_id == current_user.id:
        flash('Вы не можете удалить свою учетную запись', 'error')
        return redirect(url_for('users_list'))
    
    user = User.get_by_id(user_id)
    if user:
        User.delete(user_id)
        flash(f'Пользователь {user["name"]} удален', 'success')
    else:
        flash('Пользователь не найден', 'error')
    
    return redirect(url_for('users_list'))


@app.route('/plants')
@login_required
def plants_list():
    """Список растений"""
    plants = Plant.get_all()
    today = datetime.now().date()
    return render_template('plants.html', plants=plants, today=today)


@app.route('/plants/add', methods=['GET', 'POST'])
@login_required
def add_plant():
    """Добавление растения"""
    if request.method == 'POST':
        name = request.form.get('name')
        watering_interval = int(request.form.get('watering_interval'))
        fertilizer_interval = request.form.get('fertilizer_interval')
        description = request.form.get('description')
        location = request.form.get('location')
        
        fertilizer_interval = int(fertilizer_interval) if fertilizer_interval else None
        
        # Обработка изображения
        image_url = None
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                image_url = save_plant_image(file)
        
        # Создание растения
        Plant.create(name, watering_interval, fertilizer_interval, description, location, image_url)
        flash(f'Растение {name} успешно добавлено', 'success')
        return redirect(url_for('plants_list'))
    
    return render_template('plant_form.html', action='add')


@app.route('/plants/edit/<int:plant_id>', methods=['GET', 'POST'])
@login_required
def edit_plant(plant_id):
    """Редактирование растения"""
    plant = Plant.get_by_id(plant_id)
    if not plant:
        flash('Растение не найдено', 'error')
        return redirect(url_for('plants_list'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        watering_interval = int(request.form.get('watering_interval'))
        fertilizer_interval = request.form.get('fertilizer_interval')
        description = request.form.get('description')
        location = request.form.get('location')
        
        fertilizer_interval = int(fertilizer_interval) if fertilizer_interval else None
        
        # Обработка изображения
        image_url = plant['image_url']
        if 'image' in request.files:
            file = request.files['image']
            if file.filename:
                new_image_url = save_plant_image(file)
                if new_image_url:
                    image_url = new_image_url
        
        # Обновление растения
        Plant.update(plant_id, name, watering_interval, fertilizer_interval, description, location, image_url)
        flash(f'Данные растения {name} обновлены', 'success')
        return redirect(url_for('plants_list'))
    
    return render_template('plant_form.html', action='edit', plant=plant)


@app.route('/plants/delete/<int:plant_id>', methods=['POST'])
@login_required
def delete_plant(plant_id):
    """Удаление растения"""
    plant = Plant.get_by_id(plant_id)
    if plant:
        Plant.delete(plant_id)
        flash(f'Растение {plant["name"]} удалено', 'success')
    else:
        flash('Растение не найдено', 'error')
    
    return redirect(url_for('plants_list'))


@app.route('/plants/water/<int:plant_id>', methods=['POST'])
@login_required
def water_plant(plant_id):
    """Полить растение"""
    success = Plant.update_watering(plant_id, current_user.id)
    
    if success:
        plant = Plant.get_by_id(plant_id)
        flash(f'Растение {plant["name"]} полито', 'success')
    else:
        flash('Ошибка при обновлении данных', 'error')
    
    return redirect(request.referrer or url_for('index'))


@app.route('/plants/fertilize/<int:plant_id>', methods=['POST'])
@login_required
def fertilize_plant(plant_id):
    """Прикормить растение"""
    success = Plant.update_fertilizer(plant_id, current_user.id)
    
    if success:
        plant = Plant.get_by_id(plant_id)
        flash(f'Растение {plant["name"]} прикормлено', 'success')
    else:
        flash('Ошибка при обновлении данных', 'error')
    
    return redirect(request.referrer or url_for('index'))


@app.route('/plants/<int:plant_id>/history')
@login_required
def plant_history(plant_id):
    """История полива растения"""
    plant = Plant.get_by_id(plant_id)
    if not plant:
        flash('Растение не найдено', 'error')
        return redirect(url_for('plants_list'))
    
    history = WateringHistory.get_by_plant(plant_id, limit=50)
    return render_template('plant_history.html', plant=plant, history=history)


@app.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Настройки системы"""
    if request.method == 'POST':
        SystemSettings.set('notification_start_hour', request.form.get('start_hour'))
        SystemSettings.set('notification_end_hour', request.form.get('end_hour'))
        SystemSettings.set('notification_retry_interval_minutes', request.form.get('retry_interval'))
        SystemSettings.set('notification_max_retries', request.form.get('max_retries'))
        SystemSettings.set('telegram_bot_token', request.form.get('bot_token'))
        
        flash('Настройки успешно сохранены', 'success')
        return redirect(url_for('settings'))
    
    settings_dict = {s['setting_key']: s['setting_value'] for s in SystemSettings.get_all()}
    return render_template('settings.html', settings=settings_dict)


@app.route('/api/dashboard/stats')
@login_required
def dashboard_stats():
    """API для получения статистики дашборда"""
    plants = Plant.get_all()
    today = datetime.now().date()
    
    stats = {
        'total_plants': len(plants),
        'plants_needing_water': sum(1 for p in plants if p['next_watering_date'] and p['next_watering_date'] <= today),
        'plants_needing_fertilizer': sum(1 for p in plants if p['fertilizer_interval_days'] and 
                                        p['next_fertilizer_date'] and p['next_fertilizer_date'] <= today),
        'watered_today': sum(1 for p in plants if p['last_watered_at'] and 
                            p['last_watered_at'].date() == today)
    }
    
    return jsonify(stats)


# Запуск приложения

def start_telegram_bot():
    """Запуск Telegram бота в отдельном потоке"""
    from telegram_bot import telegram_notifier
    if telegram_notifier.application:
        telegram_notifier.run_bot()


if __name__ == '__main__':
    # Создание необходимых директорий
    Config.init_app(app)
    
    # Запуск планировщика
    notification_scheduler.start()
    
    # Запуск Telegram бота в отдельном потоке
    # bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    # bot_thread.start()
    
    # Запуск Flask приложения
    logger.info(f"Запуск приложения на {Config.HOST}:{Config.PORT}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
