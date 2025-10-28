from telegram import Update, ReplyKeyboardRemove, InputMediaPhoto
from telegram.ext import ContextTypes, MessageHandler, filters, ConversationHandler, CommandHandler
from database.manager import DatabaseManager
from config import Config
from utils.helpers import notify_moderators_about_taken_question

db = DatabaseManager()

# Состояния для ConversationHandler
AWAITING_ANSWER = 1

async def add_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда для добавления модератора"""
    user = update.effective_user
    
    # Проверка прав администратора
    if user.id not in Config.ADMIN_IDS:
        await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
        return
    
    db.add_moderator(user.id, user.username, user.first_name)
    
    await update.message.reply_text(
        "✅ Вы добавлены как модератор! Теперь вы будете получать уведомления о новых вопросах."
    )

async def start_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало ответа на вопрос"""
    message_text = update.message.text
    moderator_id = update.effective_user.id
    
    try:
        question_id = int(message_text.split('_')[1])
        
        # Проверяем, может ли текущий модератор взять вопрос в работу
        if not db.set_question_in_progress(question_id, moderator_id):
            # Вопрос уже взят другим модератором
            current_moderator_id = db.get_question_moderator(question_id)
            if current_moderator_id:
                await update.message.reply_text(
                    f"⚠️ Вопрос #Q{question_id} уже взят в работу другим модератором."
                )
            else:
                await update.message.reply_text(
                    f"❌ Вопрос #Q{question_id} уже отвечен или не найден."
                )
            return ConversationHandler.END
                
        # Получаем информацию о вопросе
        question = db.get_question(question_id)
        if not question:
            await update.message.reply_text("❌ Вопрос не найден.")
            db.release_question_lock(question_id)  # Освобождаем блокировку
            return ConversationHandler.END
        
        # Уведомляем других модераторов о том, что вопрос взят в работу
        moderator_name = update.effective_user.first_name
        await notify_moderators_about_taken_question(question_id, moderator_name, context)
        
        # Получаем фотографии вопроса если есть
        photos = db.get_question_photos(question_id)
        
        response_text = (
            f"✏️ Вы отвечаете на вопрос #Q{question_id}\n"
            f"От: {question[5]} (@{question[4] if question[4] else 'без username'})\n"
            f"ID пользователя: {question[1]}\n\n"
            f"❓ Вопрос:\n{question[2]}\n\n"
        )
        
        if photos:
            if len(photos) == 1:
                # Отправляем одно фото с подписью
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photos[0][0],  # file_id
                    caption=response_text + "📷 К вопросу прикреплено 1 фото\n\n📝 Пожалуйста, напишите ваш ответ (или /cancel для отмены):"
                )
            else:
                # Отправляем альбом с фото
                media_group = []
                
                # Первое фото с подписью
                media_group.append(
                    InputMediaPhoto(
                        media=photos[0][0],
                        caption=response_text + f"📷 К вопросу прикреплено {len(photos)} фото\n\n📝 Пожалуйста, напишите ваш ответ (или /cancel для отмены):"
                    )
                )
                
                # Остальные фото без подписи
                for photo in photos[1:]:
                    media_group.append(InputMediaPhoto(media=photo[0]))
                
                await context.bot.send_media_group(
                    chat_id=update.effective_chat.id,
                    media=media_group
                )
        else:
            # Без фото - просто текст
            response_text += "📝 Пожалуйста, напишите ваш ответ (или /cancel для отмены):"
            await update.message.reply_text(response_text, reply_markup=ReplyKeyboardRemove())
        
        # Сохраняем ID вопроса в context
        context.user_data['answering_question_id'] = question_id
        
        return AWAITING_ANSWER
        
    except (IndexError, ValueError):
        await update.message.reply_text("❌ Неверный формат команды. Используйте: /answer_123")
        return ConversationHandler.END

