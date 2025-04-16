import os
import logging
import subprocess
import tempfile
import re
import shutil
import asyncio
import sys
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
        "1. Отправь мне изображение (скриншот) интерфейса, который нужно проанализировать.\n"
        "2. Я запущу полный пайплайн анализа (GPT-4, Gemini Coordinates, Heatmap, Report).\n"
        "3. В ответ я пришлю PDF-отчет и тепловую карту.\n\n"
        "Пожалуйста, отправляй только одно изображение за раз."
    )

# --- Обработчик изображений ---

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает полученное изображение, запускает анализ и отправляет результаты."""
    message = update.message
    chat_id = update.effective_chat.id
    if not message.photo:
        await message.reply_text("Пожалуйста, отправь изображение (не файл).")
        return

    await message.reply_text("Изображение получено. Начинаю анализ... Это может занять несколько минут ⏳")

    # Получаем файл изображения наибольшего разрешения
    try:
        photo_file = await message.photo[-1].get_file()
    except Exception as e:
        logger.error(f"Не удалось получить файл изображения: {e}")
        await message.reply_text("Произошла ошибка при получении файла изображения. Попробуйте еще раз.")
        return

    # Создаем временную директорию для изображения
    with tempfile.TemporaryDirectory() as temp_dir:
        image_path = os.path.join(temp_dir, f"input_image_{photo_file.file_unique_id}.png")
        try:
            await photo_file.download_to_drive(image_path)
            logger.info(f"Изображение сохранено во временный файл: {image_path}")
        except Exception as e:
            logger.error(f"Не удалось скачать изображение: {e}")
            await message.reply_text("Произошла ошибка при сохранении изображения. Попробуйте еще раз.")
            return

        # Запускаем пайплайн анализа
        try:
            logger.info(f"Запуск run_analysis_pipeline.py для {image_path}")
            process = await asyncio.create_subprocess_exec(
                sys.executable, # Используем тот же python, что и для бота
                'run_analysis_pipeline.py',
                image_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            stdout_str = stdout.decode('utf-8', errors='ignore')
            stderr_str = stderr.decode('utf-8', errors='ignore')

            logger.info(f"run_analysis_pipeline.py завершился с кодом {process.returncode}")
            if process.returncode != 0:
                logger.error(f"Ошибка выполнения run_analysis_pipeline.py:\nstdout:\n{stdout_str}\nstderr:\n{stderr_str}")
                # Отправляем пользователю сообщение об ошибке, включая stderr, если он не пустой
                error_message = "Произошла ошибка во время анализа."
                if stderr_str:
                    # Показываем только последние ~500 символов ошибки, чтобы не спамить
                    # Используем replace для экранирования Markdown V2 спецсимволов
                    escaped_stderr = re.sub(r'([_*\[\]()~`>#+\-=|{}.!])\'', r'\\\1\'', stderr_str[-500:])
                    error_message += f"\n\nДетали ошибки:\n```\n...{escaped_stderr}\n```"

                await message.reply_text(error_message, parse_mode='MarkdownV2')
                return

            logger.info(f"stdout run_analysis_pipeline.py:\n{stdout_str}")
            if stderr_str: # Логируем stderr даже при успешном выполнении
                logger.warning(f"stderr run_analysis_pipeline.py (при коде 0):\n{stderr_str}")

            # Извлекаем пути к результатам из stdout
            pdf_path_match = re.search(r"✅ PDF Отчет: (.*\.pdf)", stdout_str)
            heatmap_path_match = re.search(r"✅ Тепловая карта: (.*\.png)", stdout_str)
            # Обновленный регекс для директории, учитывающий ./ если скрипт запущен из корня
            output_dir_match = re.search(r"Результаты будут сохранены в: (\\./)?(analysis_outputs/run_\\d{8}_\\d{6})", stdout_str)

            pdf_path = pdf_path_match.group(1).strip() if pdf_path_match else None
            heatmap_path = heatmap_path_match.group(1).strip() if heatmap_path_match else None
            # Берем вторую группу захвата, чтобы исключить опциональный "./"
            output_dir = output_dir_match.group(2).strip() if output_dir_match else None # Для очистки

            # Отправляем результаты
            await message.reply_text("Анализ завершен! Отправляю результаты...")

            results_sent = False
            if pdf_path and os.path.exists(pdf_path):
                try:
                    # Отправляем с InputFile для автоматической обработки пути
                    await context.bot.send_document(chat_id=chat_id, document=InputFile(pdf_path), filename=os.path.basename(pdf_path))
                    logger.info(f"Отправлен PDF: {pdf_path}")
                    results_sent = True
                except Exception as e:
                    logger.error(f"Не удалось отправить PDF {pdf_path}: {e}")
                    await message.reply_text(f"Не удалось отправить PDF отчет: {e}")
            else:
                logger.warning(f"PDF файл не найден ({os.path.exists(pdf_path) if pdf_path else 'N/A'}) или путь не извлечен: {pdf_path}")

            if heatmap_path and os.path.exists(heatmap_path):
                try:
                    # Отправляем с InputFile
                    await context.bot.send_photo(chat_id=chat_id, photo=InputFile(heatmap_path), caption="Тепловая карта проблемных зон")
                    logger.info(f"Отправлена тепловая карта: {heatmap_path}")
                    results_sent = True
                except Exception as e:
                    logger.error(f"Не удалось отправить тепловую карту {heatmap_path}: {e}")
                    await message.reply_text(f"Не удалось отправить тепловую карту: {e}")
            else:
                logger.warning(f"Файл тепловой карты не найден ({os.path.exists(heatmap_path) if heatmap_path else 'N/A'}) или путь не извлечен: {heatmap_path}")

            if not results_sent:
                await message.reply_text("Не удалось найти или отправить файлы результатов после анализа.")

            # Очистка: удаляем папку с результатами, если она была создана пайплайном
            if output_dir and os.path.exists(output_dir) and output_dir.startswith("analysis_outputs/"): # Доп. проверка безопасности
                try:
                    shutil.rmtree(output_dir)
                    logger.info(f"Удалена директория с результатами: {output_dir}")
                except Exception as e:
                    logger.error(f"Не удалось удалить директорию {output_dir}: {e}")
            elif output_dir:
                logger.warning(f"Директория для удаления не найдена или небезопасна: {output_dir}")

        except Exception as e:
            logger.exception("Неожиданная ошибка в handle_image") # Логируем traceback
            await message.reply_text("Произошла неожиданная ошибка во время обработки вашего запроса.")

# --- Обработчик ошибок ---

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирует ошибки, вызванные обновлениями."""
    logger.error(f"Update {update} caused error {context.error}")

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
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))

    # Регистрация обработчика ошибок
    application.add_error_handler(error_handler)

    # Запуск бота
    logger.info("Запуск бота...")
    application.run_polling()

if __name__ == "__main__":
    main() 