#!/usr/bin/env python3
# Redeploy trigger: bump version to force Railway deploy
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
DEFAULT_COORDS_PROMPT = os.path.join(SCRIPT_DIR, 'gemini_simple_prompt.md') # Assuming this is the coords prompt

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

# --- Main Pipeline Logic ---
def run_pipeline(image_path):
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
        # Using default values instead of input()
        interface_type = "Анализируемый интерфейс" 
        user_scenario = "Общий анализ"
        print("--- Контекст анализа (задан по умолчанию) ---")
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
                     raise FileNotFoundError(f"Coords prompt file not found: {DEFAULT_COORDS_PROMPT}")
                     
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
                    print("!!! Ошибка выполнения Gemini Координат через api_test.py !!!")
                    pipeline_success = False # Coordinates are likely critical
                    pipeline_error_details += "Gemini Coordinates failed.\n"
                else:
                    print(f"    Raw Gemini ответ сохранен в: {gemini_coords_raw_output}")
                    print(f"    Распарсенный Gemini ответ сохранен в: {gemini_coords_parsed_output}")
                    print("--- Успешно: Gemini Координаты ---")

            except ImportError as e:
                print(f"!!! Ошибка импорта функций из tests/api_test.py (для Координат): {e} !!!")
                pipeline_success = False 
                pipeline_error_details += "Failed to import from api_test.py (for Coords).\n"
            except FileNotFoundError as e:
                print(f"!!! Ошибка: {e} !!!") 
                pipeline_success = False
                pipeline_error_details += str(e)
            except Exception as e:
                print(f"!!! Ошибка при вызове функции из api_test.py (для Координат): {e} !!!")
                traceback.print_exc()
                pipeline_success = False
                pipeline_error_details += f"Error during api_test.py execution (for Coords): {e}\n"

        # --- 4. Generate Heatmap (Using api_test.py function) ---
        if pipeline_success and os.path.exists(gemini_coords_parsed_output):
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
                if 'coords_result_data' not in locals() or coords_result_data is None:
                     print("!!! Ошибка: Данные координат отсутствуют, невозможно запустить Генерацию Тепловой Карты !!!")
                     raise ValueError("Missing Coordinates data for Heatmap Generation")

                # Pass the loaded dictionary for gpt_result_data
                # Pass the dictionary returned by run_gemini_coordinates for coordinates_data
                success = generate_heatmap( # Corrected function call
                    image_path=image_path,
                    coordinates_data=coords_result_data, # Pass the loaded coords dictionary
                    gpt_result_data=gpt_result_data, # Pass the loaded gpt dictionary
                    output_heatmap_path=heatmap_output
                )
                if not success:
                    print("!!! Ошибка Генерации Тепловой Карты через api_test.py !!!")
                    # pipeline_success = False # Maybe not critical
                    pipeline_error_details += "Heatmap Generation failed.\n"
                else:
                    print(f"    Тепловая карта успешно сгенерирована и сохранена в: {heatmap_output}")
                    print("--- Успешно: Генерация Тепловой Карты ---")

            except ImportError as e:
                print(f"!!! Ошибка импорта функций из tests/api_test.py (для Тепловой Карты): {e} !!!")
                pipeline_error_details += "Failed to import from api_test.py (for Heatmap).\n"
            except Exception as e:
                print(f"!!! Ошибка при вызове функции из api_test.py (для Тепловой Карты): {e} !!!")
                traceback.print_exc()
                pipeline_error_details += f"Error during api_test.py execution (for Heatmap): {e}\n"
        elif pipeline_success: # Only print skip message if coords step was attempted but failed/skipped
            print("--- Пропуск Генерации Тепловой Карты (нет файла координат) --- ")

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

    # --- Final Summary ---
    print("\n============================== ИТОГОВЫЕ РЕЗУЛЬТАТЫ ==============================\n")
    # Check existence of final outputs
    final_pdf_exists = os.path.exists(report_pdf_output)
    final_heatmap_exists = os.path.exists(heatmap_output)
    final_interpretation_exists = os.path.exists(interpretation_output)
    final_recommendations_exists = os.path.exists(recommendations_output)

    if final_pdf_exists:
        print(f"✅ PDF Отчет: {report_pdf_output}")
    else:
        print("❌ Отчет (PDF/LaTeX) не был сгенерирован.")

    if final_heatmap_exists:
        print(f"✅ Тепловая карта: {heatmap_output}")
    else:
        print("❌ Тепловая карта не была сгенерирована.")

    if final_interpretation_exists:
        print(f"✅ Файл интерпретации: {interpretation_output}")
    else:
        print("❌ Файл интерпретации не был сгенерирован.")

    if final_recommendations_exists:
        print(f"✅ Файл рекомендаций: {recommendations_output}")
    else:
        print("❌ Файл рекомендаций не был сгенерирован.")

    if not pipeline_success:
        print("\n--- ❗️ Ошибки во время выполнения пайплайна --- ")
        # Print only the accumulated error details
        print(pipeline_error_details.strip())
        print("--- Конец ошибок ---")

    print("\n============================== ЗАВЕРШЕНИЕ ПАЙПЛАЙНА ==============================\n")

    # Exit with error code if pipeline failed or final report PDF is missing
    if not pipeline_success or not final_pdf_exists:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full UI analysis pipeline.")
    parser.add_argument("image_path", help="Path to the input screenshot image.")
    # Add optional args for prompts if needed later
    args = parser.parse_args()

    run_pipeline(args.image_path) 