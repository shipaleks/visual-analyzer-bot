#!/usr/bin/env python3
# Redeploy trigger: bump version to force Railway deploy - 2024-04-22 14:00:00 UTC
"""
Main pipeline script to run the full visual interface analysis.
"""

import os
import sys
import json
import subprocess
import argparse
from datetime import datetime
import shutil
import traceback # Added import
from pathlib import Path # Added import
from dotenv import load_dotenv # Added import
import firebase_admin # Added import
from firebase_admin import credentials, firestore # Added import
import io # Импортируем io

# --- Firebase Initialization ---
load_dotenv() # Load .env file for local testing

# --- ОТЛАДКА: Проверка переменной окружения ---
creds_json_str = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
if not creds_json_str:
    print("!!! ОТЛАДКА: Переменная окружения GOOGLE_APPLICATION_CREDENTIALS не найдена или пуста!")
    db = None # Установим db в None, если переменная не найдена
else:
    print("--- ОТЛАДКА: Переменная GOOGLE_APPLICATION_CREDENTIALS найдена. Попытка парсинга JSON...")
    try:
        # Попытка загрузить JSON, чтобы убедиться, что он валиден
        creds_info = json.loads(creds_json_str)
        print(f"--- ОТЛАДКА: JSON из переменной успешно распарсен. Project ID: {creds_info.get('project_id')} ---")

        # --- Явная инициализация из строки JSON ---
        # Оборачиваем строку в файлоподобный объект
        creds_json_io = io.StringIO(creds_json_str)
        cred = credentials.Certificate(creds_json_io)

        # Инициализация с явно указанными учетными данными
        try:
             if not firebase_admin._apps: # Проверяем, не инициализировано ли уже
                firebase_admin.initialize_app(cred) # Используем явные credentials
                print("--- Firebase Admin SDK инициализирован (явно из переменной) --- ")
             else:
                 print("--- Firebase Admin SDK уже был инициализирован --- ")

             # Get Firestore client
             try:
                 db = firestore.client()
                 print("--- Firestore клиент получен успешно --- ")
             except Exception as e:
                 print(f"!!! Ошибка получения Firestore клиента ПОСЛЕ ЯВНОЙ ИНИЦИАЛИЗАЦИИ: {e} !!!")
                 db = None
        except ValueError as e:
             if "The default Firebase app already exists" in str(e):
                 print("--- Firebase Admin SDK уже был инициализирован (value error) --- ")
                 # Если уже инициализировано, пытаемся получить клиент существующего приложения
                 try:
                     db = firestore.client()
                     print("--- Firestore клиент получен (из уже инициализированного приложения) --- ")
                 except Exception as e_inner:
                     print(f"!!! Ошибка получения Firestore клиента из уже инициализированного приложения: {e_inner} !!!")
                     db = None
             else:
                 print(f"!!! Ошибка явной инициализации Firebase: {e} !!!")
                 db = None
        except Exception as e:
             print(f"!!! Неожиданная ошибка явной инициализации Firebase: {e} !!!")
             db = None

    except json.JSONDecodeError as e:
        print(f"!!! ОТЛАДКА: Ошибка парсинга JSON из GOOGLE_APPLICATION_CREDENTIALS: {e} !!!")
        print("!!! ПОЖАЛУЙСТА, ПРОВЕРЬТЕ ЗНАЧЕНИЕ ПЕРЕМЕННОЙ В RAILWAY - ОНО ДОЛЖНО БЫТЬ ВАЛИДНЫМ JSON !!!")
        db = None
    except Exception as e:
        print(f"!!! ОТЛАДКА: Неожиданная ошибка при обработке переменной: {e} !!!")
        db = None

# --- КОНЕЦ ОТЛАДКИ ---

# Если инициализация выше не удалась, db будет None
if 'db' not in locals() or db is None: # Добавил проверку на None
    print("!!! Инициализация Firebase не удалась или клиент не получен.")
    db = None # Убедимся, что db None, если что-то пошло не так

# --- Configuration ---
# Определяем абсолютные пути к скриптам относительно текущего файла
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GET_GEMINI_REC_SCRIPT = os.path.join(SCRIPT_DIR, 'get_gemini_recommendations.py')
GENERATE_REPORT_SCRIPT = os.path.join(SCRIPT_DIR, 'generate_report_v2.py')

