from telegram import Update, InputMediaPhoto
from telegram.ext import ContextTypes
from database.manager import DatabaseManager
from config import Config
import base64
import uuid
import os
import re
from io import BytesIO
from PIL import Image

db = DatabaseManager()

def extract_base64_from_img_tags(img_tags: List[str]) -> List[str]:
    """
    Извлекает base64 данные из HTML img тегов
    Пример: <img src="data:image/jpeg;base64,AAAA..." />
    """
    base64_list = []
    
    for img_tag in img_tags:
        try:
            # Ищем src атрибут с data URL
            match = re.search(r'src="data:image/([^;]+);base64,([^"]+)"', img_tag)
            if match:
                image_format = match.group(1)  # jpeg, png, etc
                base64_data = match.group(2)
                
                # Формируем полный base64 data URL
                full_base64 = f"data:image/{image_format};base64,{base64_data}"
                base64_list.append(full_base64)
                
                print(f"✅ Извлечено base64 изображение формата {image_format}")
            else:
                print(f"⚠️ Не удалось извлечь base64 из тега: {img_tag[:100]}...")
                
        except Exception as e:
            print(f"❌ Ошибка при парсинге img тега: {e}")
    
    return base64_list

def optimize_image_for_telegram(image_path: str) -> str:
    """
    Оптимизирует изображение для Telegram
    Возвращает путь к оптимизированному изображению
    """
    try:
        with Image.open(image_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Получаем размеры
            width, height = img.size
            
            # Если изображение слишком большое, уменьшаем его
            max_size = 1280
            if width > max_size or height > max_size:
                if width > height:
                    new_width = max_size
                    new_height = int(height * max_size / width)
                else:
                    new_height = max_size
                    new_width = int(width * max_size / height)
                
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                print(f"✅ Изображение уменьшено с {width}x{height} до {new_width}x{new_height}")
            
            # Сохраняем оптимизированное изображение
            optimized_path = image_path.replace('.', '_optimized.')
            img.save(optimized_path, 'JPEG', quality=85, optimize=True)
            
            print(f"✅ Изображение оптимизировано: {optimized_path}")
            return optimized_path
            
    except Exception as e:
        print(f"❌ Ошибка оптимизации изображения: {e}")
        return image_path  # Возвращаем оригинальный путь в случае ошибки

async def notify_moderators(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                          question_id: int, question_text: str, photos: list):
    """Уведомляет всех модераторов о новом вопросе из Telegram"""
    moderators = db.get_active_moderators()
    user = update.effective_user
    
    if not moderators:
        print("⚠️ Нет активных модераторов для уведомления!")
        return
    
    user_info = format_user_info(user)
    
    message_text = (
        f"🚨 НОВЫЙ ВОПРОС #Q{question_id}\n"
        f"От: {user_info}\n"
        f"ID пользователя: {user.id}\n\n"
        f"❓ Вопрос:\n{question_text}\n\n"
        f"💬 Ответьте командой: /answer_{question_id}"
    )
    
    await send_to_moderators(context, moderators, message_text, photos)

async def notify_moderators_web(question_id: int, question_text: str, photo_paths: list):
    """Уведомляет модераторов о новом вопросе с сайта"""
    moderators = db.get_active_moderators()
    
    if not moderators:
        print("⚠️ Нет активных модераторов для уведомления!")
        return
    
    message_text = (
        f"🌐 НОВЫЙ ВОПРОС С САЙТА #Q{question_id}\n\n"
        f"{question_text}\n\n"
    )
    
    # Оптимизируем фото перед отправкой
    optimized_photos = []
    for photo_path in photo_paths:
        try:
            optimized_path = optimize_image_for_telegram(photo_path)
            optimized_photos.append(optimized_path)
        except Exception as e:
            print(f"❌ Ошибка оптимизации фото {photo_path}: {e}")
            optimized_photos.append(photo_path)  # Используем оригинал если оптимизация не удалась
    
    # Отправляем фото если есть
    for moderator_id, username, first_name in moderators:
        try:
            if optimized_photos:
                if len(optimized_photos) == 1:
                    # Одно фото с подписью
                    await send_telegram_photo_from_path(Config.BOT_TOKEN, moderator_id, optimized_photos[0], message_text)
                else:
                    # Несколько фото - отправляем альбомом
                    await send_telegram_media_group_from_paths(Config.BOT_TOKEN, moderator_id, optimized_photos, message_text)
            else:
                # Без фото - просто текст
                await send_telegram_message(Config.BOT_TOKEN, moderator_id, message_text)
            
            print(f"✅ Уведомление отправлено модератору {first_name} (ID: {moderator_id})")
            
        except Exception as e:
            print(f"❌ Ошибка отправки модератору {moderator_id}: {e}")

def save_base64_image(base64_string: str, question_id: int, photo_index: int) -> str:
    """
    Сохраняет base64 изображение в файл
    Возвращает путь к сохраненному файлу
    """
    try:
        # Создаем папку для фото если не существует
        photos_dir = os.path.join("uploads", "photos", str(question_id))
        os.makedirs(photos_dir, exist_ok=True)
        
        # Определяем тип изображения и расширение
        if base64_string.startswith('data:image/jpeg;base64,'):
            extension = '.jpg'
            base64_data = base64_string.replace('data:image/jpeg;base64,', '')
        elif base64_string.startswith('data:image/png;base64,'):
            extension = '.png'
            base64_data = base64_string.replace('data:image/png;base64,', '')
        elif base64_string.startswith('data:image/gif;base64,'):
            extension = '.gif'
            base64_data = base64_string.replace('data:image/gif;base64,', '')
        elif base64_string.startswith('data:image/webp;base64,'):
            extension = '.webp'
            base64_data = base64_string.replace('data:image/webp;base64,', '')
        else:
            # По умолчанию считаем jpg
            extension = '.jpg'
            base64_data = base64_string
        
        # Генерируем уникальное имя файла
        filename = f"photo_{photo_index}_{uuid.uuid4().hex}{extension}"
        filepath = os.path.join(photos_dir, filename)
        
        # Декодируем и сохраняем изображение
        image_data = base64.b64decode(base64_data)
        with open(filepath, 'wb') as f:
            f.write(image_data)
        
        print(f"✅ Фото сохранено: {filepath}")
        return filepath
        
    except Exception as e:
        print(f"❌ Ошибка сохранения base64 изображения: {e}")
        return None

async def send_telegram_photo_from_path(bot_token: str, chat_id: int, photo_path: str, caption: str = ""):
    """Отправляет фото в Telegram по пути к файлу"""
    import aiohttp
    
    url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    
    with open(photo_path, 'rb') as photo_file:
        form_data = aiohttp.FormData()
        form_data.add_field('chat_id', str(chat_id))
        if caption:
            form_data.add_field('caption', caption)
            form_data.add_field('parse_mode', 'HTML')
        form_data.add_field('photo', photo_file, filename=os.path.basename(photo_path))
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"Telegram API error: {error_text}")