async def receive_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получение ответа от модератора"""
    answer_text = update.message.text
    question_id = context.user_data.get('answering_question_id')
    moderator_id = update.effective_user.id
    
    if not question_id:
        await update.message.reply_text("❌ Ошибка: вопрос не найден в контексте.")
        return ConversationHandler.END
    
    # Проверяем, что текущий модератор все еще владеет вопросом
    current_moderator_id = db.get_question_moderator(question_id)
    if current_moderator_id != moderator_id:
        await update.message.reply_text(
            f"⚠️ Вопрос #Q{question_id} уже взят другим модератором. Ответ не будет отправлен."
        )
        context.user_data.pop('answering_question_id', None)
        return ConversationHandler.END
        
    # Получаем информацию о вопросе
    question = db.get_question(question_id)
    if not question:
        await update.message.reply_text("❌ Вопрос не найден в базе данных.")
        context.user_data.pop('answering_question_id', None)
        return ConversationHandler.END
    
    user_id = question[1]  # ID пользователя, задавшего вопрос
    
    try:
        # Отправляем ответ пользователю
        user_response_text = (
            f"📧 Ответ на ваш вопрос #Q{question_id}:\n\n"
            f"{answer_text}\n\n"
            f"💬 Если у вас есть дополнительные вопросы, просто задайте их через бота!"
        )
        
        await context.bot.send_message(
            chat_id=user_id,
            text=user_response_text
        )
        
        # Сохраняем ответ в базу данных
        answer_id = db.add_answer(question_id, moderator_id, answer_text)
        db.update_question_status(question_id, 'answered')
        
        # Очищаем контекст
        context.user_data.pop('answering_question_id', None)
        
        await update.message.reply_text(
            f"✅ Ответ #A{answer_id} успешно отправлен пользователю!",
            reply_markup=ReplyKeyboardRemove()
        )
        
        print(f"✅ Ответ #{answer_id} отправлен пользователю {user_id} (Вопрос #{question_id})")
        
    except Exception as e:
        error_message = f"❌ Ошибка при отправке ответа: {e}"
        print(error_message)
        
        # Более детальная диагностика ошибки
        if "chat not found" in str(e) or "bot was blocked" in str(e):
            error_message += "\n\n⚠️ Пользователь заблокировал бота или чат не найден."
        elif "Forbidden" in str(e):
            error_message += "\n\n⚠️ У бота нет прав для отправки сообщения этому пользователю."
        
        await update.message.reply_text(error_message)
        
        # Все равно сохраняем ответ в БД, но отмечаем ошибку
        try:
            answer_id = db.add_answer(question_id, moderator_id, answer_text)
            db.update_question_status(question_id, 'error')
            print(f"📁 Ответ #{answer_id} сохранен в БД, но не доставлен пользователю")
        except Exception as db_error:
            print(f"❌ Ошибка сохранения в БД: {db_error}")
    
    return ConversationHandler.END

async def cancel_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена ответа на вопрос"""
    question_id = context.user_data.get('answering_question_id')
    
    if question_id:
        # Освобождаем блокировку вопроса
        db.release_question_lock(question_id)
        context.user_data.pop('answering_question_id', None)
    
    await update.message.reply_text(
        "❌ Ответ отменен.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def show_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать статистику для модераторов"""
    # TODO: Реализовать сбор статистики из БД
    stats_text = (
        "📊 Статистика обратной связи:\n"
        "• Новых вопросов: 0\n"
        "• Всего отзывов: 0\n"
        "• Ответов отправлено: 0"
    )
    
    await update.message.reply_text(stats_text)

# Создаем ConversationHandler для ответов модераторов
def get_answer_conversation_handler():
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.TEXT & filters.Regex(r'^/answer_\d+'), start_answer)
        ],
        states={
            AWAITING_ANSWER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_answer)
            ]
        },
        fallbacks=[
            CommandHandler('cancel', cancel_answer)
        ]
    )