# Check if scripts exist
if not os.path.exists(GET_GEMINI_REC_SCRIPT):
    print(f"!!! Ошибка: Скрипт {GET_GEMINI_REC_SCRIPT} не найден !!!")
    # sys.exit(1) # Or handle differently
if not os.path.exists(GENERATE_REPORT_SCRIPT):
    print(f"!!! Ошибка: Скрипт {GENERATE_REPORT_SCRIPT} не найден !!!")
    # sys.exit(1)

# Default paths for prompts (relative to SCRIPT_DIR)
# Make sure these paths are correct within your project structure
DEFAULT_GPT_PROMPT = os.path.join(SCRIPT_DIR, 'tests', 'gpt_full_prompt.txt') # Corrected path to tests/
DEFAULT_INTERPRETATION_PROMPT = os.path.join(SCRIPT_DIR, 'gemini_interpretation_prompt.md')
DEFAULT_RECOMMENDATIONS_PROMPT = os.path.join(SCRIPT_DIR, 'gemini_recommendations_only_prompt.md')
DEFAULT_COORDS_PROMPT = os.path.join(SCRIPT_DIR, 'gemini_simple_prompt.md')

# Ensure Gemini simple prompt exists
if not os.path.exists(DEFAULT_COORDS_PROMPT):
    print(f"!!! Предупреждение: Gemini простой промпт не найден: {DEFAULT_COORDS_PROMPT}")
    # Try to find it in the tests directory
    alt_coords_prompt = os.path.join(SCRIPT_DIR, 'tests', 'gemini_simple_prompt.md')
    if os.path.exists(alt_coords_prompt):
        print(f"Найден альтернативный Gemini промпт: {alt_coords_prompt}")
        DEFAULT_COORDS_PROMPT = alt_coords_prompt
    else:
        print(f"!!! Предупреждение: Альтернативный промпт тоже не найден !!!")

# --- Helper Functions ---

def run_command(command, description):
    """Runs a command and prints status."""
    print(f"--- Запуск: {description} ---")
    print(f"Команда: {' '.join(command)}")
    try:
        # Changed to run without shell=True for better security and argument handling
        result = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8') # check=False to handle errors manually
        print("Вывод:")
        print(result.stdout)
        if result.stderr:
            print("Ошибки (stderr):") # Clarify this is stderr
            print(result.stderr)
        
        if result.returncode != 0:
            print(f"!!! Ошибка выполнения {description}: Команда завершилась с кодом {result.returncode}")
            print(f"--- Ошибка: {description} ---")
            return False, result.stderr or result.stdout # Return stderr if available, otherwise stdout
        
        print(f"--- Успешно: {description} ---")
        return True, result.stdout
    except FileNotFoundError as e:
        print(f"!!! Ошибка: Команда или скрипт не найден: {e}")
        print(f"--- Ошибка: {description} ---")
        return False, str(e)
    except Exception as e:
        print(f"!!! Неожиданная ошибка при выполнении {description}: {e}")
        traceback.print_exc() # Print traceback for unexpected errors
        print(f"--- Ошибка: {description} ---")
        return False, str(e)

