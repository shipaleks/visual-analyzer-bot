#!/usr/bin/env python3
"""
Telegram bot for UI analysis.

This bot accepts screenshots from users, optionally asks for context,
runs an analysis pipeline, and returns the results including
strategic interpretations, recommendations, PDF reports and heatmaps.
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import Message, FSInputFile, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# Custom modules
from analysis_pipeline import run_analysis_pipeline

# Configure logging
logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Define state machine for conversation flow
class AnalysisStates(StatesGroup):
    waiting_for_screenshot = State()
    waiting_for_context = State()
    entering_context = State()  # Новое состояние для ввода описания
    waiting_for_userflows = State()
    entering_userflows = State()  # Новое состояние для ввода сценариев
    analyzing = State()

# Ensure directories exist
os.makedirs("temp", exist_ok=True)
os.makedirs("results", exist_ok=True)

# Command handlers
@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle the /start command."""
    await message.answer(
        "Привет! Я бот для анализа UI/UX интерфейсов. 🚀\n\n"
        "Отправь мне скриншот интерфейса для анализа.\n"
        "После этого у тебя будет возможность добавить описание и сценарии использования "
        "или сразу перейти к анализу."
    )

@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle the /help command."""
    await message.answer(
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

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Handle the /cancel command."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("Нечего отменять. Отправьте скриншот для анализа.")
        return

    # Cancel state and inform user
    await state.clear()
    await message.answer("Анализ отменен. Отправьте скриншот, чтобы начать снова.")

# Message handlers
@router.message(lambda message: message.photo)
async def handle_photo(message: Message, state: FSMContext):
    """Handle incoming photos (screenshots)."""
    # Check if we're already in a state
    current_state = await state.get_state()
    if current_state and current_state != "AnalysisStates:waiting_for_screenshot":
        await message.answer("У вас уже идет процесс анализа. Используйте /cancel для отмены.")
        return

    # Get the largest photo (best quality)
    photo = message.photo[-1]
    
    # Generate unique filename using user ID and timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_id = message.from_user.id
    file_id = f"{user_id}_{timestamp}"
    
    # Path to save the screenshot
    screenshot_path = f"temp/{file_id}_input.png"
    
    # Download the photo
    await message.answer("Получил скриншот! Сохраняю...")
    file_info = await bot.get_file(photo.file_id)
    await bot.download_file(file_info.file_path, screenshot_path)
    
    # Save file path and info in FSM storage
    await state.update_data(
        screenshot_path=screenshot_path,
        file_id=file_id,
        timestamp=timestamp
    )
    
    # Move to the next state and ask for context with buttons
    await state.set_state(AnalysisStates.waiting_for_context)
    
    # Create keyboard with options
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пропустить")],
            [KeyboardButton(text="Ввести описание")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "Что изображено на скриншоте? Это поможет сделать анализ более точным.",
        reply_markup=keyboard
    )

@router.message(AnalysisStates.waiting_for_context)
async def handle_context_choice(message: Message, state: FSMContext):
    """Handle user's choice to enter context or skip."""
    text = message.text.strip()
    
    if text == "Пропустить":
        # Skip entering context, set to None
        await state.update_data(context=None)
        
        # Move to userflows stage with buttons
        await state.set_state(AnalysisStates.waiting_for_userflows)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Пропустить")],
                [KeyboardButton(text="Ввести сценарии")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "Какие основные пользовательские сценарии (user flows) связаны с этим интерфейсом? Это поможет сделать анализ более релевантным.",
            reply_markup=keyboard
        )
    
    elif text == "Ввести описание":
        # Move to the state for entering context
        await state.set_state(AnalysisStates.entering_context)
        await message.answer(
            "Пожалуйста, опишите, что изображено на скриншоте:",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    else:
        # Если пользователь ввел что-то другое, интерпретируем это как контекст
        await state.update_data(context=text)
        
        # Move to userflows stage with buttons
        await state.set_state(AnalysisStates.waiting_for_userflows)
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Пропустить")],
                [KeyboardButton(text="Ввести сценарии")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            "Какие основные пользовательские сценарии (user flows) связаны с этим интерфейсом? Это поможет сделать анализ более релевантным.",
            reply_markup=keyboard
        )

@router.message(AnalysisStates.entering_context)
async def handle_context_input(message: Message, state: FSMContext):
    """Handle actual context text input."""
    context = message.text.strip()
    
    # Save context in FSM storage
    await state.update_data(context=context)
    
    # Move to userflows stage with buttons
    await state.set_state(AnalysisStates.waiting_for_userflows)
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пропустить")],
            [KeyboardButton(text="Ввести сценарии")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "Какие основные пользовательские сценарии (user flows) связаны с этим интерфейсом? Это поможет сделать анализ более релевантным.",
        reply_markup=keyboard
    )

@router.message(AnalysisStates.waiting_for_userflows)
async def handle_userflows_choice(message: Message, state: FSMContext):
    """Handle user's choice to enter userflows or skip."""
    text = message.text.strip()
    
    if text == "Пропустить":
        # Skip entering userflows, set to None
        await state.update_data(userflows=None)
        
        # Start analysis
        await start_analysis(message, state)
    
    elif text == "Ввести сценарии":
        # Move to the state for entering userflows
        await state.set_state(AnalysisStates.entering_userflows)
        await message.answer(
            "Пожалуйста, опишите основные сценарии использования этого интерфейса:",
            reply_markup=types.ReplyKeyboardRemove()
        )
    
    else:
        # Если пользователь ввел что-то другое, интерпретируем это как сценарии
        await state.update_data(userflows=text)
        
        # Start analysis
        await start_analysis(message, state)

@router.message(AnalysisStates.entering_userflows)
async def handle_userflows_input(message: Message, state: FSMContext):
    """Handle actual userflows text input."""
    userflows = message.text.strip()
    
    # Save userflows in FSM storage
    await state.update_data(userflows=userflows)
    
    # Start analysis
    await start_analysis(message, state)

async def start_analysis(message: Message, state: FSMContext):
    """Start the analysis process with collected data."""
    # Get all the data we've collected
    data = await state.get_data()
    screenshot_path = data["screenshot_path"]
    file_id = data["file_id"]
    context = data.get("context")
    userflows = data.get("userflows")
    
    # Move to analyzing state
    await state.set_state(AnalysisStates.analyzing)
    
    # Inform the user that analysis has started
    await message.answer(
        "Спасибо! Начинаю анализ интерфейса. "
        "Это может занять несколько минут...",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    # Start the analysis pipeline in a separate task to not block the bot
    asyncio.create_task(
        process_analysis(message, state, screenshot_path, file_id, context, userflows)
    )

async def process_analysis(message, state, screenshot_path, file_id, context, userflows):
    """Process the analysis pipeline and send results to user."""
    try:
        # Run the analysis pipeline
        await message.answer("⏳ Анализирую скриншот с помощью GPT-4.1...")
        
        results = await run_analysis_pipeline(
            screenshot_path=screenshot_path,
            file_id=file_id,
            context=context,
            userflows=userflows
        )
        
        if not results:
            await message.answer("❌ Произошла ошибка при анализе. Пожалуйста, попробуйте позже или с другим скриншотом.")
            await state.clear()
            return
            
        # Extract paths from results
        interpretation_path = results["interpretation_path"]
        recommendations_path = results["recommendations_path"]
        pdf_report_path = results["pdf_report_path"]
        heatmap_path = results["heatmap_path"]
        
        # Send interpretation
        await message.answer("✅ Анализ завершен! Отправляю результаты...")
        
        # Format and send interpretation
        await message.answer("🧠 <b>Стратегическая интерпретация:</b>")
        interpretation_messages = format_interpretation(interpretation_path)
        for msg in interpretation_messages:
            await message.answer(msg, parse_mode="HTML")
        
        # Format and send recommendations
        await message.answer("💡 <b>Стратегические рекомендации:</b>")
        recommendation_messages = format_recommendations(recommendations_path)
        for msg in recommendation_messages:
            await message.answer(msg, parse_mode="HTML")
        
        # Send PDF report
        await message.answer("📊 <b>Полный отчет (PDF):</b>")
        pdf_file = FSInputFile(pdf_report_path)
        await message.answer_document(pdf_file, caption="Полный отчет с анализом интерфейса")
        
        # Send heatmap
        await message.answer("🔥 <b>Тепловая карта проблемных зон:</b>")
        heatmap_file = FSInputFile(heatmap_path)
        await message.answer_photo(heatmap_file, caption="Визуализация проблемных зон интерфейса")
        
        # Complete the analysis process
        await message.answer(
            "Анализ завершен! Если у вас есть еще скриншоты для анализа, просто отправьте их."
        )
        
    except Exception as e:
        logging.error(f"Error in process_analysis: {e}", exc_info=True)
        await message.answer(
            f"❌ Произошла ошибка при обработке результатов: {str(e)}\n"
            "Пожалуйста, попробуйте позже или с другим скриншотом."
        )
    finally:
        # Clear the state regardless of success or failure
        await state.clear()

def format_interpretation(interpretation_path):
    """Format interpretation JSON into readable messages."""
    try:
        with open(interpretation_path, 'r', encoding='utf-8') as f:
            data = f.read()
            
        # Handle case when JSON is returned directly
        try:
            interpretation = json.loads(data)
        except json.JSONDecodeError:
            # Try to extract JSON from text if it's wrapped in backticks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', data, re.DOTALL)
            if json_match:
                try:
                    interpretation = json.loads(json_match.group(1))
                except:
                    return [f"Ошибка при парсинге JSON из интерпретации. Пожалуйста, проверьте файл: {interpretation_path}"]
            else:
                # If not JSON, return the raw text split into chunks
                return [data[i:i+4000] for i in range(0, len(data), 4000)]
        
        # Extract and format each section of the interpretation
        formatted_messages = []
        
        if 'strategicInterpretation' in interpretation:
            interp = interpretation['strategicInterpretation']
            
            # Cognitive Ecosystem
            if 'cognitiveEcosystem' in interp:
                formatted_messages.append(f"<b>🧬 Когнитивная Экосистема</b>\n\n{interp['cognitiveEcosystem']}")
            
            # Business-User Tension
            if 'businessUserTension' in interp:
                formatted_messages.append(f"<b>⚖️ Напряжение Бизнес-Пользователь</b>\n\n{interp['businessUserTension']}")
            
            # Attention Architecture
            if 'attentionArchitecture' in interp:
                formatted_messages.append(f"<b>👁️ Архитектура Внимания</b>\n\n{interp['attentionArchitecture']}")
            
            # Perceptual Crossroads
            if 'perceptualCrossroads' in interp:
                formatted_messages.append(f"<b>🔀 Перцептивные Перекрестки</b>\n\n{interp['perceptualCrossroads']}")
            
            # Hidden Patterns
            if 'hiddenPatterns' in interp:
                formatted_messages.append(f"<b>🔍 Скрытые Паттерны</b>\n\n{interp['hiddenPatterns']}")
        else:
            # If structure is not as expected, return raw JSON
            formatted_messages.append(f"Структура интерпретации не соответствует ожидаемой. Сырые данные:\n\n{data[:3900]}...")
            
        return formatted_messages
            
    except Exception as e:
        logging.error(f"Error formatting interpretation: {e}", exc_info=True)
        return [f"Ошибка при форматировании интерпретации: {str(e)}"]

def format_recommendations(recommendations_path):
    """Format recommendations JSON into readable messages."""
    try:
        with open(recommendations_path, 'r', encoding='utf-8') as f:
            data = f.read()
            
        # Handle case when JSON is returned directly
        try:
            recommendations = json.loads(data)
        except json.JSONDecodeError:
            # Try to extract JSON from text if it's wrapped in backticks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', data, re.DOTALL)
            if json_match:
                try:
                    recommendations = json.loads(json_match.group(1))
                except:
                    return [f"Ошибка при парсинге JSON из рекомендаций. Пожалуйста, проверьте файл: {recommendations_path}"]
            else:
                # If not JSON, return the raw text split into chunks
                return [data[i:i+4000] for i in range(0, len(data), 4000)]
        
        # Extract and format each recommendation
        formatted_messages = []
        
        if 'strategicRecommendations' in recommendations:
            for i, rec in enumerate(recommendations['strategicRecommendations'], 1):
                msg = f"<b>💡 Рекомендация {i}: {rec.get('title', 'Без названия')}</b>\n\n"
                
                if 'problemStatement' in rec:
                    msg += f"<b>Проблема:</b>\n{rec['problemStatement']}\n\n"
                
                if 'solutionDescription' in rec:
                    msg += f"<b>Решение:</b>\n{rec['solutionDescription']}\n\n"
                
                if 'businessConstraints' in rec:
                    msg += f"<b>Бизнес-ограничения:</b>\n{rec['businessConstraints']}\n\n"
                
                if 'expectedImpact' in rec:
                    msg += f"<b>Ожидаемый эффект:</b>\n{rec['expectedImpact']}\n\n"
                
                if 'crossDomainExample' in rec:
                    msg += f"<b>Пример из другой области:</b>\n{rec['crossDomainExample']}\n\n"
                
                if 'testingApproach' in rec:
                    msg += f"<b>Подход к тестированию:</b>\n{rec['testingApproach']}"
                
                formatted_messages.append(msg)
        else:
            # If structure is not as expected, return raw JSON
            formatted_messages.append(f"Структура рекомендаций не соответствует ожидаемой. Сырые данные:\n\n{data[:3900]}...")
            
        return formatted_messages
            
    except Exception as e:
        logging.error(f"Error formatting recommendations: {e}", exc_info=True)
        return [f"Ошибка при форматировании рекомендаций: {str(e)}"]

# Register the router
dp.include_router(router)

async def main():
    # Skip pending updates
    await bot.delete_webhook(drop_pending_updates=True)
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.info("Starting bot...")
    asyncio.run(main()) 