# redeploy trigger: fix detection - roll back to stable version
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
from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, 
    ConversationHandler, CallbackQueryHandler
)
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

# Define conversation states
GET_TYPE, WAIT_TYPE, GET_SCENARIO, WAIT_SCENARIO = range(4)

# --- Обработчики команд ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start."""
    user = update.effective_user
    await update.message.reply_html(
        f"Привет, {user.mention_html()}!\n\n"
        f"Отправь мне изображение (скриншот интерфейса), и я проведу его анализ.\n"
        f"Используй команду /help для получения дополнительной информации.",
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help."""
    await update.message.reply_text(
        "Как использовать бота:\n"
        "1. Отправь мне изображение (скриншот) интерфейса, который нужно проанализировать (как фото или как файл).\n"
        "2. Я запущу полный пайплайн анализа (GPT-4, Gemini Coordinates, Heatmap, Report).\n"
        "3. В ответ я пришлю PDF-отчет и тепловую карту.\n\n"
        "Пожалуйста, отправляй только одно изображение за раз."
    )

# --- Обработчик изображений / Начало диалога ---

async def start_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начинает диалог после получения изображения, сохраняет его и спрашивает тип интерфейса."""
    message = update.message
    chat_id = update.effective_chat.id
    file_to_get = None
    file_unique_id = None
    file_extension = '.png' # Default extension

    photo = message.photo
    document = message.document

    if photo:
        # Process photo
        await message.reply_text("Фото получено. 👍 Теперь задам пару уточняющих вопросов...")
        try:
            file_to_get = await message.photo[-1].get_file()
            file_unique_id = file_to_get.file_unique_id
        except Exception as e:
            logger.error(f"Не удалось получить файл фото: {e}")
            await message.reply_text("Произошла ошибка при получении файла фото. Попробуйте еще раз.")
            return ConversationHandler.END
    elif document and document.mime_type and document.mime_type.startswith('image/'):
        # Process document image
        await message.reply_text("Изображение получено. 👍 Теперь задам пару уточняющих вопросов...")
        try:
            file_to_get = await document.get_file()
            file_unique_id = file_to_get.file_unique_id
            file_extension = mimetypes.guess_extension(document.mime_type) or '.png'
        except Exception as e:
            logger.error(f"Не удалось получить файл документа: {e}")
            await message.reply_text("Произошла ошибка при получении файла документа. Попробуйте еще раз.")
            return ConversationHandler.END
    else:
        # Should not happen if handler filters are correct, but as a safeguard
        await message.reply_text("Пожалуйста, отправь изображение (как фото или как файл изображения).")
        return ConversationHandler.END

    # Создаем директорию для пользовательских изображений, если ее нет
    user_images_dir = os.path.join(SCRIPT_DIR, "user_images")
    os.makedirs(user_images_dir, exist_ok=True)

    # Сохраняем изображение в user_images/
    image_filename = f"input_image_{file_unique_id}{file_extension}"
    image_path = os.path.join(user_images_dir, image_filename)
    try:
        await file_to_get.download_to_drive(image_path)
        logger.info(f"Изображение сохранено в: {image_path}")
    except Exception as e:
        logger.error(f"Не удалось скачать изображение: {e}")
        await message.reply_text("Произошла ошибка при сохранении изображения. Попробуйте еще раз.")
        return ConversationHandler.END

    # Сохраняем путь к изображению в user_data
    context.user_data['image_path'] = image_path
    logger.info(f"Сохранен image_path в user_data: {context.user_data['image_path']}")
    context.user_data['interface_type'] = None # Инициализируем
    context.user_data['user_scenario'] = None  # Инициализируем

    # Спрашиваем про тип интерфейса
    keyboard = [
        [InlineKeyboardButton("Указать тип", callback_data='specify_type')],
        [InlineKeyboardButton("Пропустить", callback_data='skip_type')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(
        "Хотите указать тип анализируемого интерфейса? (например, 'страница результатов поиска', 'форма регистрации', 'панель управления')\nЭто поможет сделать анализ точнее.",
        reply_markup=reply_markup
    )

    return GET_TYPE

# --- Остальные обработчики диалога будут добавлены ниже ---

async def ask_scenario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запрашивает сценарий использования."""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Указать сценарий", callback_data='specify_scenario')],
        [InlineKeyboardButton("Пропустить", callback_data='skip_scenario')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text="Хотите указать типичный сценарий использования этого интерфейса? (например, 'поиск товара', 'заполнение профиля')\nЭто также поможет анализу.",
        reply_markup=reply_markup
    )
    return GET_SCENARIO

async def ask_type_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ответ на кнопку 'Указать тип'. Просит пользователя ввести текст."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="Пожалуйста, введите тип интерфейса:")
    return WAIT_TYPE

async def received_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет введенный тип интерфейса и запрашивает сценарий."""
    user_type = update.message.text
    context.user_data['interface_type'] = user_type
    logger.info(f"Получен тип интерфейса: {user_type}")
    await update.message.reply_text(f"Тип интерфейса '{user_type}' сохранен.")

    # Теперь запрашиваем сценарий, отправляя новое сообщение с кнопками
    keyboard = [
        [InlineKeyboardButton("Указать сценарий", callback_data='specify_scenario')],
        [InlineKeyboardButton("Пропустить", callback_data='skip_scenario')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        text="Хотите указать типичный сценарий использования этого интерфейса? (например, 'поиск товара', 'заполнение профиля')\nЭто также поможет анализу.",
        reply_markup=reply_markup
    )

    # Переходим в состояние ожидания ответа на вопрос о сценарии
    return GET_SCENARIO

async def skip_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает пропуск ввода типа интерфейса и переходит к запросу сценария."""
    query = update.callback_query
    await query.answer()
    context.user_data['interface_type'] = None # Или можно использовать "Не указан"
    logger.info("Пользователь пропустил ввод типа интерфейса.")
    # Переходим к следующему шагу - запросу сценария
    # Важно: используем query.message для передачи update в ask_scenario, т.к. update здесь - это CallbackQuery
    # Если update.message не существует (например, если это было первое сообщение), используем query.message
    responder_message = getattr(update, 'message', query.message)
    return await ask_scenario(responder_message, context)

async def start_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Запускает пайплайн анализа с собранными данными."""
    logger.info("--- Начинается этап запуска анализа ---")
    responder = update.message if hasattr(update, 'message') else update.callback_query.message
    chat_id = responder.chat_id

    image_path = context.user_data.get('image_path')
    # Используем 'Не указан' если значение None или пустая строка
    interface_type = context.user_data.get('interface_type') or 'Не указан'
    user_scenario = context.user_data.get('user_scenario') or 'Не указан'

    logger.info(f"Данные для анализа: image_path={image_path}, interface_type='{interface_type}', user_scenario='{user_scenario}'")

    if not image_path or not os.path.exists(image_path):
        logger.error("Ошибка: путь к изображению не найден в user_data или файл не существует.")
        await responder.reply_text("Критическая ошибка: не удалось найти сохраненное изображение. Попробуйте начать заново.")
        context.user_data.clear()
        return ConversationHandler.END

    # --- Запуск пайплайна анализа ---
    message_text = "Отлично! Все данные собраны. Запускаю полный анализ изображения..."
    if interface_type != 'Не указан':
        message_text += f"\nТип: {interface_type}"
    if user_scenario != 'Не указан':
        message_text += f"\nСценарий: {user_scenario}"
    message_text += "\nЭто может занять около 10 минут. Пожалуйста, подождите... ⏳"
    await responder.reply_text(message_text)

    try:
        # Проверяем существование скрипта пайплайна
        if not os.path.exists(PIPELINE_SCRIPT_PATH):
            logger.error(f"Скрипт пайплайна не найден по пути: {PIPELINE_SCRIPT_PATH}")
            await responder.reply_text("Ошибка: Не удалось найти скрипт анализа. Обратитесь к администратору.")
            context.user_data.clear()
            return ConversationHandler.END

        # Формируем команду для запуска
        command = [
            sys.executable,  # Используем тот же python, что и для бота
            PIPELINE_SCRIPT_PATH,
            '--image-path', image_path,
            '--interface-type', interface_type,
            '--user-scenario', user_scenario
        ]
        logger.info(f"Запуск команды: {' '.join(command)}")

        # Запускаем пайплайн асинхронно
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate() # Ждем завершения
        stdout_decoded = stdout.decode().strip() if stdout else ""
        stderr_decoded = stderr.decode().strip() if stderr else ""


        if process.returncode == 0:
            logger.info(f"Пайплайн успешно завершен для {image_path}.")
            if stdout_decoded: logger.info(f"Pipeline stdout:\n{stdout_decoded}")
            if stderr_decoded: logger.warning(f"Pipeline stderr:\n{stderr_decoded}") # Логируем stderr даже при успехе

            # --- Поиск и отправка результатов ---
            image_path_obj = Path(image_path)
            base_filename = image_path_obj.stem # Имя файла без расширения
            results_dir = image_path_obj.parent # Директория с исходным изображением

            # Ищем PDF, PNG и JSON файлы с тем же базовым именем + суффиксами
            pdf_report_pattern = f"{base_filename}_report.pdf"
            heatmap_pattern = f"{base_filename}_heatmap.png"
            interpretation_pattern = f"{base_filename}_interpretation.json"
            recommendations_pattern = f"{base_filename}_recommendations.json"

            pdf_files = list(results_dir.glob(pdf_report_pattern))
            heatmap_files = list(results_dir.glob(heatmap_pattern))
            interpretation_files = list(results_dir.glob(interpretation_pattern))
            recommendations_files = list(results_dir.glob(recommendations_pattern))

            logger.info(f"Поиск результатов: PDF='{pdf_report_pattern}', Heatmap='{heatmap_pattern}', Interpretation='{interpretation_pattern}', Recommendations='{recommendations_pattern}' в '{results_dir}'")

            sent_files_count = 0 # Счетчик успешно отправленных файлов
            sent_files = False
            if pdf_files:
                pdf_path = str(pdf_files[0])
                try:
                    logger.info(f"Отправка PDF отчета: {pdf_path}")
                    with open(pdf_path, 'rb') as pdf_file:
                         await context.bot.send_document(chat_id=chat_id, document=pdf_file, connect_timeout=60, read_timeout=60)
                    sent_files = True
                    sent_files_count += 1
                except telegram.error.NetworkError as ne:
                     logger.error(f"Ошибка сети при отправке PDF отчета: {ne}. Попытка увеличения таймаута.")
                     try:
                         with open(pdf_path, 'rb') as pdf_file:
                             await context.bot.send_document(chat_id=chat_id, document=pdf_file, connect_timeout=120, read_timeout=120)
                         sent_files = True
                         sent_files_count += 1
                     except Exception as e_retry:
                         logger.error(f"Повторная ошибка отправки PDF: {e_retry}")
                         await responder.reply_text("Не удалось отправить PDF отчет из-за проблем с сетью.")

                except Exception as e:
                    logger.error(f"Ошибка отправки PDF отчета: {e}", exc_info=True)
                    await responder.reply_text("Не удалось отправить PDF отчет.")
            else:
                logger.warning(f"PDF отчет не найден для {base_filename} в {results_dir}")
                # Debug: list files in dir
                try:
                    files_in_dir = os.listdir(results_dir)
                    logger.debug(f"Файлы в директории {results_dir}: {files_in_dir}")
                except Exception as list_e:
                    logger.error(f"Не удалось прочитать директорию {results_dir}: {list_e}")


            if heatmap_files:
                heatmap_path = str(heatmap_files[0])
                try:
                    logger.info(f"Отправка тепловой карты (как документа): {heatmap_path}")
                    with open(heatmap_path, 'rb') as hm_file:
                        await context.bot.send_document(chat_id=chat_id, document=hm_file, connect_timeout=60, read_timeout=60)
                    sent_files = True
                    sent_files_count += 1
                except telegram.error.NetworkError as ne:
                     logger.error(f"Ошибка сети при отправке документа тепловой карты: {ne}. Попытка увеличения таймаута.")
                     try:
                         with open(heatmap_path, 'rb') as hm_file:
                             await context.bot.send_document(chat_id=chat_id, document=hm_file, connect_timeout=120, read_timeout=120)
                         sent_files = True
                         sent_files_count += 1
                     except Exception as e_retry:
                         logger.error(f"Повторная ошибка отправки документа тепловой карты: {e_retry}")
                         await responder.reply_text("Не удалось отправить тепловую карту из-за проблем с сетью.")

                except Exception as e:
                    logger.error(f"Ошибка отправки документа тепловой карты: {e}", exc_info=True)
                    await responder.reply_text("Не удалось отправить тепловую карту.")
            else:
                logger.warning(f"Тепловая карта не найдена для {base_filename} в {results_dir}")
                 # Debug: list files in dir (if not already done for PDF)
                if not pdf_files: # Avoid listing twice if both are missing
                    try:
                        files_in_dir = os.listdir(results_dir)
                        logger.debug(f"Файлы в директории {results_dir}: {files_in_dir}")
                    except Exception as list_e:
                        logger.error(f"Не удалось прочитать директорию {results_dir}: {list_e}")

            # Отправка JSON интерпретации
            if interpretation_files:
                interpretation_path = str(interpretation_files[0])
                try:
                    logger.info(f"Отправка JSON интерпретации: {interpretation_path}")
                    with open(interpretation_path, 'rb') as interp_file:
                         await context.bot.send_document(chat_id=chat_id, document=interp_file, caption="JSON с интерпретацией анализа", connect_timeout=60, read_timeout=60)
                    sent_files_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки JSON интерпретации: {e}", exc_info=True)
                    await responder.reply_text("Не удалось отправить файл JSON с интерпретацией.")
            else:
                logger.warning(f"JSON интерпретации не найден для {base_filename} в {results_dir}")

            # Отправка JSON рекомендаций
            if recommendations_files:
                recommendations_path = str(recommendations_files[0])
                try:
                    logger.info(f"Отправка JSON рекомендаций: {recommendations_path}")
                    with open(recommendations_path, 'rb') as rec_file:
                         await context.bot.send_document(chat_id=chat_id, document=rec_file, caption="JSON с рекомендациями", connect_timeout=60, read_timeout=60)
                    sent_files_count += 1
                except Exception as e:
                    logger.error(f"Ошибка отправки JSON рекомендаций: {e}", exc_info=True)
                    await responder.reply_text("Не удалось отправить файл JSON с рекомендациями.")
            else:
                logger.warning(f"JSON рекомендаций не найден для {base_filename} в {results_dir}")


            # Обновленное сообщение об отсутствии файлов
            if sent_files_count == 0:
                 await responder.reply_text("Анализ завершен, но не удалось найти файлы результатов (PDF, тепловая карта, JSON). Проверьте логи.")
            elif sent_files_count < 4: # Если отправлены не все 4 файла (PDF, PNG, 2xJSON)
                 await responder.reply_text("Анализ завершен, но не все файлы результатов удалось отправить. Проверьте сообщения выше и логи.")

        else:
            logger.error(f"Ошибка выполнения пайплайна для {image_path}. Код возврата: {process.returncode}")
            logger.error(f"Pipeline stdout:\n{stdout_decoded}")
            logger.error(f"Pipeline stderr:\n{stderr_decoded}")
            # Сообщаем пользователю об ошибке
            error_message = f"Произошла ошибка во время анализа изображения. 😥"
            # Можно добавить детали из stderr, если это безопасно и информативно
            if stderr_decoded and len(stderr_decoded) < 500 : # Ограничиваем длину и проверяем наличие
               error_message += f"\nДетали: {stderr_decoded}"
            await responder.reply_text(error_message)

    except Exception as e:
        logger.error(f"Исключение при запуске/обработке пайплайна: {e}", exc_info=True)
        await responder.reply_text("Произошла непредвиденная ошибка при выполнении анализа.")

    finally:
        # Очищаем user_data после завершения диалога или ошибки
        logger.info("Очистка user_data.")
        context.user_data.clear()
        # Попытка удалить временное изображение, если оно существует
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logger.info(f"Удалено временное изображение: {image_path}")
            except Exception as del_e:
                logger.warning(f"Не удалось удалить временное изображение {image_path}: {del_e}")


    return ConversationHandler.END

async def ask_scenario_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Ответ на кнопку 'Указать сценарий'. Просит пользователя ввести текст."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text="Пожалуйста, введите типичный сценарий использования:")
    return WAIT_SCENARIO

async def received_scenario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Сохраняет введенный сценарий и запускает анализ."""
    user_scenario_text = update.message.text
    context.user_data['user_scenario'] = user_scenario_text
    logger.info(f"Получен сценарий: {user_scenario_text}")
    await update.message.reply_text(f"Сценарий '{user_scenario_text}' сохранен.")
    # Запускаем анализ
    return await start_analysis(update, context)

async def skip_scenario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обрабатывает пропуск ввода сценария и запускает анализ."""
    query = update.callback_query
    await query.answer()
    context.user_data['user_scenario'] = None # Или "Не указан"
    logger.info("Пользователь пропустил ввод сценария.")
    # Запускаем анализ
    # Важно: используем query для передачи update в start_analysis
    return await start_analysis(query, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий диалог."""
    logger.info("Пользователь отменил диалог.")
    responder = update.message if hasattr(update, 'message') else update.callback_query.message
    await responder.reply_text('Действие отменено. Можете отправить новое изображение.')
    # Очищаем user_data и удаляем временный файл, если он есть
    image_path = context.user_data.get('image_path')
    context.user_data.clear()
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
            logger.info(f"Удалено временное изображение при отмене: {image_path}")
        except Exception as del_e:
            logger.warning(f"Не удалось удалить временное изображение при отмене {image_path}: {del_e}")

    return ConversationHandler.END

# --- Старые внутренние функции (будут перенесены или удалены) ---
# Helper function to detect MIME type
# ... (get_mime_type)
# Функции для форматирования и отправки структурированных данных
# ... (send_formatted_interpretation)
# ... (send_formatted_recommendations)

# --- Запуск пайплайна (будет перенесен в start_analysis) ---
# try:
#    # Check if pipeline script exists
#    # ... (pipeline execution code) ...
# except Exception as e:
#    # ... (error handling) ...

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

    # Создание ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.PHOTO | filters.Document.IMAGE, start_conversation)],
        states={
            GET_TYPE: [
                CallbackQueryHandler(ask_type_input, pattern='^specify_type$'),
                CallbackQueryHandler(skip_type, pattern='^skip_type$'),
            ],
            WAIT_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_type)],
            GET_SCENARIO: [
                CallbackQueryHandler(ask_scenario_input, pattern='^specify_scenario$'),
                CallbackQueryHandler(skip_scenario, pattern='^skip_scenario$'),
            ],
            WAIT_SCENARIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, received_scenario)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
         # Можно добавить таймаут ожидания ответа
        # conversation_timeout=600 # 10 минут
    )

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(conv_handler) # Добавляем ConversationHandler
    # Убираем старый обработчик изображений, т.к. он теперь entry_point для conv_handler
    # application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))

    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)

    # Запуск бота
    logger.info("Запуск бота...")
    application.run_polling()

if __name__ == "__main__":
    main() 