async def send_telegram_media_group_from_paths(bot_token: str, chat_id: int, photo_paths: list, caption: str = ""):
    """Отправляет группу медиа в Telegram по путям к файлам"""
    import aiohttp
    import json
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
    
    # Подготавливаем медиа группу
    media = []
    files = {}
    
    for i, photo_path in enumerate(photo_paths):
        # Читаем файл и добавляем в files
        with open(photo_path, 'rb') as photo_file:
            file_key = f'photo_{i}'
            files[file_key] = photo_file.read()
        
        # Для первого фото добавляем подпись, для остальных - нет
        media_item = {
            'type': 'photo',
            'media': f'attach://{file_key}'
        }
        
        # Добавляем caption и parse_mode только для первого фото
        if i == 0 and caption:
            media_item['caption'] = caption
            media_item['parse_mode'] = 'HTML'
        
        media.append(media_item)
    
    # Создаем form data
    form_data = aiohttp.FormData()
    form_data.add_field('chat_id', str(chat_id))
    form_data.add_field('media', json.dumps(media))
    
    # Добавляем файлы
    for file_key, file_content in files.items():
        form_data.add_field(file_key, file_content, filename=f'{file_key}.jpg')
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form_data) as response:
            if response.status != 200:
                error_text = await response.text()
                # Если не удалось отправить альбом, пробуем отправить по одному
                if "MEDIA_GROUP_INVALID" in error_text or "WEBP_NOT_SUPPORTED" in error_text:
                    print(f"⚠️ Не удалось отправить альбом, отправляю фото по одному: {error_text}")
                    await send_photos_individually_from_paths(bot_token, chat_id, photo_paths, caption)
                else:
                    raise Exception(f"Telegram API error: {error_text}")

