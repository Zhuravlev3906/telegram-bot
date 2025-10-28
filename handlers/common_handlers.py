from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from states.user_states import UserState

async def handle_unexpected_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик неожиданного ввода"""
    # Пропускаем сообщения, которые обрабатываются ConversationHandler модераторов
    if context.user_data.get('answering_question_id'):
        return
        
    current_state = context.user_data.get('state')
    
    if current_state == UserState.AWAITING_QUESTION:
        # В состоянии ожидания вопроса показываем соответствующие кнопки
        await update.message.reply_text(
            "Пожалуйста, отправьте текст вопроса или фото с подписью:",
            reply_markup=ReplyKeyboardMarkup([
                ["🚫 Отмена"]
            ], resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "Пожалуйста, используйте кнопки для навигации. Что бы вы хотели сделать?",
            reply_markup=ReplyKeyboardMarkup([["🗣️ Оставить отзыв", "❓ Задать вопрос"]], resize_keyboard=True)
        )
        context.user_data['state'] = UserState.AWAITING_CHOICE

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Главный обработчик сообщений с маршрутизацией по состояниям"""
    # Пропускаем сообщения, которые уже обработаны ConversationHandler
    if context.user_data.get('answering_question_id'):
        return
        
    current_state = context.user_data.get('state')
    
    if current_state == UserState.AWAITING_FEEDBACK:
        from handlers.user_handlers import handle_feedback
        await handle_feedback(update, context)
    elif current_state == UserState.AWAITING_QUESTION:
        from handlers.user_handlers import handle_question
        await handle_question(update, context)
    else:
        from handlers.user_handlers import handle_choice
        await handle_choice(update, context)

async def handle_unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик неизвестных команд"""
    # Пропускаем команды, которые обрабатываются ConversationHandler модераторов
    if context.user_data.get('answering_question_id'):
        return
        
    await update.message.reply_text(
        "❌ Неизвестная команда. Используйте /start для начала работы.",
        reply_markup=ReplyKeyboardMarkup([["🗣️ Оставить отзыв", "❓ Задать вопрос"]], resize_keyboard=True)
    )