# --- Function to save metrics --- 
def save_metrics_to_firebase(gpt_json_path, run_id, img_path, iface_type, scenario):
    """Loads metrics from GPT analysis JSON and saves them to Firestore."""
    if not db:
        print("!!! Firestore клиент недоступен, пропуск сохранения метрик !!!")
        return

    print(f"--- Попытка сохранения метрик из {gpt_json_path} в Firebase ---")
    try:
        with open(gpt_json_path, 'r', encoding='utf-8') as f:
            analysis_data = json.load(f)

        # Ищем ключ с метриками (предполагаем 'complexityScores')
        metrics_data = analysis_data.get('complexityScores')

        # Дополнительная проверка, если ключ верхнего уровня не найден
        if not metrics_data:
            if 'analysis_results' in analysis_data and isinstance(analysis_data['analysis_results'], dict):
                 metrics_data = analysis_data['analysis_results'].get('complexityScores')

        if not metrics_data or not isinstance(metrics_data, dict):
            # Пытаемся найти другой ключ, если 'complexityScores' не сработал
            found_metrics = False
            for key, value in analysis_data.items():
                 # Ищем словарь, который содержит много числовых значений (эвристика)
                 if isinstance(value, dict) and len(value) > 10 and sum(isinstance(v, (int, float)) for v in value.values()) > len(value) * 0.7:
                      print(f"Найдены возможные метрики под ключом: '{key}'")
                      metrics_data = value
                      found_metrics = True
                      break
            if not found_metrics:
                 print(f"!!! Ключ 'complexityScores' или похожий не найден в {gpt_json_path} или данные не являются словарем. Пропуск сохранения метрик.")
                 # Debug: print top-level keys
                 print(f"Top-level keys in {gpt_json_path}: {list(analysis_data.keys())}")
                 return

        # Подготовка данных для Firestore
        data_to_save = {
            'run_id': run_id, # Используем run_timestamp как ID запуска
            'timestamp': firestore.SERVER_TIMESTAMP, # Используем серверное время Firebase
            'image_reference': Path(img_path).name, # Сохраняем только имя файла изображения
            'interface_type': iface_type,
            'user_scenario': scenario,
            'metrics': metrics_data # Сохраняем весь словарь метрик
        }

        # Добавляем документ в коллекцию 'analysis_metrics'
        # Используем run_id как ID документа для предотвращения дубликатов при перезапуске
        doc_ref = db.collection('analysis_metrics').document(run_id)
        doc_ref.set(data_to_save)
        print(f"--- Метрики успешно сохранены/обновлены в Firebase. Document ID: {run_id} ---")

    except FileNotFoundError:
        print(f"!!! Ошибка: Файл {gpt_json_path} не найден. Не могу сохранить метрики.")
    except json.JSONDecodeError:
        print(f"!!! Ошибка: Не удалось декодировать JSON из {gpt_json_path}. Не могу сохранить метрики.")
    except Exception as e:
        print(f"!!! Неожиданная ошибка при сохранении метрик в Firebase: {e}")
        traceback.print_exc()

