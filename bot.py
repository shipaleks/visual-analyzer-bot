import os
import logging
import subprocess
import tempfile
import re
import shutil
import asyncio
import sys
import mimetypes
import telegram
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv

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
            if process.returncode != 0:
                logger.error(f"Ошибка выполнения {PIPELINE_SCRIPT_PATH}:\nstdout:\n{stdout_str}\nstderr:\n{stderr_str}")
                error_message = "Произошла ошибка во время анализа."
                if stderr_str:
                    # Corrected MarkdownV2 escaping
                    # Escapes _ * [ ] ( ) ~ ` > # + - = | { } . !
                    try:
                        escaped_stderr = re.sub(r'([_*\\[\\]()~`>#+\\-=|{}.!])', r'\\\\\\1', stderr_str[-500:]) # Fixed regex pattern
                        error_message += f"\n\nДетали ошибки:\n```\n...{escaped_stderr}\n```"
                        await message.reply_text(error_message, parse_mode='MarkdownV2')
                    except Exception as escape_err:
                        logger.error(f"Failed to send MarkdownV2 error message: {escape_err}. Sending plain text.")
                        error_message += f"\n\nДетали ошибки (raw):\n...{stderr_str[-500:]}"
                        await message.reply_text(error_message) # Fallback to plain text

                else:
                    await message.reply_text(error_message) # Send generic if no stderr
                return

            logger.info(f"stdout {PIPELINE_SCRIPT_PATH}:\n{stdout_str}")
            if stderr_str: # Логируем stderr даже при успешном выполнении
                logger.warning(f"stderr {PIPELINE_SCRIPT_PATH} (при коде 0):\n{stderr_str}")

            # Извлекаем пути к результатам из stdout
            pdf_path_match = re.search(r"✅ PDF Отчет: (.*\.pdf)", stdout_str)
            heatmap_path_match = re.search(r"✅ Тепловая карта: (.*\.png)", stdout_str)
            output_dir_match = re.search(r"Результаты будут сохранены в: (\\\\./)?(analysis_outputs/run_\\d{8}_\\d{6})", stdout_str)

            pdf_path = pdf_path_match.group(1).strip() if pdf_path_match else None
            heatmap_path = heatmap_path_match.group(1).strip() if heatmap_path_match else None
            output_dir = output_dir_match.group(2).strip() if output_dir_match else None # Для очистки

            # Отправляем результаты
            await message.reply_text("Анализ завершен! Отправляю результаты...")

            results_sent = False
            if pdf_path and os.path.exists(pdf_path):
                try:
                    await context.bot.send_document(chat_id=chat_id, document=InputFile(pdf_path), filename=os.path.basename(pdf_path))
                    logger.info(f"Отправлен PDF: {pdf_path}")
                    results_sent = True
                except Exception as e:
                    logger.error(f"Не удалось отправить PDF {pdf_path}: {e}")
                    await message.reply_text(f"Не удалось отправить PDF отчет.") # Simplified error
            else:
                logger.warning(f"PDF файл не найден ({os.path.exists(pdf_path) if pdf_path else 'N/A'}) или путь не извлечен: {pdf_path}")

            if heatmap_path and os.path.exists(heatmap_path):
                try:
                    await context.bot.send_photo(chat_id=chat_id, photo=InputFile(heatmap_path), caption="Тепловая карта проблемных зон")
                    logger.info(f"Отправлена тепловая карта: {heatmap_path}")
                    results_sent = True
                except Exception as e:
                    logger.error(f"Не удалось отправить тепловую карту {heatmap_path}: {e}")
                    await message.reply_text(f"Не удалось отправить тепловую карту.") # Simplified error
            else:
                logger.warning(f"Файл тепловой карты не найден ({os.path.exists(heatmap_path) if heatmap_path else 'N/A'}) или путь не извлечен: {heatmap_path}")

            if not results_sent:
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

        except Exception as e:
            logger.exception("Неожиданная ошибка в handle_image")
            await message.reply_text("Произошла неожиданная ошибка во время обработки вашего запроса.")

# --- Обработчик ошибок ---

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки, вызванные обновлениями."""
    # Log the error before reacting to it
    logger.error(f"Update {update} caused error {context.error}", exc_info=context.error)

    # Handle potential MarkdownV2 issues in error reporting itself
    if isinstance(context.error, telegram.error.BadRequest) and "Can't parse entities" in str(context.error):
        logger.warning("BadRequest when sending error message, potentially MarkdownV2 issue.")
        # Optionally send a generic error to the user if the detailed one failed
        if update and hasattr(update, 'effective_message'):
            try:
                # Avoid sending another MarkdownV2 message here if that's the source of the error
                await update.effective_message.reply_text("Произошла внутренняя ошибка при обработке предыдущей ошибки.")
            except Exception as inner_e:
                logger.error(f"Failed to send fallback error message: {inner_e}")

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