async def send_photos_individually_from_paths(bot_token: str, chat_id: int, photo_paths: list, caption: str = ""):
    """Отправляет фото по одному (fallback метод)"""
    for i, photo_path in enumerate(photo_paths):
        # Первое фото с подписью, остальные без
        photo_caption = caption if i == 0 else ""
        await send_telegram_photo_from_path(bot_token, chat_id, photo_path, photo_caption)

async def send_to_moderators(context: ContextTypes.DEFAULT_TYPE, moderators: list, 
                           message_text: str, photos: list):
    """Отправляет сообщение всем модераторам"""
    for moderator_id, username, first_name in moderators:
        try:
            if photos and hasattr(photos[0], 'get'):
                # Telegram фото (из бота)
                if len(photos) == 1:
                    await context.bot.send_photo(
                        chat_id=moderator_id,
                        photo=photos[0]['file_id'],
                        caption=message_text
                    )
                else:
                    media_group = []
                    media_group.append(
                        InputMediaPhoto(
                            media=photos[0]['file_id'],
                            caption=message_text
                        )
                    )
                    for photo in photos[1:]:
                        media_group.append(InputMediaPhoto(media=photo['file_id']))
                    
                    await context.bot.send_media_group(
                        chat_id=moderator_id,
                        media=media_group
                    )
            else:
                # Текстовое сообщение
                await context.bot.send_message(
                    chat_id=moderator_id,
                    text=message_text
                )
            
            print(f"✅ Уведомление отправлено модератору {first_name} (ID: {moderator_id})")
            
        except Exception as e:
            print(f"❌ Ошибка отправки модератору {moderator_id}: {e}")

async def send_telegram_message(bot_token: str, chat_id: int, text: str):
    """Отправляет сообщение в Telegram через API"""
    import aiohttp
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                raise Exception(f"Telegram API error: {error_text}")

async def notify_moderators_about_taken_question(question_id: int, moderator_name: str, context: ContextTypes.DEFAULT_TYPE):
    """Уведомляет модераторов о том, что вопрос взят в работу"""
    moderators = db.get_active_moderators()
    
    for moderator_id, username, first_name in moderators:
        try:
            await context.bot.send_message(
                chat_id=moderator_id,
                text=f"ℹ️ Вопрос #Q{question_id} взят в работу модератором {moderator_name}"
            )
        except Exception as e:
            print(f"❌ Ошибка отправки уведомления модератору {moderator_id}: {e}")

def format_user_info(user) -> str:
    """Форматирование информации о пользователе"""
    user_info = f"👤 {user.first_name}"
    if user.username:
        user_info += f" (@{user.username})"
    return user_info

def is_moderator(user_id: int) -> bool:
    """Проверка, является ли пользователь модератором"""
    moderators = db.get_active_moderators()
    moderator_ids = [mod[0] for mod in moderators]
    return user_id in moderator_ids

def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in Config.ADMIN_IDS

def truncate_text(text: str, max_length: int = 100) -> str:
    """Обрезает текст до максимальной длины"""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."

async def send_to_user(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str):
    """Отправляет сообщение пользователю"""
    try:
        await context.bot.send_message(chat_id=user_id, text=text)
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки пользователю {user_id}: {e}")
        return False