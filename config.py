import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Токен бота из переменных окружения
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    # Настройки базы данных
    DATABASE_PATH = os.getenv('DATABASE_PATH', 'feedback_bot.db')
    
    # ID администраторов (через запятую в .env)
    ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x]
    
    # Лимиты
    MAX_PHOTOS_PER_QUESTION = 3
    FEEDBACK_COOLDOWN_MINUTES = 5
    
    # Настройки FastAPI
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('API_PORT', 8000))