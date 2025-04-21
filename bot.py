# redeploy trigger: cosmetic bump
import os
import logging
import subprocess
import tempfile
import re
import shutil
import asyncio
import sys
import mimetypes
import magic  # New import for detecting MIME types
import telegram
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from dotenv import load_dotenv
import json
import glob
from pathlib import Path
import traceback
from datetime import datetime
import io

# Загрузка переменных окружения (токен бота)
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING) # Уменьшаем шум от библиотеки httpx
logger = logging.getLogger(__name__)

# --- Define script path relative to bot.py ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PIPELINE_SCRIPT_PATH = os.path.join(SCRIPT_DIR, 'run_analysis_pipeline.py')

# Initialize MIME types
mimetypes.init()

# Состояния диалога
WAITING_IMAGE, WAITING_CONTEXT, ENTERING_CONTEXT, WAITING_USERFLOWS, ENTERING_USERFLOWS = range(5)

# --- Обработчики команд ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\n\n"
        f"Отправь мне изображение (скриншот интерфейса), и я проведу его анализ.\n"
        f"После этого у тебя будет возможность добавить описание и сценарии использования.\n"
        f"Используй команду /help для получения дополнительной информации.",
    )
    return WAITING_IMAGE

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    await update.message.reply_text(
        "Как использовать бота:\n\n"
        "1. Отправьте скриншот интерфейса 📱\n"
        "2. Выберите, хотите ли вы добавить описание того, что изображено на скриншоте (опционально) 📝\n"
        "3. Выберите, хотите ли вы добавить основные пользовательские сценарии (опционально) 🔄\n"
        "4. Дождитесь результатов анализа ⏳\n\n"
        "Я проведу когнитивный анализ интерфейса и предоставлю:\n"
        "- Стратегическую интерпретацию проблем 🧠\n"
        "- Рекомендации по улучшению 💡\n"
        "- PDF-отчет с детальным анализом 📊\n"
        "- Тепловую карту проблемных зон 🔥\n\n"
        "Команды:\n"
        "/start - Начать взаимодействие\n"
        "/cancel - Отменить текущий анализ\n"
        "/help - Показать эту справку"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel."""
    await update.message.reply_text(
        "Анализ отменен. Используйте /start, чтобы начать снова.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# --- Обработчик изображений ---

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает полученное изображение и переходит к запросу контекста."""
    message = update.message
    chat_id = update.effective_chat.id
    file_to_get = None
    file_unique_id = None
    file_extension = '.png' # Default extension

    photo = message.photo
    document = message.document

    if photo:
        # Process photo
        await message.reply_text("Фото получено.")
        try:
            file_to_get = await message.photo[-1].get_file()
            file_unique_id = file_to_get.file_unique_id
        except Exception as e:
            logger.error(f"Не удалось получить файл фото: {e}")
            await message.reply_text("Произошла ошибка при получении файла фото. Попробуйте еще раз.")
            return WAITING_IMAGE
    elif document and document.mime_type and document.mime_type.startswith('image/'):
        # Process document image
        await message.reply_text("Изображение (как документ) получено.")
        try:
            file_to_get = await document.get_file()
            file_unique_id = file_to_get.file_unique_id
            file_extension = mimetypes.guess_extension(document.mime_type) or '.png'
        except Exception as e:
            logger.error(f"Не удалось получить файл документа: {e}")
            await message.reply_text("Произошла ошибка при получении файла документа. Попробуйте еще раз.")
            return WAITING_IMAGE
    else:
        # Neither photo nor image document
        await message.reply_text("Пожалуйста, отправь изображение (как фото или как файл изображения).")
        return WAITING_IMAGE

    # Создаем временную директорию для изображения
    with tempfile.TemporaryDirectory() as temp_dir:
        # Use unique ID and determined extension for filename
        image_filename = f"input_image_{file_unique_id}{file_extension}"
        image_path = os.path.join(temp_dir, image_filename)
        try:
            await file_to_get.download_to_drive(image_path)
            logger.info(f"Изображение сохранено во временный файл: {image_path}")
            # Сохраняем путь к файлу в контексте для последующего использования
            context.user_data['image_path'] = image_path
            context.user_data['file_unique_id'] = file_unique_id
            context.user_data['temp_dir'] = temp_dir
        except Exception as e:
            logger.error(f"Не удалось скачать изображение: {e}")
            await message.reply_text("Произошла ошибка при сохранении изображения. Попробуйте еще раз.")
            return WAITING_IMAGE
    
    # Create keyboard with options for context
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пропустить")],
            [KeyboardButton(text="Ввести описание")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.reply_text(
        "Что изображено на скриншоте? Это поможет сделать анализ более точным.",
        reply_markup=keyboard
    )
    return WAITING_CONTEXT

async def handle_context_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя относительно добавления контекста."""
    text = update.message.text.strip()
    
    if text == "Пропустить":
        context.user_data['context'] = None
        return await offer_userflow_options(update, context)
    elif text == "Ввести описание":
        await update.message.reply_text(
            "Пожалуйста, опишите, что изображено на скриншоте:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ENTERING_CONTEXT
    else:
        context.user_data['context'] = text
        return await offer_userflow_options(update, context)

async def entering_context(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод контекста."""
    context.user_data['context'] = update.message.text
    return await offer_userflow_options(update, context)

async def offer_userflow_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Предлагает опции для добавления пользовательских сценариев."""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пропустить")],
            [KeyboardButton(text="Ввести сценарии")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await update.message.reply_text(
        "Какие основные пользовательские сценарии связаны с этим интерфейсом? Это поможет сделать анализ более релевантным.",
        reply_markup=keyboard
    )
    return WAITING_USERFLOWS

async def handle_userflow_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор пользователя относительно добавления пользовательских сценариев."""
    text = update.message.text.strip()
    
    if text == "Пропустить":
        context.user_data['userflows'] = None
        return await start_analysis(update, context)
    elif text == "Ввести сценарии":
        await update.message.reply_text(
            "Пожалуйста, опишите основные сценарии использования этого интерфейса:",
            reply_markup=ReplyKeyboardRemove()
        )
        return ENTERING_USERFLOWS
    else:
        context.user_data['userflows'] = text
        return await start_analysis(update, context)

async def entering_userflows(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод пользовательских сценариев."""
    context.user_data['userflows'] = update.message.text
    return await start_analysis(update, context)

async def start_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает анализ интерфейса."""
    await update.message.reply_text(
        "Спасибо! Начинаю анализ интерфейса... Это может занять несколько минут ⏳",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # Получаем сохраненные данные
    image_path = context.user_data.get('image_path')
    user_context = context.user_data.get('context')
    userflows = context.user_data.get('userflows')
    
    # Запускаем процесс анализа с пайплайном
    # Здесь должна быть логика запуска run_analysis_pipeline.py с передачей контекста и userflows
    try:
        # Копируем существующую функциональность handle_image, но с учетом уже полученного изображения
        # и добавлением контекста и пользовательских сценариев
        
        # Check if pipeline script exists
        if not os.path.exists(PIPELINE_SCRIPT_PATH):
            logger.error(f"Скрипт анализа не найден по пути: {PIPELINE_SCRIPT_PATH}")
            await update.message.reply_text("Критическая ошибка: не найден скрипт анализа на сервере.")
            return ConversationHandler.END

        logger.info(f"Запуск {PIPELINE_SCRIPT_PATH} для {image_path}")
        
        # Подготовка команды для запуска пайплайна с доп. параметрами
        cmd = [sys.executable, PIPELINE_SCRIPT_PATH, image_path]
        # Добавляем контекст и пользовательские сценарии как аргументы, если они указаны
        if user_context:
            cmd.extend(["--context", user_context])
        if userflows:
            cmd.extend(["--userflows", userflows])
            
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        stdout_str = stdout.decode('utf-8', errors='ignore')
        stderr_str = stderr.decode('utf-8', errors='ignore')

        logger.info(f"{PIPELINE_SCRIPT_PATH} завершился с кодом {process.returncode}")
        
        # Обработка результатов, как в оригинальном коде
        # ... логика обработки и отправки результатов
        
        # Обрабатываем результаты и отправляем сообщения пользователю
        await update.message.reply_text("Анализ завершен! Отправляю результаты...")
        
        # Здесь добавьте код для обработки и отправки результатов пользователю
        # Этот код должен быть заимствован из существующей логики
        
    except Exception as e:
        logger.error(f"Error during analysis: {e}")
        traceback.print_exc()
        await update.message.reply_text(f"Произошла ошибка при анализе: {e}")
    
    return ConversationHandler.END


# --- Обработчик ошибок ---

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки, вызванные обновлениями."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

# --- Основная функция ---

def main():
    """Запуск бота."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Не найден токен TELEGRAM_BOT_TOKEN в переменных окружения.")
        return

    # Создание приложения и передача токена
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрация обработчиков команд и сообщений через ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_IMAGE: [
                MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image)
            ],
            WAITING_CONTEXT: [
                MessageHandler(filters.TEXT, handle_context_choice)
            ],
            ENTERING_CONTEXT: [
                MessageHandler(filters.TEXT, entering_context)
            ],
            WAITING_USERFLOWS: [
                MessageHandler(filters.TEXT, handle_userflow_choice)
            ],
            ENTERING_USERFLOWS: [
                MessageHandler(filters.TEXT, entering_userflows)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("help", help_command))
    
    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)
    
    # Запуск бота
    logger.info("Запуск бота...")
    application.run_polling()

if __name__ == "__main__":
    main()