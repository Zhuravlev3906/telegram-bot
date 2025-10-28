import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any
from config import Config

class DatabaseManager:
    def __init__(self, db_path: str = Config.DATABASE_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Инициализация таблиц в базе данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица отзывов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    text TEXT NOT NULL,
                    status TEXT DEFAULT 'new',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица вопросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    text TEXT NOT NULL,
                    status TEXT DEFAULT 'new',
                    moderator_id INTEGER DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (moderator_id) REFERENCES moderators (user_id)
                )
            ''')
            
            # Таблица фотографий для вопросов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS question_photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER,
                    file_id TEXT NOT NULL,
                    file_unique_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions (id)
                )
            ''')
            
            # Таблица модераторов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS moderators (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Таблица ответов на вопросы
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER,
                    moderator_id INTEGER,
                    answer_text TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions (id),
                    FOREIGN KEY (moderator_id) REFERENCES moderators (user_id)
                )
            ''')
            
            conn.commit()
    
    def add_user(self, user_id: int, username: str, first_name: str):
        """Добавление/обновление пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (user_id, username, first_name))
            conn.commit()
    
    def add_feedback(self, user_id: int, text: str) -> int:
        """Добавление отзыва в базу"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedbacks (user_id, text)
                VALUES (?, ?)
            ''', (user_id, text))
            conn.commit()
            return cursor.lastrowid
    
    def add_question(self, user_id: int, text: str) -> int:
        """Добавление вопроса в базу"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO questions (user_id, text)
                VALUES (?, ?)
            ''', (user_id, text))
            conn.commit()
            return cursor.lastrowid
    
    def add_question_photo(self, question_id: int, file_id: str, file_unique_id: str):
        """Добавление фотографии к вопросу"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO question_photos (question_id, file_id, file_unique_id)
                VALUES (?, ?, ?)
            ''', (question_id, file_id, file_unique_id))
            conn.commit()
    
    def get_active_moderators(self) -> List[tuple]:
        """Получение списка активных модераторов"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, username, first_name 
                FROM moderators 
                WHERE is_active = 1
            ''')
            return cursor.fetchall()
    
    def add_moderator(self, user_id: int, username: str, first_name: str):
        """Добавление модератора"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO moderators (user_id, username, first_name)
                VALUES (?, ?, ?)
            ''', (user_id, username, first_name))
            conn.commit()
    
    def get_question(self, question_id: int) -> Optional[tuple]:
        """Получение вопроса по ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT q.*, u.user_id, u.username, u.first_name 
                FROM questions q
                JOIN users u ON q.user_id = u.user_id
                WHERE q.id = ?
            ''', (question_id,))
            return cursor.fetchone()
    
    def get_question_photos(self, question_id: int) -> List[tuple]:
        """Получение фотографий вопроса"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT file_id, file_unique_id 
                FROM question_photos 
                WHERE question_id = ?
            ''', (question_id,))
            return cursor.fetchall()
    
    def update_question_status(self, question_id: int, status: str):
        """Обновление статуса вопроса"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE questions SET status = ? WHERE id = ?
            ''', (status, question_id))
            conn.commit()
    
    def add_answer(self, question_id: int, moderator_id: int, answer_text: str) -> int:
        """Добавление ответа на вопрос"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO answers (question_id, moderator_id, answer_text)
                VALUES (?, ?, ?)
            ''', (question_id, moderator_id, answer_text))
            conn.commit()
            return cursor.lastrowid
    
    def is_question_answered(self, question_id: int) -> bool:
        """Проверка, отвечен ли вопрос"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status FROM questions WHERE id = ?
            ''', (question_id,))
            result = cursor.fetchone()
            return result and result[0] == 'answered'
    
    def get_question_status(self, question_id: int) -> Optional[str]:
        """Получение статуса вопроса"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT status FROM questions WHERE id = ?
            ''', (question_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def set_question_in_progress(self, question_id: int, moderator_id: int) -> bool:
        """
        Устанавливает вопрос "в работе" указанным модератором.
        Возвращает True если блокировка успешна, False если вопрос уже взят другим модератором.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Проверяем, не взят ли вопрос уже другим модератором
            cursor.execute('''
                SELECT moderator_id FROM questions WHERE id = ? AND (status = 'new' OR status = 'in_progress')
            ''', (question_id,))
            result = cursor.fetchone()
            
            if result and result[0] is not None:
                # Вопрос уже взят другим модератором
                return False
            
            # Блокируем вопрос за текущим модератором
            cursor.execute('''
                UPDATE questions 
                SET status = 'in_progress', moderator_id = ? 
                WHERE id = ? AND (status = 'new' OR status = 'in_progress')
            ''', (moderator_id, question_id))
            
            conn.commit()
            return cursor.rowcount > 0
    
    def release_question_lock(self, question_id: int) -> bool:
        """Освобождает блокировку вопроса"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE questions 
                SET status = 'new', moderator_id = NULL 
                WHERE id = ? AND status = 'in_progress'
            ''', (question_id,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_question_moderator(self, question_id: int) -> Optional[int]:
        """Получает ID модератора, который взял вопрос в работу"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT moderator_id FROM questions WHERE id = ?
            ''', (question_id,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_new_questions(self) -> List[tuple]:
        """Получает список новых вопросов (статус 'new')"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT q.*, u.username, u.first_name 
                FROM questions q
                JOIN users u ON q.user_id = u.user_id
                WHERE q.status = 'new'
                ORDER BY q.created_at ASC
            ''')
            return cursor.fetchall()
    
    def get_in_progress_questions(self) -> List[tuple]:
        """Получает список вопросов в работе"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT q.*, u.username, u.first_name, m.username as moderator_username
                FROM questions q
                JOIN users u ON q.user_id = u.user_id
                LEFT JOIN moderators m ON q.moderator_id = m.user_id
                WHERE q.status = 'in_progress'
                ORDER BY q.created_at ASC
            ''')
            return cursor.fetchall()
    
    def get_question_answers(self, question_id: int) -> List[dict]:
        """Получение ответов на вопрос"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT a.id, a.answer_text, a.created_at, m.first_name as moderator_name
                FROM answers a
                LEFT JOIN moderators m ON a.moderator_id = m.user_id
                WHERE a.question_id = ?
                ORDER BY a.created_at ASC
            ''', (question_id,))
            
            answers = []
            for row in cursor.fetchall():
                answers.append({
                    'id': row[0],
                    'text': row[1],
                    'created_at': row[2],
                    'moderator_name': row[3] or 'Модератор'
                })
            return answers