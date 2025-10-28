from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
import html
import base64
import uuid
import os
import re
from io import BytesIO

from database.manager import DatabaseManager
from utils.helpers import notify_moderators_web, save_base64_image, extract_base64_from_img_tags
from config import Config

router = APIRouter()
db = DatabaseManager()

class PhotoData(BaseModel):
    ContentType: Optional[str] = None
    ContentDisposition: Optional[str] = None
    Headers: Optional[dict] = None
    Length: Optional[int] = None
    Name: Optional[str] = None
    FileName: Optional[str] = None

class WebQuestionRequest(BaseModel):
    Email: str
    Description: str
    Steps: str
    Photo1: Optional[Any] = None  # Может быть объектом или null
    Photo2: Optional[Any] = None
    Photo3: Optional[Any] = None
    DeviceInfo: str
    ImgTags: List[str] = []  # Список HTML img тегов с base64

class WebQuestionResponse(BaseModel):
    success: bool
    question_id: Optional[int] = None
    message: str

@router.post("/web-question", response_model=WebQuestionResponse)
async def create_question_from_web(request: WebQuestionRequest):
    """
    Создание вопроса из веб-формы с base64 фото в ImgTags
    """
    try:
        # Экранируем HTML символы для безопасности
        email = html.escape(request.Email)
        description = html.escape(request.Description)
        steps = html.escape(request.Steps)
        device_info = html.escape(request.DeviceInfo)
        
        # Формируем полный текст вопроса
        question_text = (
            f"📧 <b>Вопрос с сайта</b>\n"
            f"📨 Email: {email}\n\n"
            f"📝 <b>Описание проблемы:</b>\n{description}\n\n"
            f"🔹 <b>Шаги воспроизведения:</b>\n{steps.replace('<br>', '\n')}\n\n"
            f"💻 <b>Информация об устройстве:</b>\n{device_info.replace('<br>', '\n')}"
        )
        
        # Создаем запись в базе данных
        # Для веб-вопросов используем user_id = 0 (системный пользователь)
        question_id = db.add_question(0, question_text)
        
        # Извлекаем base64 данные из ImgTags
        base64_images = extract_base64_from_img_tags(request.ImgTags)
        
        # Обрабатываем base64 фото из ImgTags
        saved_photos = []
        photo_index = 0
        
        for photo_base64 in base64_images[:3]:  # Ограничиваем до 3 фото
            if photo_base64 and photo_base64.strip():
                try:
                    # Сохраняем base64 фото в файл
                    photo_path = save_base64_image(photo_base64, question_id, photo_index)
                    if photo_path:
                        saved_photos.append(photo_path)
                        photo_index += 1
                except Exception as e:
                    print(f"❌ Ошибка обработки фото: {e}")
                    # Продолжаем обработку даже если одно фото не сохранилось
        
        # Уведомляем модераторов
        await notify_moderators_web(question_id, question_text, saved_photos)
        
        return WebQuestionResponse(
            success=True,
            question_id=question_id,
            message="Вопрос успешно создан и отправлен модераторам"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при создании вопроса: {str(e)}"
        )

@router.get("/questions/{question_id}")
async def get_question_status(question_id: int):
    """Получение статуса вопроса"""
    try:
        question = db.get_question(question_id)
        if not question:
            raise HTTPException(status_code=404, detail="Вопрос не найден")
        
        status = db.get_question_status(question_id)
        answers = db.get_question_answers(question_id)
        
        return {
            "question_id": question_id,
            "status": status,
            "created_at": question[4],  # created_at поле
            "answers": answers
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при получении статуса вопроса: {str(e)}"
        )

# Добавляем экспорт router
api_router = router