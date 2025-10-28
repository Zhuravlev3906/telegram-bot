import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

from bot import start_bot
from api.handlers import api_router
from config import Config

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запуск и остановка бота вместе с FastAPI"""
    # Запускаем бота в фоне
    bot_task = asyncio.create_task(start_bot())
    
    yield
    
    # Останавливаем бот при завершении приложения
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass

# Создание FastAPI приложения
app = FastAPI(
    title="Feedback Bot API",
    description="API для приема обращений с сайта и Telegram бота",
    version="1.0.0",
    lifespan=lifespan
)

# Подключаем роутеры
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Feedback Bot API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )