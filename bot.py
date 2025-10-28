import logging, asyncio
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from config import Config

# Импорты обработчиков пользователей
from handlers.user_handlers import (
    start, 
    cancel_operation, 
    handle_choice,
    handle_feedback,
    handle_question
)

# Импорты обработчиков модераторов
from handlers.moderator_handlers import (
    add_moderator, 
    show_statistics,
    get_answer_conversation_handler
)

# Импорты общих обработчиков
from handlers.common_handlers import (
    handle_message,
    handle_unexpected_input,
    handle_unknown_command
)

def setup_handlers(application):
    """Настройка всех обработчиков"""
    
    # Добавляем ConversationHandler для ответов модераторов ПЕРВЫМ
    application.add_handler(get_answer_conversation_handler())
    
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel_operation))
    application.add_handler(CommandHandler("moderator", add_moderator))
    application.add_handler(CommandHandler("stats", show_statistics))
    
    # Обработчики выбора действия пользователя
    application.add_handler(MessageHandler(
        filters.TEXT & filters.Regex("^(🗣️ Оставить отзыв|❓ Задать вопрос)$"), 
        handle_choice
    ))
    
    # Главный обработчик текстовых сообщений
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        handle_message
    ))
    
    # Обработчик фотографий (для вопросов)
    application.add_handler(MessageHandler(
        filters.PHOTO,
        handle_message
    ))
    
    # Обработчик неизвестных команд
    application.add_handler(MessageHandler(
        filters.COMMAND,
        handle_unknown_command
    ))

async def start_bot():
    """Запуск бота (для использования в FastAPI)"""
    # Проверка токена
    if not Config.BOT_TOKEN:
        print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
        return
    
    # Создание приложения
    application = Application.builder().token(Config.BOT_TOKEN).build()
    
    # Настройка обработчиков
    setup_handlers(application)
    
    # Запуск бота
    print("🤖 Бот запущен...")
    print("⏹️  Для остановки нажмите Ctrl+C")
    
    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Бесконечный цикл для поддержания работы бота
        while True:
            await asyncio.sleep(3600)  # Спим 1 час
            
    except (KeyboardInterrupt, asyncio.CancelledError):
        print("\n🛑 Бот остановлен")
        if application.updater:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
    except Exception as e:
        print(f"❌ Ошибка при запуске бота: {e}")

def main():
    """Старая функция запуска для обратной совместимости"""
    import asyncio
    asyncio.run(start_bot())

if __name__ == '__main__':
    main()