# --- Main Pipeline Logic ---
def run_pipeline(image_path, interface_type="Анализируемый интерфейс", user_scenario="Общий анализ"):
    """Runs the entire analysis pipeline."""
    if not os.path.exists(image_path):
        print(f"!!! Ошибка: Файл изображения не найден по пути {image_path} !!!")
        return

    # Generate a unique run ID based on timestamp
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(SCRIPT_DIR, f"analysis_outputs/run_{run_timestamp}")
    try:
        os.makedirs(output_dir, exist_ok=True)
        print(f"--- Результаты будут сохранены в: {output_dir.replace(SCRIPT_DIR, '.') } --- \n")
    except OSError as e:
         print(f"!!! Ошибка создания директории {output_dir}: {e} !!!")
         return

    # --- Define output file paths ---
    gpt_analysis_output = os.path.join(output_dir, f"gpt_analysis_{run_timestamp}.json")
    gemini_coords_raw_output = os.path.join(output_dir, f"gemini_coords_raw_{run_timestamp}.json")
    gemini_coords_parsed_output = os.path.join(output_dir, f"gemini_coords_parsed_{run_timestamp}.json")
    heatmap_output = os.path.join(output_dir, f"heatmap_{run_timestamp}.png")
    interpretation_output = os.path.join(output_dir, f"interpretation_{run_timestamp}.json")
    recommendations_output = os.path.join(output_dir, f"recommendations_{run_timestamp}.json")
    report_base_output = os.path.join(output_dir, f"report_{run_timestamp}") # Base name for .tex and .pdf
    report_pdf_output = f"{report_base_output}.pdf"

    pipeline_success = True
    pipeline_error_details = ""

    try:
        # --- 1. Set Context (No interactive input) ---
        print("--- Контекст анализа ---")
        print(f"    Тип интерфейса: {interface_type}")
        print(f"    Сценарий: {user_scenario}")

        # --- 2. Run GPT-4 Analysis (Using api_test.py function) ---
        print(f"--- Запуск GPT-4.1 Анализа для: {image_path} ---")
        try:
            # Dynamically import api_test.py or ensure it's in PYTHONPATH
            # Assuming api_test is in the 'tests' subdirectory relative to SCRIPT_DIR
            tests_dir = os.path.join(SCRIPT_DIR, 'tests')
            if tests_dir not in sys.path:
                sys.path.insert(0, tests_dir) # Add tests dir to path for import
                
            # Check if the prompt file exists
            if not os.path.exists(DEFAULT_GPT_PROMPT):
                 print(f"!!! Ошибка: Файл GPT промпта не найден: {DEFAULT_GPT_PROMPT} !!!")
                 raise FileNotFoundError(f"Prompt file not found: {DEFAULT_GPT_PROMPT}")
            
            from api_test import run_gpt_analysis # Corrected function name

            success, gpt_result_data = run_gpt_analysis( # Corrected function call
                image_path=image_path,
                output_json_path=gpt_analysis_output,
                interface_type=interface_type,
                user_scenario=user_scenario,
                # Pass the correct gpt_prompt_path here if run_gpt_analysis needs it
                # gpt_prompt_path=DEFAULT_GPT_PROMPT # This might be handled inside run_gpt_analysis now
            )
            if not success:
                print("!!! Ошибка выполнения GPT-4.1 Анализа через api_test.py !!!")
                pipeline_success = False
                pipeline_error_details += "GPT-4 Analysis failed.\n"
            else:
                print(f"    Результат GPT анализа сохранен в: {gpt_analysis_output}")
                print("--- Успешно: GPT-4.1 Анализ ---")

            # --- Save Metrics to Firebase ---
            if pipeline_success and os.path.exists(gpt_analysis_output) and db: # Проверяем, что анализ успешен, файл есть и db инициализирован
                 save_metrics_to_firebase(
                     gpt_json_path=gpt_analysis_output,
                     run_id=run_timestamp, # Передаем run_timestamp
                     img_path=image_path, # Передаем исходный путь к картинке
                     iface_type=interface_type,
                     scenario=user_scenario
                 )
            elif not db:
                 print("--- Пропуск сохранения метрик в Firebase (клиент не инициализирован) ---")
            elif not os.path.exists(gpt_analysis_output):
                 print("--- Пропуск сохранения метрик в Firebase (файл анализа GPT не найден) ---")
            elif not pipeline_success:
                 print("--- Пропуск сохранения метрик в Firebase (анализ GPT завершился с ошибкой) ---")

        except ImportError as e:
            print(f"!!! Ошибка импорта функций из tests/api_test.py: {e} !!!")
            print("Убедитесь, что файл tests/api_test.py существует и python может его найти.")
            pipeline_success = False
            pipeline_error_details += "Failed to import from api_test.py.\n"
        except FileNotFoundError as e:
            print(f"!!! Ошибка: {e} !!!") # Print file not found error from above check
            pipeline_success = False
            pipeline_error_details += str(e)
        except Exception as e:
            print(f"!!! Ошибка при вызове функции из api_test.py: {e} !!!")
            traceback.print_exc()
            pipeline_success = False
            pipeline_error_details += f"Error during api_test.py execution: {e}\n"

        # --- 3. Run Gemini Coordinates (Using api_test.py function) ---
        if pipeline_success: 
            print(f"--- Запуск Gemini Координат для: {image_path} ---")
            try:
                # Ensure tests dir is still in path if needed
                tests_dir = os.path.join(SCRIPT_DIR, 'tests')
                if tests_dir not in sys.path:
                     sys.path.insert(0, tests_dir)
                
                if not os.path.exists(DEFAULT_COORDS_PROMPT):
                     print(f"!!! Ошибка: Файл Gemini координат промпта не найден: {DEFAULT_COORDS_PROMPT} !!!")
                     # Try to create a default simple prompt
                     try:
                         simple_prompt = """You are a specialized visual analysis system designed to extract precise coordinates for identified UI usability issues in images. Your task is to locate specific problematic elements and provide their bounding box coordinates using a normalized coordinate system."""
                         os.makedirs(os.path.dirname(DEFAULT_COORDS_PROMPT), exist_ok=True)
                         with open(DEFAULT_COORDS_PROMPT, 'w') as f:
                             f.write(simple_prompt)
                         print(f"Создан стандартный промпт в: {DEFAULT_COORDS_PROMPT}")
                     except Exception as e:
                         print(f"Не удалось создать стандартный промпт: {e}")
                         raise FileNotFoundError(f"Coords prompt file not found and couldn't create default: {DEFAULT_COORDS_PROMPT}")
                     
                from api_test import run_gemini_coordinates # Corrected function name
                
                # Check if gpt_result_data exists from previous step
                if 'gpt_result_data' not in locals() or gpt_result_data is None:
                    print("!!! Ошибка: Данные GPT анализа отсутствуют, невозможно запустить Gemini Координаты !!!")
                    raise ValueError("Missing GPT analysis data for Gemini Coordinates")
                    
                coords_result_data = run_gemini_coordinates(
                    image_path=image_path,
                    gpt_result_data=gpt_result_data,
                    output_raw_json_path=gemini_coords_raw_output,
                    output_parsed_json_path=gemini_coords_parsed_output
                )
                if not coords_result_data:
                    print("!!! Предупреждение: Gemini Координаты не были получены; создаю пустую структуру !!!")
                    # Create an empty coordinates structure 
                    coords_result_data = {"element_coordinates": []}
                    # Save empty structure
                    os.makedirs(os.path.dirname(gemini_coords_parsed_output), exist_ok=True)
                    with open(gemini_coords_parsed_output, 'w') as f:
                        json.dump(coords_result_data, f)
                    print(f"Создана пустая структура координат: {gemini_coords_parsed_output}")
                    pipeline_error_details += "Gemini Coordinates failed; created empty coordinates structure.\n"
                else:
                    print(f"    Raw Gemini ответ сохранен в: {gemini_coords_raw_output}")
                    print(f"    Распарсенный Gemini ответ сохранен в: {gemini_coords_parsed_output}")
                    print("--- Успешно: Gemini Координаты ---")

            except ImportError as e:
                print(f"!!! Ошибка импорта функций из tests/api_test.py (для Координат): {e} !!!")
                pipeline_error_details += "Failed to import from api_test.py (for Coords).\n"
            except FileNotFoundError as e:
                print(f"!!! Ошибка: {e} !!!") 
                pipeline_error_details += str(e) + "\n"
            except Exception as e:
                print(f"!!! Ошибка при вызове функции из api_test.py (для Координат): {e} !!!")
                traceback.print_exc()
                pipeline_error_details += f"Error during api_test.py execution (for Coords): {e}\n"

        # --- 4. Generate Heatmap (Using api_test.py function) ---
        if pipeline_success: # Changed from checking gemini_coords_parsed_output exists
            print(f"--- Запуск Генерации Тепловой Карты для: {image_path} ---")
            print(f"    Сохранение в: {heatmap_output}")
            try:
                # Ensure tests dir is still in path if needed
                tests_dir = os.path.join(SCRIPT_DIR, 'tests')
                if tests_dir not in sys.path:
                     sys.path.insert(0, tests_dir)
                     
                from api_test import generate_heatmap # Corrected function name

                # Check if needed data exists
                if 'gpt_result_data' not in locals() or gpt_result_data is None:
                    print("!!! Ошибка: Данные GPT анализа отсутствуют, невозможно запустить Генерацию Тепловой Карты !!!")
                    raise ValueError("Missing GPT analysis data for Heatmap Generation")
                    
                # If coords_result_data is not available, create an empty one
                if 'coords_result_data' not in locals() or coords_result_data is None:
                     print("!!! Предупреждение: Данные координат отсутствуют, создаю пустую структуру !!!")
                     coords_result_data = {"element_coordinates": []}

                # Pass the loaded dictionary for gpt_result_data
                # Pass the dictionary returned by run_gemini_coordinates for coordinates_data
                success = generate_heatmap( # Corrected function call
                    image_path=image_path,
                    coordinates_data=coords_result_data, # Pass the loaded coords dictionary
                    gpt_result_data=gpt_result_data, # Pass the loaded gpt dictionary
                    output_heatmap_path=heatmap_output
                )
                
                if success:
                    print(f"    Тепловая карта успешно сгенерирована и сохранена в: {heatmap_output}")
                    print("--- Успешно: Генерация Тепловой Карты ---")
                else:
                    print("!!! Ошибка: не удалось сгенерировать тепловую карту !!!")
                    pipeline_error_details += "Heatmap generation failed.\n"
                    # Try to create a basic placeholder image
                    try:
                        import matplotlib.pyplot as plt
                        import numpy as np
                        from PIL import Image
                        
                        # Create a simple placeholder
                        plt.figure(figsize=(8, 6))
                        plt.text(0.5, 0.5, "Heatmap generation failed", 
                                ha='center', va='center', fontsize=20, color='red',
                                bbox=dict(facecolor='white', alpha=0.8))
                        plt.axis('off')
                        os.makedirs(os.path.dirname(heatmap_output), exist_ok=True)
                        plt.savefig(heatmap_output)
                        plt.close()
                        print(f"Создана заглушка тепловой карты в: {heatmap_output}")
                    except Exception as e:
                        print(f"Не удалось создать заглушку тепловой карты: {e}")

            except ImportError as e:
                print(f"!!! Ошибка импорта функций из tests/api_test.py (для Тепловой Карты): {e} !!!")
                pipeline_error_details += "Failed to import from api_test.py (for Heatmap).\n"
                
                # Try to create a fallback heatmap without importing the module
                try:
                    import matplotlib.pyplot as plt
                    from PIL import Image
                    
                    # Create a simple heatmap message
                    img = Image.open(image_path)
                    plt.figure(figsize=(img.width/100, img.height/100), dpi=100)
                    plt.imshow(np.array(img))
                    plt.text(img.width/2, img.height/2, "Ошибка импорта модуля для тепловой карты", 
                            ha='center', va='center', fontsize=20, color='red',
                            bbox=dict(facecolor='white', alpha=0.8))
                    plt.axis('off')
                    os.makedirs(os.path.dirname(heatmap_output), exist_ok=True)
                    plt.savefig(heatmap_output)
                    plt.close()
                    print(f"Создана заглушка тепловой карты в: {heatmap_output}")
                except Exception as e2:
                    print(f"Не удалось создать заглушку тепловой карты: {e2}")
            
            except Exception as e:
                print(f"!!! Ошибка при вызове функции из api_test.py (для Тепловой Карты): {e} !!!")
                pipeline_error_details += f"Error during api_test.py execution (for Heatmap): {e}\n"
                traceback.print_exc()

        # --- 5. Run Gemini Interpretation --- (Uses get_gemini_recommendations.py script)
        if pipeline_success and os.path.exists(gpt_analysis_output):
             if not os.path.exists(DEFAULT_INTERPRETATION_PROMPT):
                  print(f"!!! Ошибка: Файл промпта Интерпретации не найден: {DEFAULT_INTERPRETATION_PROMPT} !!!")
                  pipeline_success = False
                  pipeline_error_details += f"Interpretation prompt file not found: {DEFAULT_INTERPRETATION_PROMPT}\n"
             else:
                 command = [
                     sys.executable, GET_GEMINI_REC_SCRIPT,
                     '--input', gpt_analysis_output,
                     '--prompt-file', DEFAULT_INTERPRETATION_PROMPT,
                     '--output', interpretation_output
                 ]
                 success, stderr_out = run_command(command, "Gemini Интерпретация")
                 if not success:
                     pipeline_success = False
                     pipeline_error_details += f"Gemini Interpretation failed. Details: {stderr_out}\n"
        elif pipeline_success:
            print("--- Пропуск Gemini Интерпретации (нет файла GPT анализа) --- ")

        # --- 6. Run Gemini Recommendations --- (Uses get_gemini_recommendations.py script)
        if pipeline_success and os.path.exists(gpt_analysis_output):
            if not os.path.exists(DEFAULT_RECOMMENDATIONS_PROMPT):
                 print(f"!!! Ошибка: Файл промпта Рекомендаций не найден: {DEFAULT_RECOMMENDATIONS_PROMPT} !!!")
                 pipeline_success = False
                 pipeline_error_details += f"Recommendations prompt file not found: {DEFAULT_RECOMMENDATIONS_PROMPT}\n"
            else:
                command = [
                    sys.executable, GET_GEMINI_REC_SCRIPT,
                    '--input', gpt_analysis_output,
                    '--prompt-file', DEFAULT_RECOMMENDATIONS_PROMPT,
                    '--output', recommendations_output
                ]
                success, stderr_out = run_command(command, "Gemini Рекомендации")
                if not success:
                     pipeline_success = False
                     pipeline_error_details += f"Gemini Recommendations failed. Details: {stderr_out}\n"
        elif pipeline_success:
            print("--- Пропуск Gemini Рекомендаций (нет файла GPT анализа) --- ")

        # --- 7. Generate Report --- (Uses generate_report_v2.py script)
        if pipeline_success and os.path.exists(gpt_analysis_output):
            command = [
                sys.executable, GENERATE_REPORT_SCRIPT,
                '--input', gpt_analysis_output,
                '--output', report_base_output, # Pass base path
                '--image', image_path,
                '--pdf' # Always generate PDF
            ]
            # Add optional files if they exist
            if os.path.exists(gemini_coords_parsed_output):
                command.extend(['--gemini-data', gemini_coords_parsed_output])
            if os.path.exists(heatmap_output):
                command.extend(['--heatmap', heatmap_output])

            success, report_stderr_out = run_command(command, "Генерация Отчета (LaTeX + PDF)")
            if not success:
                 pipeline_success = False # Report generation failed
                 pipeline_error_details += f"Report Generation failed. Details: {report_stderr_out}\n"
        elif pipeline_success:
             print("--- Пропуск Генерации Отчета (нет файла GPT анализа) --- ")

    except Exception as e:
        print(f"!!! Неожиданная ошибка в главном пайплайне: {e} !!!")
        traceback.print_exc() # Now traceback is imported
        pipeline_success = False
        pipeline_error_details += f"Unexpected pipeline error: {e}\n"

    # --- Copy final results to input image directory ---
    print("\n--- Копирование финальных результатов в директорию исходного изображения ---")
    target_pdf_path = None
    target_heatmap_path = None
    target_interpretation_path = None
    target_recommendations_path = None
    try:
        input_path = Path(image_path)
        input_dir = input_path.parent
        input_base_name = input_path.stem
        target_pdf_path = input_dir / f"{input_base_name}_report.pdf"
        target_heatmap_path = input_dir / f"{input_base_name}_heatmap.png"
        target_interpretation_path = input_dir / f"{input_base_name}_interpretation.json"
        target_recommendations_path = input_dir / f"{input_base_name}_recommendations.json"

        source_pdf_path = Path(report_pdf_output)
        source_heatmap_path = Path(heatmap_output)
        source_interpretation_path = Path(interpretation_output)
        source_recommendations_path = Path(recommendations_output)

        if source_pdf_path.exists():
            shutil.copy2(str(source_pdf_path), str(target_pdf_path))
            print(f"✅ PDF отчет скопирован в: {target_pdf_path}")
        else:
             print(f"⚠️ Исходный PDF отчет не найден для копирования: {source_pdf_path}")

        if source_heatmap_path.exists():
            shutil.copy2(str(source_heatmap_path), str(target_heatmap_path))
            print(f"✅ Тепловая карта скопирована в: {target_heatmap_path}")
        else:
             print(f"⚠️ Исходная тепловая карта не найдена для копирования: {source_heatmap_path}")

        # Copy Interpretation JSON
        if source_interpretation_path.exists():
            shutil.copy2(str(source_interpretation_path), str(target_interpretation_path))
            print(f"✅ JSON интерпретации скопирован в: {target_interpretation_path}")
        else:
             print(f"⚠️ Исходный JSON интерпретации не найден для копирования: {source_interpretation_path}")

        # Copy Recommendations JSON
        if source_recommendations_path.exists():
            shutil.copy2(str(source_recommendations_path), str(target_recommendations_path))
            print(f"✅ JSON рекомендаций скопирован в: {target_recommendations_path}")
        else:
             print(f"⚠️ Исходный JSON рекомендаций не найден для копирования: {source_recommendations_path}")


    except Exception as e:
        print(f"!!! Ошибка при копировании финальных результатов: {e}")
        traceback.print_exc()
        # We don't mark pipeline as failed here, just report the copy error

    # --- Final Summary ---
    print("\n============================== ИТОГОВЫЕ РЕЗУЛЬТАТЫ ==============================")
    # Check existence of final outputs in the original output_dir
    final_tex_exists = os.path.exists(f"{report_base_output}.tex")
    final_pdf_exists = os.path.exists(report_pdf_output)
    final_heatmap_exists = os.path.exists(heatmap_output)
    final_interpretation_exists = os.path.exists(interpretation_output)
    final_recommendations_exists = os.path.exists(recommendations_output)

    # Check existence of final outputs in the TARGET directory now
    target_pdf_exists = target_pdf_path.exists() if target_pdf_path else False
    target_heatmap_exists = target_heatmap_path.exists() if target_heatmap_path else False
    target_interpretation_exists = target_interpretation_path.exists() if target_interpretation_path else False
    target_recommendations_exists = target_recommendations_path.exists() if target_recommendations_path else False

    # Update final summary based on copied files
    if target_pdf_exists:
        print(f"✅ PDF Отчет (скопированный): {target_pdf_path}")
    elif final_pdf_exists:
        print(f"✅ PDF Отчет (исходный): {report_pdf_output}")
    elif final_tex_exists:
        print(f"✅ LaTeX Отчет (.tex): {report_base_output}.tex")
        print("⚠️ PDF генерация пропущена или копирование не удалось. Вы можете скомпилировать .tex вручную или проверить логи копирования.")
    else:
        print("❌ Отчет не был сгенерирован или скопирован.")

    if target_heatmap_exists:
        print(f"✅ Тепловая карта (скопированная): {target_heatmap_path}")
    elif final_heatmap_exists:
        print(f"✅ Тепловая карта (исходная): {heatmap_output}")
    else:
        print("❌ Тепловая карта не была сгенерирована или скопирована.")

    if target_interpretation_exists:
        print(f"✅ Файл интерпретации (скопированный): {target_interpretation_path}")
    elif final_interpretation_exists:
        print(f"✅ Файл интерпретации (исходный): {interpretation_output}")
    else:
        print("❌ Файл интерпретации не был сгенерирован или скопирован.")

    if target_recommendations_exists:
        print(f"✅ Файл рекомендаций (скопированный): {target_recommendations_path}")
    elif final_recommendations_exists:
        print(f"✅ Файл рекомендаций (исходный): {recommendations_output}")
    else:
        print("❌ Файл рекомендаций не был сгенерирован или скопирован.")

    if not pipeline_success:
        print("\n--- ❗️ Ошибки во время выполнения пайплайна --- ")
        # Print only the accumulated error details
        print(pipeline_error_details.strip())
        print("--- Конец ошибок ---")

    print("\n============================== ЗАВЕРШЕНИЕ ПАЙПЛАЙНА ==============================")

    # Exit with success if at least the COPIED PDF exists, or fallback to original PDF/Tex
    # Also consider copied heatmap and JSONs for a more complete success indication
    if target_pdf_exists and target_heatmap_exists:
        print("✅ Основные результаты (PDF, Heatmap) скопированы.")
        sys.exit(0)
    elif target_pdf_exists:
        print("⚠️ PDF скопирован, но карта и/или JSON не были скопированы.")
        sys.exit(0) # Exit successfully if at least PDF is copied
    elif final_pdf_exists or final_tex_exists:
        print("⚠️ Пайплайн завершен, но финальные результаты не были скопированы в директорию user_images. Бот может не найти результаты.")
        sys.exit(0) # Still exit successfully if original PDF/TEX exists
    else:
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Запускает полный пайплайн анализа визуального интерфейса.")
    parser.add_argument("--image-path", required=True, help="Путь к файлу изображения для анализа.")
    parser.add_argument("--interface-type", default="Не указан", help="Тип анализируемого интерфейса (например, 'форма регистрации').")
    parser.add_argument("--user-scenario", default="Не указан", help="Типичный сценарий использования интерфейса (например, 'заполнение профиля').")

    args = parser.parse_args()

    # Проверяем существование файла изображения перед запуском
    if not os.path.exists(args.image_path):
        print(f"!!! КРИТИЧЕСКАЯ ОШИБКА: Файл изображения не найден: {args.image_path} !!!")
        sys.exit(1) # Выход с ошибкой

    # Запуск основного пайплайна
    run_pipeline(
        image_path=args.image_path, 
        interface_type=args.interface_type, 
        user_scenario=args.user_scenario
    ) 