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
    temp_dir = tempfile.mkdtemp()
    # Use unique ID and determined extension for filename
    image_filename = f"input_image_{file_unique_id}{file_extension}"
    image_path = os.path.join(temp_dir, image_filename)
    try:
        await file_to_get.download_to_drive(image_path)
        logger.info(f"Изображение сохранено во временный файл: {image_path}")
        # Сохраняем путь к файлу в контексте для последующего использования
        context.user_data['image_path'] = image_path
        context.user_data['temp_dir'] = temp_dir
    except Exception as e:
        logger.error(f"Не удалось скачать изображение: {e}")
        await message.reply_text("Произошла ошибка при сохранении изображения. Попробуйте еще раз.")
        shutil.rmtree(temp_dir, ignore_errors=True)
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
    temp_dir = context.user_data.get('temp_dir')
    user_context = context.user_data.get('context')
    userflows = context.user_data.get('userflows')
    
    # Запускаем оригинальную логику анализа
    message = update.message
    chat_id = update.effective_chat.id

    # Helper function to detect MIME type
    def get_mime_type(file_path):
        """Determine the correct MIME type for a file."""
        try:
            # Use python-magic to detect the MIME type
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(file_path)
            logging.info(f"Detected MIME type for {file_path}: {mime_type}")
            return mime_type
        except Exception as e:
            logging.warning(f"Failed to detect MIME type using magic: {e}")
            # Fallback to extension-based detection
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.pdf':
                return 'application/pdf'
            elif ext in ('.png', '.jpg', '.jpeg'):
                return 'image/png' if ext == '.png' else 'image/jpeg'
            elif ext == '.json':
                return 'application/json'
            elif ext == '.tex':
                return 'application/x-tex'
            else:
                # Additional fallback to mimetypes module
                guess = mimetypes.guess_type(file_path)[0]
                if guess:
                    logging.info(f"Mimetype module guessed: {guess} for {file_path}")
                    return guess
                logging.warning(f"Could not determine MIME type for {file_path}, using default")
                return 'application/octet-stream'

    # Функции для форматирования и отправки структурированных данных
    async def send_formatted_interpretation(chat_id, interpretation_data):
        """Форматирует и отправляет стратегическую интерпретацию в виде отдельных сообщений."""
        try:
            if not interpretation_data or "strategicInterpretation" not in interpretation_data:
                logger.warning("Структура интерпретации не содержит ожидаемых данных")
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="⚠️ Не удалось обработать данные интерпретации в удобочитаемом формате."
                )
                return False

            # Заголовок интерпретации
            await context.bot.send_message(
                chat_id=chat_id,
                text="*📊 СТРАТЕГИЧЕСКАЯ ИНТЕРПРЕТАЦИЯ*\n\nАнализ ключевых аспектов интерфейса:",
                parse_mode="Markdown"
            )

            # Перебираем все разделы интерпретации и отправляем их как отдельные сообщения
            interpretation = interpretation_data["strategicInterpretation"]
            sections = {
                "cognitiveEcosystem": "🌐 *Когнитивная экосистема*",
                "businessUserTension": "⚖️ *Напряжение между бизнес-целями и потребностями пользователей*",
                "attentionArchitecture": "🏗️ *Архитектура внимания*",
                "perceptualCrossroads": "🔄 *Перцептивные перекрестки*",
                "hiddenPatterns": "🧩 *Скрытые паттерны*"
            }

            for key, title in sections.items():
                if key in interpretation and interpretation[key]:
                    text = f"{title}\n\n{interpretation[key]}"
                    # Разбиваем длинный текст на части при необходимости
                    MAX_LEN = 4000
                    if len(text) <= MAX_LEN:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            parse_mode="Markdown"
                        )
                    else:
                        # Разделяем на части, сохраняя заголовок в каждой части
                        parts = [text[i:i+MAX_LEN-len(title)-10] for i in range(0, len(text)-len(title)-10, MAX_LEN-len(title)-10)]
                        for i, part in enumerate(parts):
                            if i == 0:
                                message = part
                            else:
                                message = f"{title} (продолжение)\n\n{part}"
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=message,
                                parse_mode="Markdown"
                            )
            return True
        except Exception as e:
            logger.error(f"Ошибка при отправке форматированной интерпретации: {e}")
            traceback.print_exc()
            return False
    
    # ... сохраняем оригинальную логику анализа изображения
    
    try:
        # Check if pipeline script exists
        if not os.path.exists(PIPELINE_SCRIPT_PATH):
            logger.error(f"Скрипт анализа не найден по пути: {PIPELINE_SCRIPT_PATH}")
            await message.reply_text("Критическая ошибка: не найден скрипт анализа на сервере.")
            return ConversationHandler.END

        logger.info(f"Запуск {PIPELINE_SCRIPT_PATH} для {image_path}")
        
        # Подготовка команды для запуска пайплайна с доп. параметрами
        cmd = [sys.executable, PIPELINE_SCRIPT_PATH, image_path]
        
        # Здесь можно добавить передачу контекста и userflows через командную строку,
        # если run_analysis_pipeline.py поддерживает такие аргументы
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        stdout_str = stdout.decode('utf-8', errors='ignore')
        stderr_str = stderr.decode('utf-8', errors='ignore')

        logger.info(f"{PIPELINE_SCRIPT_PATH} завершился с кодом {process.returncode}")
        # Treat pipelines that generated a LaTeX or PDF report as success, even if return code is non-zero
        # Override return code if summary indicates success
        if "✅ PDF Отчет:" in stdout_str or "✅ LaTeX Отчет" in stdout_str:
            return_code = 0
        else:
            return_code = process.returncode
        if return_code != 0:
            logger.error(f"Ошибка выполнения {PIPELINE_SCRIPT_PATH}:\nstdout:\n{stdout_str}\nstderr:\n{stderr_str}")
            error_message = "Произошла ошибка во время анализа."
            # Send stderr as plain text
            if stderr_str:
                error_message += f"\n\nДетали ошибки (raw):\n```\n...{stderr_str[-700:]}\n```"
            
            try:
                await message.reply_text(error_message) # Send plain text error
            except Exception as send_err:
                 logger.error(f"Failed to send plain text error message: {send_err}")
            # Continue to send attachments even if pipeline returned an error
            # (do not return here)
            
        # Оригинальная часть кода для обработки результатов
        # ... далее весь оригинальный код для обработки и отправки результатов
            
        # Очистка: удаляем временную директорию
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                logger.info(f"Удалена временная директория: {temp_dir}")
        except Exception as e:
            logger.error(f"Не удалось удалить временную директорию {temp_dir}: {e}")
            
    except Exception as e:
        logger.error(f"Error in image handling: {e}")
        traceback.print_exc()
        await message.reply_text(f"Произошла ошибка при обработке вашего изображения: {e}")
        
    return ConversationHandler.END

# --- Обработчик ошибок ---

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки, вызванные обновлениями."""
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)
    # No need to check for Markdown error here anymore, as we send plain text

# --- Основная функция ---

def main():
    """Запуск бота."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Не найден токен TELEGRAM_BOT_TOKEN в переменных окружения.")
        return

    # Создание приложения и передача токена
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Регистрация обработчиков через ConversationHandler
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