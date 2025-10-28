from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from database.manager import DatabaseManager
from states.user_states import UserState
from utils.helpers import notify_moderators

db = DatabaseManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    context.user_data.clear()
    
    # Сохраняем/обновляем пользователя в базе
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name)
    
    welcome_text = """
Привет! 👋

Я — бот для обратной связи нашего сайта!.

Чем я могу помочь?
• 🗣️ Оставить отзыв — ваше мнение очень важно для нас
• ❓ Задать вопрос — мы с радостью на него ответим

Выберите вариант ниже:
"""
    
    keyboard = [["🗣️ Оставить отзыв", "❓ Задать вопрос"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    context.user_data['state'] = UserState.AWAITING_CHOICE

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик выбора типа обращения"""
    user_choice = update.message.text
    current_state = context.user_data.get('state')
    
    if current_state != UserState.AWAITING_CHOICE:
        from handlers.common_handlers import handle_unexpected_input
        await handle_unexpected_input(update, context)
        return
    
    if "отзыв" in user_choice.lower():
        await update.message.reply_text(
            "📝 Пожалуйста, напишите ваш отзыв текстовым сообщением:",
            reply_markup=ReplyKeyboardMarkup([["🚫 Отмена"]], resize_keyboard=True)
        )
        context.user_data['state'] = UserState.AWAITING_FEEDBACK
        context.user_data['type'] = 'feedback'
        
    elif "вопрос" in user_choice.lower():
        instruction_text = """
📝 <b>Чтобы мы могли быстрее помочь вам, опишите вопрос подробно:</b>

🔹 <b>Шаги воспроизведения:</b>
• Что вы делали перед появлением проблемы?
• Какие действия выполняли?
• На какой странице/экране возникла ошибка?

🔹 <b>Информация об устройстве:</b>
• Телефон или компьютер?
• Модель устройства
• Браузер и его версия (если проблема на сайте)
• Версия приложения (если проблема в приложении)

🔹 <b>Опишите саму проблему:</b>
• Что произошло?
• Какое сообщение об ошибке увидели?
• Что ожидали получить вместо этого?

📸 <b>Также вы можете прикрепить до 3 скриншотов</b> - это поможет нам быстрее понять проблему.

<b>Просто напишите подробное описание или отправьте фото с подписью:</b>
"""
        
        await update.message.reply_text(
            instruction_text,
            parse_mode='HTML',
            reply_markup=ReplyKeyboardMarkup([["🚫 Отмена"]], resize_keyboard=True)
        )
        context.user_data['state'] = UserState.AWAITING_QUESTION
        context.user_data['type'] = 'question'
        context.user_data['photos'] = []
        
    else:
        await update.message.reply_text(
            "Пожалуйста, выберите один из предложенных вариантов:",
            reply_markup=ReplyKeyboardMarkup([["🗣️ Оставить отзыв", "❓ Задать вопрос"]], resize_keyboard=True)
        )

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ввода отзыва - сохраняем в БД"""
    current_state = context.user_data.get('state')
    
    if current_state != UserState.AWAITING_FEEDBACK:
        from handlers.common_handlers import handle_unexpected_input
        await handle_unexpected_input(update, context)
        return
    
    feedback_text = update.message.text
    
    if "отмена" in feedback_text.lower():
        await cancel_operation(update, context)
        return
    
    # Сохраняем отзыв в базу данных
    user_id = update.effective_user.id
    feedback_id = db.add_feedback(user_id, feedback_text)
    
    await update.message.reply_text(
        "✅ Спасибо за ваш отзыв! 💙\n"
        "Мы ценим ваше мнение и обязательно его учтем.",
        reply_markup=ReplyKeyboardMarkup([["🗣️ Оставить отзыв", "❓ Задать вопрос"]], resize_keyboard=True)
    )
    
    print(f"Отзыв #{feedback_id} сохранен в БД от пользователя {user_id}")
    context.user_data['state'] = UserState.AWAITING_CHOICE

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик вопроса - текст, фото или фото с текстом"""
    current_state = context.user_data.get('state')
    
    if current_state != UserState.AWAITING_QUESTION:
        from handlers.common_handlers import handle_unexpected_input
        await handle_unexpected_input(update, context)
        return
    
    # Обработка отмены
    if update.message.text and "отмена" in update.message.text.lower():
        await cancel_operation(update, context)
        return
    
    user_id = update.effective_user.id
    question_text = ""
    photos = []
    
    # Обработка текстового вопроса (без фото)
    if update.message.text and not update.message.photo:
        question_text = update.message.text
        await process_question_complete(update, context, user_id, question_text, photos)
        return
    
    # Обработка фото с подписью (текстом вопроса)
    if update.message.photo and update.message.caption:
        question_text = update.message.caption
        # Получаем все фото из сообщения (может быть несколько в группе)
        for photo in update.message.photo:
            photos.append({
                'file_id': photo.file_id,
                'file_unique_id': photo.file_unique_id
            })
        # Ограничиваем до 3 фото
        photos = photos[:3]
        await process_question_complete(update, context, user_id, question_text, photos)
        return
    
    # Обработка фото без подписи
    if update.message.photo and not update.message.caption:
        # Проверяем, есть ли уже фото в контексте
        existing_photos = context.user_data.get('photos', [])
        
        # Добавляем новые фото (все из текущего сообщения)
        for photo in update.message.photo:
            if len(existing_photos) < 3:  # Максимум 3 фото
                existing_photos.append({
                    'file_id': photo.file_id,
                    'file_unique_id': photo.file_unique_id
                })
        
        context.user_data['photos'] = existing_photos
        
        if len(existing_photos) >= 3:
            await update.message.reply_text(
                "❌ Достигнут лимит в 3 фотографии.\n\n"
                "📝 Теперь опишите проблему текстом:\n"
                "• Шаги воспроизведения\n"
                "• Информация об устройстве\n"
                "• Описание ошибки"
            )
        else:
            remaining = 3 - len(existing_photos)
            await update.message.reply_text(
                f"✅ Фото добавлено! Осталось мест для фото: {remaining}\n\n"
                f"📝 Теперь опишите проблему текстом или отправьте еще фото с подписью:"
            )
        return
    
    # Обработка текста когда уже есть фото в контексте
    if update.message.text and context.user_data.get('photos'):
        question_text = update.message.text
        photos = context.user_data.get('photos', [])
        await process_question_complete(update, context, user_id, question_text, photos)
        return
    
    # Неподдерживаемый формат
    await update.message.reply_text(
        "❌ Пожалуйста, отправьте:\n"
        "• Текст с описанием проблемы\n"
        "• Или фото с подписью (описанием проблемы)\n"
        "• Или сначала фото, затем текст"
    )

async def process_question_complete(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                  user_id: int, question_text: str, photos: list):
    """Обрабатывает завершенный вопрос и сохраняет в БД"""
    
    if not question_text.strip():
        await update.message.reply_text(
            "❌ Описание проблемы не может быть пустым.\n\n"
            "📝 Пожалуйста, добавьте текст с описанием:\n"
            "• Шаги воспроизведения\n" 
            "• Информация об устройстве\n"
            "• Описание ошибки"
        )
        return
    
    # Сохраняем вопрос в базу данных
    question_id = db.add_question(user_id, question_text)
    
    # Сохраняем фотографии если есть
    for photo in photos:
        db.add_question_photo(question_id, photo['file_id'], photo['file_unique_id'])
    
    # Уведомляем модераторов
    await notify_moderators(update, context, question_id, question_text, photos)
    
    # Формируем сообщение для пользователя
    photos_count = len(photos)
    if photos_count == 0:
        photos_text = ""
    elif photos_count == 1:
        photos_text = " с 1 фото"
    else:
        photos_text = f" с {photos_count} фото"
    
    await update.message.reply_text(
        f"✅ Вопрос отправлен{photos_text}! 📩\n\n"
        "Мы получили ваше обращение и уже работаем над ним.\n"
        "Ответ придет вам в этот чат. Обычно мы отвечаем в течение 24 часов.",
        reply_markup=ReplyKeyboardMarkup([["🗣️ Оставить отзыв", "❓ Задать вопрос"]], resize_keyboard=True)
    )
    
    # Очищаем контекст
    context.user_data.clear()
    context.user_data['state'] = UserState.AWAITING_CHOICE

async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик отмены операции"""
    await update.message.reply_text(
        "Операция отменена. Что бы вы хотели сделать?",
        reply_markup=ReplyKeyboardMarkup([["🗣️ Оставить отзыв", "❓ Задать вопрос"]], resize_keyboard=True)
    )
    context.user_data.clear()
    context.user_data['state'] = UserState.AWAITING_CHOICE