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
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
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

# --- Обработчик изображений ---

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает полученное изображение (фото или документ), запускает анализ и отправляет результаты."""
    message = update.message
    chat_id = update.effective_chat.id
    file_to_get = None
    file_unique_id = None
    file_extension = '.png' # Default extension

    photo = message.photo
    document = message.document

    if photo:
        # Process photo
        await message.reply_text("Фото получено. Начинаю анализ... Это может занять несколько минут ⏳")
        try:
            file_to_get = await message.photo[-1].get_file()
            file_unique_id = file_to_get.file_unique_id
        except Exception as e:
            logger.error(f"Не удалось получить файл фото: {e}")
            await message.reply_text("Произошла ошибка при получении файла фото. Попробуйте еще раз.")
            return
    elif document and document.mime_type and document.mime_type.startswith('image/'):
        # Process document image
        await message.reply_text("Изображение (как документ) получено. Начинаю анализ... Это может занять несколько минут ⏳")
        try:
            file_to_get = await document.get_file()
            file_unique_id = file_to_get.file_unique_id
            file_extension = mimetypes.guess_extension(document.mime_type) or '.png'
        except Exception as e:
            logger.error(f"Не удалось получить файл документа: {e}")
            await message.reply_text("Произошла ошибка при получении файла документа. Попробуйте еще раз.")
            return
    else:
        # Neither photo nor image document
        await message.reply_text("Пожалуйста, отправь изображение (как фото или как файл изображения).")
        return

    # Создаем временную директорию для изображения
    with tempfile.TemporaryDirectory() as temp_dir:
        # Use unique ID and determined extension for filename
        image_filename = f"input_image_{file_unique_id}{file_extension}"
        image_path = os.path.join(temp_dir, image_filename)
        try:
            await file_to_get.download_to_drive(image_path)
            logger.info(f"Изображение сохранено во временный файл: {image_path}")
        except Exception as e:
            logger.error(f"Не удалось скачать изображение: {e}")
            await message.reply_text("Произошла ошибка при сохранении изображения. Попробуйте еще раз.")
            return

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

        async def send_formatted_recommendations(chat_id, recommendations_data):
            """Форматирует и отправляет стратегические рекомендации в виде отдельных сообщений."""
            try:
                if not recommendations_data or "strategicRecommendations" not in recommendations_data:
                    logger.warning("Структура рекомендаций не содержит ожидаемых данных")
                    await context.bot.send_message(
                        chat_id=chat_id,
                        text="⚠️ Не удалось обработать данные рекомендаций в удобочитаемом формате."
                    )
                    return False

                # Заголовок рекомендаций
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="*💡 СТРАТЕГИЧЕСКИЕ РЕКОМЕНДАЦИИ*\n\nПредлагаемые улучшения интерфейса:",
                    parse_mode="Markdown"
                )

                # Перебираем все рекомендации и отправляем их как отдельные сообщения
                recommendations = recommendations_data["strategicRecommendations"]
                for i, rec in enumerate(recommendations, 1):
                    # Формируем текст рекомендации
                    text = f"*{i}. {rec.get('title', 'Рекомендация')}*\n\n"
                    
                    if "problemStatement" in rec:
                        text += f"*Проблема:*\n{rec['problemStatement']}\n\n"
                    
                    if "solutionDescription" in rec:
                        text += f"*Решение:*\n{rec['solutionDescription']}\n\n"
                    
                    if "expectedImpact" in rec:
                        text += f"*Ожидаемый эффект:*\n{rec['expectedImpact']}\n\n"
                    
                    if "businessConstraints" in rec:
                        text += f"*Бизнес-ограничения:*\n{rec['businessConstraints']}\n\n"
                    
                    # Дополнительная информация в зависимости от длины основного текста
                    additional_text = ""
                    if "crossDomainExample" in rec:
                        additional_text += f"*Пример из других областей:*\n{rec['crossDomainExample']}\n\n"
                    
                    if "testingApproach" in rec:
                        additional_text += f"*Подход к тестированию:*\n{rec['testingApproach']}\n\n"
                    
                    # Разбиваем на части при необходимости
                    MAX_LEN = 4000
                    if len(text) <= MAX_LEN:
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=text,
                            parse_mode="Markdown"
                        )
                    else:
                        # Если основной текст слишком длинный, разбиваем его
                        parts = [text[i:i+MAX_LEN] for i in range(0, len(text), MAX_LEN)]
                        for j, part in enumerate(parts):
                            part_text = part
                            if j == 0:
                                part_text = f"*{i}. {rec.get('title', 'Рекомендация')}*\n\n" + part[len(f"*{i}. {rec.get('title', 'Рекомендация')}*\n\n"):]
                            else:
                                part_text = f"*{i}. {rec.get('title', 'Рекомендация')}* (продолжение {j+1})\n\n" + part
                            
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=part_text,
                                parse_mode="Markdown"
                            )
                    
                    # Отправляем дополнительную информацию отдельным сообщением, если она есть
                    if additional_text and len(additional_text) > 0:
                        if len(additional_text) <= MAX_LEN:
                            await context.bot.send_message(
                                chat_id=chat_id,
                                text=f"*Дополнительно по рекомендации {i}:*\n\n{additional_text}",
                                parse_mode="Markdown"
                            )
                        else:
                            # Разбиваем дополнительный текст на части
                            add_parts = [additional_text[i:i+MAX_LEN] for i in range(0, len(additional_text), MAX_LEN)]
                            for j, add_part in enumerate(add_parts):
                                await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=f"*Дополнительно по рекомендации {i} (часть {j+1}):*\n\n{add_part}",
                                    parse_mode="Markdown"
                                )
                
                return True
            except Exception as e:
                logger.error(f"Ошибка при отправке форматированных рекомендаций: {e}")
                traceback.print_exc()
                return False

        # Запускаем пайплайн анализа
        try:
            # Check if pipeline script exists
            if not os.path.exists(PIPELINE_SCRIPT_PATH):
                logger.error(f"Скрипт анализа не найден по пути: {PIPELINE_SCRIPT_PATH}")
                await message.reply_text("Критическая ошибка: не найден скрипт анализа на сервере.")
                return

            logger.info(f"Запуск {PIPELINE_SCRIPT_PATH} для {image_path}")
            process = await asyncio.create_subprocess_exec(
                sys.executable, # Используем тот же python, что и для бота
                PIPELINE_SCRIPT_PATH, # Use the absolute path
                image_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # Set working directory to the script's directory? Maybe not needed if paths inside pipeline are ok.
                # cwd=SCRIPT_DIR
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

            logger.info(f"stdout {PIPELINE_SCRIPT_PATH}:\n{stdout_str}") # Log received stdout
            if stderr_str: # Логируем stderr даже при успешном выполнении
                logger.warning(f"stderr {PIPELINE_SCRIPT_PATH} (при коде 0):\n{stderr_str}")

            # Извлекаем пути к результатам из stdout
            logger.info("Parsing pipeline stdout for result paths...")
            pdf_path_match = re.search(r"✅ PDF Отчет: (.*\.pdf)", stdout_str)
            heatmap_path_match = re.search(r"✅ Тепловая карта: (.*\.png)", stdout_str)
            interp_match = re.search(r"✅ Файл интерпретации: (.*\.json)", stdout_str)
            rec_match = re.search(r"✅ Файл рекомендаций: (.*\.json)", stdout_str)
            tex_match = re.search(r"✅ LaTeX Отчет.*: (.*\.tex)", stdout_str)

            pdf_path = pdf_path_match.group(1).strip() if pdf_path_match else None
            heatmap_path = heatmap_path_match.group(1).strip() if heatmap_path_match else None
            interp_path = interp_match.group(1).strip() if interp_match else None
            rec_path = rec_match.group(1).strip() if rec_match else None
            tex_path = tex_match.group(1).strip() if tex_match else None
            output_dir_match = re.search(r"Результаты будут сохранены в: (?:\./)?(analysis_outputs/run_\d{8}_\d{6})", stdout_str)
            output_dir = output_dir_match.group(1).strip() if output_dir_match else None # Group 1 is the analysis_outputs/... part

            logger.info(f"  Parsed PDF path: {pdf_path}")
            logger.info(f"  Parsed Heatmap path: {heatmap_path}")
            logger.info(f"  Parsed Interpretation path: {interp_path}")
            logger.info(f"  Parsed Recommendations path: {rec_path}")
            logger.info(f"  Parsed Fallback TeX path: {tex_path}")
            logger.info(f"  Parsed Output dir for cleanup: {output_dir}")

            # Отправляем результаты
            await message.reply_text("Анализ завершен! Отправляю результаты...")

            results_sent = False
            # --- Sending PDF --- 
            if pdf_path:
                logger.info(f"Checking existence of PDF: {pdf_path}")
                if os.path.exists(pdf_path):
                    try:
                        logger.info(f"Attempting to send PDF: {pdf_path}")
                        # Get MIME type for PDF
                        mime_type = get_mime_type(pdf_path)
                        logger.info(f"Detected MIME type for PDF: {mime_type}")
                        
                        with open(pdf_path, 'rb') as pdf_file:
                            pdf_bytes = pdf_file.read()  # Read file into memory
                            await context.bot.send_document(
                                chat_id=chat_id, 
                                document=InputFile(pdf_bytes, filename=os.path.basename(pdf_path)),
                                caption="Анализ UI (PDF)"
                            )
                        logger.info(f"Отправлен PDF: {pdf_path}")
                        results_sent = True
                    except Exception as e:
                        logger.error(f"Не удалось отправить PDF {pdf_path}: {e}")
                        try:
                            # Try simplified approach
                            with open(pdf_path, 'rb') as pdf_file:
                                await context.bot.send_document(
                                    chat_id=chat_id,
                                    document=pdf_file,
                                    filename=os.path.basename(pdf_path),
                                    caption="Анализ UI (PDF) - резервный метод"
                                )
                            logger.info(f"PDF отправлен резервным методом: {pdf_path}")
                            results_sent = True
                        except Exception as e2:
                            logger.error(f"Не удалось отправить PDF резервным методом: {e2}")
                            try:
                                await message.reply_text(f"Не удалось отправить PDF отчет.") 
                            except Exception as reply_e:
                                logger.error(f"Failed to send error reply for PDF: {reply_e}")
                else:
                    logger.warning(f"PDF file path found in stdout, but file does not exist at: {pdf_path}")
            else:
                logger.info("No PDF path found in stdout.")

            # --- Sending Heatmap --- 
            if heatmap_path:
                logger.info(f"Checking existence of Heatmap: {heatmap_path}")
                heatmap_size_mb = os.path.getsize(heatmap_path) / (1024 * 1024) if os.path.exists(heatmap_path) else 0
                logger.info(f"Heatmap file size: {heatmap_size_mb:.2f} MB")
                if os.path.exists(heatmap_path):
                    try:
                        logger.info(f"Attempting to send Heatmap: {heatmap_path} (Size: {heatmap_size_mb:.2f} MB)")
                        
                        # First try to send as photo directly
                        with open(heatmap_path, 'rb') as img_file:
                            await context.bot.send_photo(
                                chat_id=chat_id,
                                photo=InputFile(img_file),
                                caption="Тепловая карта проблемных зон",
                                parse_mode="HTML"
                            )
                        logger.info("Heatmap sent successfully as photo")
                        results_sent = True
                    except Exception as e:
                        logger.error(f"Failed to send heatmap as photo: {e}")
                        
                        try:
                            # Try sending as document instead
                            logger.info("Trying to send heatmap as document instead...")
                            with open(heatmap_path, 'rb') as img_file:
                                img_bytes = img_file.read()
                                file_name = os.path.basename(heatmap_path)
                                
                                await context.bot.send_document(
                                    chat_id=chat_id, 
                                    document=InputFile(io.BytesIO(img_bytes), filename=file_name),
                                    caption="Тепловая карта проблемных зон",
                                    parse_mode="HTML"
                                )
                            logger.info("Heatmap sent successfully as document")
                            results_sent = True
                        except Exception as e2:
                            logger.error(f"Failed to send heatmap as document: {e2}")
                            await message.reply_text("Не удалось отправить тепловую карту. Проверьте логи сервера.")
                else:
                    logger.warning(f"Heatmap file path found in stdout, but file does not exist at: {heatmap_path}")
            else:
                logger.info("No Heatmap path found in stdout.")

            # --- Sending Interpretation JSON file --- 
            if interp_path:
                logger.info(f"Checking existence of Interpretation JSON: {interp_path}")
                if os.path.exists(interp_path):
                    try:
                        # Сначала отправляем форматированный текст
                        logger.info(f"Attempting to read and format Interpretation: {interp_path}")
                        with open(interp_path, 'r', encoding='utf-8') as f:
                            interp_data = json.load(f)
                        
                        interp_formatted_sent = await send_formatted_interpretation(chat_id, interp_data)
                        
                        # Затем отправляем исходный JSON-файл как документ для сохранения
                        logger.info(f"Attempting to send Interpretation JSON file: {interp_path}")
                        with open(interp_path, 'rb') as json_file:
                            json_bytes = json_file.read() 
                            mime_type = "application/json"
                            file_name = os.path.basename(interp_path)
                            
                            await context.bot.send_document(
                                chat_id=chat_id, 
                                document=InputFile(io.BytesIO(json_bytes), filename=file_name),
                                caption="Стратегическая интерпретация (JSON для сохранения)",
                                parse_mode="HTML"
                            )
                        logger.info(f"Отправлен файл интерпретации: {interp_path}")
                        results_sent = True
                    except Exception as e:
                        logger.error(f"Не удалось отправить интерпретацию {interp_path}: {e}")
                        try:
                            await message.reply_text("Не удалось отправить интерпретацию.")
                        except Exception as reply_e:
                            logger.error(f"Failed to send error reply for Interpretation: {reply_e}")
                else:
                    logger.warning(f"Interpretation JSON path found in stdout, but file does not exist at: {interp_path}")
            else:
                logger.info("No Interpretation JSON path found in stdout.")

            # --- Sending Recommendations JSON file --- 
            if rec_path:
                logger.info(f"Checking existence of Recommendations JSON: {rec_path}")
                if os.path.exists(rec_path):
                    try:
                        # Сначала отправляем форматированный текст
                        logger.info(f"Attempting to read and format Recommendations: {rec_path}")
                        with open(rec_path, 'r', encoding='utf-8') as f:
                            rec_data = json.load(f)
                        
                        rec_formatted_sent = await send_formatted_recommendations(chat_id, rec_data)
                        
                        # Затем отправляем исходный JSON-файл как документ для сохранения
                        logger.info(f"Attempting to send Recommendations JSON file: {rec_path}")
                        with open(rec_path, 'rb') as json_file:
                            json_bytes = json_file.read()
                            mime_type = "application/json"
                            file_name = os.path.basename(rec_path)
                            
                            await context.bot.send_document(
                                chat_id=chat_id, 
                                document=InputFile(io.BytesIO(json_bytes), filename=file_name),
                                caption="Стратегические рекомендации (JSON для сохранения)",
                                parse_mode="HTML"
                            )
                        logger.info(f"Отправлен файл рекомендаций: {rec_path}")
                        results_sent = True
                    except Exception as e:
                        logger.error(f"Не удалось отправить файл рекомендаций {rec_path}: {e}")
                        try:
                            await message.reply_text("Не удалось отправить файл рекомендаций.")
                        except Exception as reply_e:
                            logger.error(f"Failed to send error reply for Recommendations JSON: {reply_e}")
                else:
                    logger.warning(f"Recommendations JSON path found in stdout, but file does not exist at: {rec_path}")
            else:
                logger.info("No Recommendations JSON path found in stdout.")

            # --- PDF or Fallback Sending TeX file --- 
            if pdf_path and os.path.exists(pdf_path):
                logger.info(f"Checking existence of PDF: {pdf_path}")
                pdf_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
                logger.info(f"PDF file size: {pdf_size_mb:.2f} MB")
                try:
                    logger.info(f"Attempting to send PDF file: {pdf_path}")
                    
                    with open(pdf_path, 'rb') as pdf_file:
                        pdf_bytes = pdf_file.read()  # Read file into memory
                        
                        # Explicitly specify the MIME type
                        mime_type = "application/pdf"
                        file_name = os.path.basename(pdf_path)
                        
                        await context.bot.send_document(
                            chat_id=chat_id, 
                            document=InputFile(io.BytesIO(pdf_bytes), filename=file_name),
                            caption="Отчет анализа (PDF)",
                            parse_mode="HTML"
                        )
                    logger.info(f"Отправлен PDF отчет: {pdf_path}")
                    results_sent = True
                except Exception as e:
                    logger.error(f"Не удалось отправить PDF {pdf_path}: {e}")
                    try:
                        await message.reply_text("Не удалось отправить PDF отчет.")
                    except Exception as reply_e:
                        logger.error(f"Failed to send error reply for PDF: {reply_e}")
            elif tex_path and os.path.exists(tex_path): # Only if PDF path wasn't found or file doesn't exist
                logger.info("PDF path missing or file not found, attempting fallback to TeX file.")
                logger.info(f"Checking existence of Fallback TeX: {tex_path}")
                try:
                    logger.info(f"Attempting to send Fallback TeX file: {tex_path}")
                    
                    with open(tex_path, 'rb') as tex_file:
                        tex_bytes = tex_file.read()  # Read file into memory
                        
                        # Explicitly specify the MIME type
                        mime_type = "application/x-tex"
                        file_name = os.path.basename(tex_path)
                        
                        await context.bot.send_document(
                            chat_id=chat_id, 
                            document=InputFile(io.BytesIO(tex_bytes), filename=file_name),
                            caption="Отчет анализа (TeX файл)",
                            parse_mode="HTML"
                        )
                    logger.info(f"Отправлен LaTeX отчет (.tex): {tex_path}")
                    results_sent = True
                except Exception as e:
                    logger.error(f"Не удалось отправить LaTeX отчет {tex_path}: {e}")
                    try:
                        await message.reply_text("Не удалось отправить LaTeX отчет (.tex).")
                    except Exception as reply_e:
                        logger.error(f"Failed to send error reply for Fallback TeX: {reply_e}")
            else:
                logger.warning(f"Neither PDF nor TeX files found or could be sent")

            if not results_sent:
                # If after all attempts nothing was sent, inform the user
                logger.warning("No results were successfully sent to the user.")
                await message.reply_text("Не удалось найти или отправить файлы результатов после анализа.")

            # Очистка: удаляем папку с результатами
            if output_dir and os.path.exists(output_dir) and output_dir.startswith("analysis_outputs/"):
                try:
                    # Use absolute path for safety? Though relative should work if bot CWD is /app
                    # output_dir_abs = os.path.join(SCRIPT_DIR, output_dir) # If needed
                    shutil.rmtree(output_dir)
                    logger.info(f"Удалена директория с результатами: {output_dir}")
                except Exception as e:
                    logger.error(f"Не удалось удалить директорию {output_dir}: {e}")
            elif output_dir:
                logger.warning(f"Директория для удаления не найдена или небезопасна: {output_dir}")

            # --- ENHANCED DEBUGGING FOR COORDINATES, HEATMAP, AND PDF ISSUES ---
            # Extra debug logging for coordinates file
            gemini_coords_parsed = None
            for line in stdout_str.splitlines():
                if "Распарсенный Gemini ответ сохранен в:" in line:
                    gemini_coords_parsed = line.split("Распарсенный Gemini ответ сохранен в:", 1)[1].strip()
                    logger.info(f"FOUND COORDINATES FILE PATH: {gemini_coords_parsed}")
                    if os.path.exists(gemini_coords_parsed):
                        try:
                            with open(gemini_coords_parsed, 'r', encoding='utf-8') as f:
                                coords_data = json.load(f)
                                coords_count = len(coords_data.get("element_coordinates", []))
                                logger.info(f"COORDINATES FILE EXISTS with {coords_count} elements")
                        except Exception as e:
                            logger.error(f"ERROR READING COORDINATES FILE: {e}")
                    else:
                        logger.error(f"COORDINATES FILE NOT FOUND AT: {gemini_coords_parsed}")
            
            # Extra debug logging for heatmap file
            heatmap_path = None
            for line in stdout_str.splitlines():
                if "Тепловая карта успешно сгенерирована и сохранена в:" in line:
                    heatmap_path = line.split("Тепловая карта успешно сгенерирована и сохранена в:", 1)[1].strip()
                    logger.info(f"FOUND HEATMAP FILE PATH: {heatmap_path}")
                    if os.path.exists(heatmap_path):
                        heatmap_size_mb = os.path.getsize(heatmap_path) / (1024 * 1024)
                        logger.info(f"HEATMAP FILE EXISTS with size: {heatmap_size_mb:.2f} MB")
                    else:
                        logger.error(f"HEATMAP FILE NOT FOUND AT: {heatmap_path}")
            
            # Extra debug logging for PDF generation
            pdf_path = None
            tex_path = None
            for line in stdout_str.splitlines():
                if ".pdf" in line and "✅ PDF Отчет:" in line:
                    pdf_path = line.split("✅ PDF Отчет:", 1)[1].strip()
                    logger.info(f"FOUND PDF FILE PATH: {pdf_path}")
                    if os.path.exists(pdf_path):
                        pdf_size_mb = os.path.getsize(pdf_path) / (1024 * 1024)
                        logger.info(f"PDF FILE EXISTS with size: {pdf_size_mb:.2f} MB")
                    else:
                        logger.error(f"PDF FILE NOT FOUND AT: {pdf_path}")
                        
                        # Check if tex file exists
                        tex_path = pdf_path.replace(".pdf", ".tex")
                        if os.path.exists(tex_path):
                            logger.info(f"TEX FILE EXISTS at: {tex_path}")
                            # Check log file for errors
                            log_path = tex_path.replace(".tex", ".log")
                            if os.path.exists(log_path):
                                try:
                                    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                                        log_tail = f.readlines()[-20:]  # Get last 20 lines
                                        logger.error(f"PDF GENERATION LOG (last 20 lines): {''.join(log_tail)}")
                                except Exception as e:
                                    logger.error(f"Error reading log file: {e}")
                        else:
                            logger.error(f"TEX FILE NOT FOUND AT: {tex_path}")
            
            # ... rest of the existing code ...

        except Exception as e:
            logger.error(f"Error in image handling: {e}")
            traceback.print_exc()
            await message.reply_text(f"Произошла ошибка при обработке вашего изображения: {e}")

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

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    # Updated handler to accept photos OR image documents
    application.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_image))

    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)

    # Запуск бота
    logger.info("Запуск бота...")
    application.run_polling()

if __name__ == "__main__":
    main() 