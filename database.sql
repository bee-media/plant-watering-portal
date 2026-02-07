-- Создание базы данных для системы управления поливом растений
CREATE DATABASE IF NOT EXISTS plant_watering CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE plant_watering;

-- Таблица пользователей
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    telegram_id VARCHAR(100),
    receive_notifications BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_telegram_id (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица растений
CREATE TABLE IF NOT EXISTS plants (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    watering_interval_days INT NOT NULL,
    fertilizer_interval_days INT,
    description TEXT,
    location VARCHAR(255),
    image_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_watered_at TIMESTAMP NULL,
    last_fertilized_at TIMESTAMP NULL,
    next_watering_date DATE,
    next_fertilizer_date DATE,
    INDEX idx_next_watering (next_watering_date),
    INDEX idx_next_fertilizer (next_fertilizer_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица настроек системы
CREATE TABLE IF NOT EXISTS system_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    setting_key VARCHAR(100) UNIQUE NOT NULL,
    setting_value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица истории поливов
CREATE TABLE IF NOT EXISTS watering_history (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plant_id INT NOT NULL,
    user_id INT NOT NULL,
    action_type ENUM('watering', 'fertilizer') NOT NULL,
    watered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_plant_id (plant_id),
    INDEX idx_user_id (user_id),
    INDEX idx_watered_at (watered_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Таблица журнала уведомлений
CREATE TABLE IF NOT EXISTS notification_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    plant_id INT NOT NULL,
    notification_type ENUM('watering', 'fertilizer') NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    attempt_number INT DEFAULT 1,
    is_completed BOOLEAN DEFAULT FALSE,
    completed_by_user_id INT NULL,
    completed_at TIMESTAMP NULL,
    FOREIGN KEY (plant_id) REFERENCES plants(id) ON DELETE CASCADE,
    FOREIGN KEY (completed_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_plant_id (plant_id),
    INDEX idx_sent_at (sent_at),
    INDEX idx_is_completed (is_completed)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Вставка начальных настроек системы
INSERT INTO system_settings (setting_key, setting_value, description) VALUES
('notification_start_hour', '8', 'Начало времени отправки уведомлений (час)'),
('notification_end_hour', '22', 'Конец времени отправки уведомлений (час)'),
('notification_retry_interval_minutes', '120', 'Интервал повтора уведомлений (минуты)'),
('notification_max_retries', '3', 'Максимальное количество повторов уведомлений'),
('timezone', 'Europe/Moscow', 'Часовой пояс системы'),
('telegram_bot_token', '', 'Токен Telegram бота')
ON DUPLICATE KEY UPDATE setting_value=VALUES(setting_value);
