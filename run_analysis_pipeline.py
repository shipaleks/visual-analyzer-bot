#!/usr/bin/env python3
"""
Main Orchestration Script for the Visual Interface Analyzer Pipeline.

This script coordinates the execution of various analysis components:
1.  User input for context (interface type, user flow).
2.  GPT-4.1 analysis of the screenshot.
3.  Gemini coordinate extraction for problem areas.
4.  Heatmap generation.
5.  Gemini strategic interpretation.
6.  Gemini strategic recommendations.
7.  LaTeX/PDF report generation.
"""

import os
import sys
import subprocess
import argparse
import json
from datetime import datetime

# --- Configuration ---
GPT_MODEL = "gpt-4.1"  # Ensure consistency, though scripts define their own
GEMINI_MODEL = "gemini-2.5-pro-preview-03-25" # Ensure consistency

# --- Add tests directory to Python Path for import ---
# This allows importing from the 'tests' directory directly
current_dir = os.path.dirname(os.path.abspath(__file__))
tests_dir = os.path.join(current_dir, 'tests')
if tests_dir not in sys.path:
    sys.path.insert(0, tests_dir)

# --- Import Refactored Functions ---
try:
    # Assuming api_test.py is in the 'tests' directory relative to this script
    from api_test import run_gpt_analysis, run_gemini_coordinates, generate_heatmap
except ImportError as e:
    print(f"!!! Ошибка импорта функций из tests/api_test.py: {e} !!!")
    print("Убедитесь, что файл tests/api_test.py существует и не содержит синтаксических ошибок.")
    sys.exit(1)
except EnvironmentError as e:
    print(f"!!! Ошибка инициализации API (из tests/api_test.py): {e} !!!")
    sys.exit(1)


# Define script paths (adjust if necessary)
# API_TEST_SCRIPT = os.path.join("tests", "api_test.py") # No longer needed
REPORT_SCRIPT = "generate_report_v2.py"
GEMINI_REC_SCRIPT = "get_gemini_recommendations.py"

# Define prompt file paths
INTERPRETATION_PROMPT = "gemini_interpretation_prompt.md"
RECOMMENDATIONS_PROMPT = "gemini_recommendations_only_prompt.md"

# Define base directories
OUTPUT_DIR = "analysis_outputs"
# Define output subdirectories based on timestamp later

# --- Helper Functions ---

def run_command(command_list, description):
    """Runs a subprocess command and checks for errors."""
    print(f"--- Запуск: {description} ---")
    print(f"Команда: {' '.join(command_list)}")
    try:
        # Run with utf-8 encoding explicitly specified for stdout/stderr
        result = subprocess.run(command_list, check=True, capture_output=True, text=True, encoding='utf-8')
        print(f"Вывод:\n{result.stdout}")
        if result.stderr:
            print(f"Ошибки:\n{result.stderr}")
        print(f"--- Успешно: {description} ---")
        return True
    except subprocess.CalledProcessError as e:
        print(f"!!! Ошибка при выполнении: {description} !!!")
        print(f"Код возврата: {e.returncode}")
        # Decode stdout/stderr if they are bytes
        stdout = e.stdout.decode('utf-8', errors='ignore') if isinstance(e.stdout, bytes) else e.stdout
        stderr = e.stderr.decode('utf-8', errors='ignore') if isinstance(e.stderr, bytes) else e.stderr
        print(f"Вывод:\n{stdout}")
        print(f"Ошибки:\n{stderr}")
        return False
    except FileNotFoundError:
         print(f"!!! Ошибка: Команда не найдена (возможно, 'python' или путь к скрипту неверный) для '{description}' !!!")
         return False
    except Exception as e:
        print(f"!!! Неожиданная ошибка при выполнении {description}: {e} !!!")
        return False

def get_user_context():
    """Get interface type and user scenario from the user."""
    print("\n--- Сбор контекста ---")
    interface_type = input("Пожалуйста, опишите тип интерфейса (например, 'Страница результатов поиска Google', 'Форма заказа пиццы'): ")
    user_scenario = input("Пожалуйста, опишите основной сценарий пользователя (например, 'Ищет информацию о погоде', 'Пытается оформить заказ'): ")
    
    if not interface_type:
        interface_type = "Не указано"
        print("Тип интерфейса не указан, используется значение по умолчанию.")
        
    if not user_scenario:
        user_scenario = "Не указано"
        print("Сценарий пользователя не указан, используется значение по умолчанию.")
        
    return interface_type, user_scenario

# --- Main Pipeline ---

def run_pipeline(image_path):
    """Executes the full analysis pipeline."""
    
    abs_image_path = os.path.abspath(image_path)
    if not os.path.exists(abs_image_path):
        print(f"!!! Ошибка: Файл изображения не найден по пути: {abs_image_path} !!!")
        return

    # Generate unique timestamp and create dedicated output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_output_dir = os.path.join(OUTPUT_DIR, f"run_{timestamp}") 
    os.makedirs(run_output_dir, exist_ok=True)
    print(f"--- Результаты будут сохранены в: {run_output_dir} --- ")
    
    # Define output file paths within the run-specific directory
    gpt_analysis_output_path = os.path.join(run_output_dir, f"gpt_analysis_{timestamp}.json")
    gemini_coords_raw_path = os.path.join(run_output_dir, f"gemini_coords_raw_{timestamp}.json")
    gemini_coords_parsed_path = os.path.join(run_output_dir, f"gemini_coords_parsed_{timestamp}.json")
    heatmap_output_path = os.path.join(run_output_dir, f"heatmap_{timestamp}.png")
    interpretation_output_path = os.path.join(run_output_dir, f"interpretation_{timestamp}.json")
    recommendations_output_path = os.path.join(run_output_dir, f"recommendations_{timestamp}.json")
    report_output_base_path = os.path.join(run_output_dir, f"report_{timestamp}") # for .tex and .pdf

    # --- Pipeline Steps ---
    gpt_analysis_data = None
    gemini_coords_data = None
    heatmap_success = False

    try:
        # 1. Get User Context (Steps 2 & 3)
        interface_type, user_scenario = get_user_context()
        # Step 4 (Gemini context fallback) is skipped for now.

        # 2. Run GPT Analysis (Step 5 - using imported function)
        gpt_analysis_data = run_gpt_analysis(abs_image_path, interface_type, user_scenario, gpt_analysis_output_path)
        if gpt_analysis_data is None:
            print("!!! Ошибка: Анализ GPT не удался. Прерывание пайплайна. !!!")
            return # Stop pipeline if GPT fails

        # 3. Run Gemini Coordinates (Step 7 - using imported function)
        gemini_coords_data = run_gemini_coordinates(abs_image_path, gpt_analysis_data, gemini_coords_raw_path, gemini_coords_parsed_path)
        if gemini_coords_data is None:
             print("--- Предупреждение: Не удалось получить координаты Gemini. Тепловая карта и детализация в отчете могут отсутствовать. ---")
             # Continue pipeline, but heatmap/report will lack coordinates
        
        # 4. Generate Heatmap (Step 6 - using imported function)
        if gemini_coords_data:
            heatmap_success = generate_heatmap(abs_image_path, gemini_coords_data, gpt_analysis_data, heatmap_output_path)
            if not heatmap_success:
                print("--- Предупреждение: Не удалось сгенерировать тепловую карту. ---")
        else:
            print("--- Пропуск генерации тепловой карты: нет данных координат. ---")

        # 5. Run Gemini Interpretation (Step 9a - subprocess)
        cmd_interpret = [
            sys.executable, GEMINI_REC_SCRIPT, # Use sys.executable for safety
            "--input", gpt_analysis_output_path,
            "--prompt-file", INTERPRETATION_PROMPT,
            "--output", interpretation_output_path
        ]
        if not run_command(cmd_interpret, "Gemini Интерпретация"): 
            print("--- Предупреждение: Не удалось выполнить Gemini Интерпретацию. ---")
            # Continue pipeline

        # 6. Run Gemini Recommendations (Step 9b - subprocess)
        cmd_recommend = [
            sys.executable, GEMINI_REC_SCRIPT,
            "--input", gpt_analysis_output_path,
            "--prompt-file", RECOMMENDATIONS_PROMPT,
            "--output", recommendations_output_path
        ]
        if not run_command(cmd_recommend, "Gemini Рекомендации"): 
            print("--- Предупреждение: Не удалось выполнить Gemini Рекомендации. ---")
            # Continue pipeline

        # 7. Generate Report (Step 8 - subprocess)
        cmd_report = [
            sys.executable, REPORT_SCRIPT,
            "--input", gpt_analysis_output_path,
            "--output", report_output_base_path, # Base name for .tex/.pdf
            "--image", abs_image_path, # Original image
            "--pdf" # Generate PDF
        ]
        # Conditionally add gemini data and heatmap if they exist and were successful
        if gemini_coords_data and os.path.exists(gemini_coords_parsed_path): # Check if file was actually saved
             cmd_report.extend(["--gemini-data", gemini_coords_parsed_path])
        
        if heatmap_success and os.path.exists(heatmap_output_path):
            cmd_report.extend(["--heatmap", heatmap_output_path])
             
        if not run_command(cmd_report, "Генерация Отчета (LaTeX + PDF)"): 
            print("--- Предупреждение: Не удалось сгенерировать PDF отчет. Проверьте вывод pdflatex. ---")
            # Continue pipeline

    except Exception as e:
        print(f"!!! Неожиданная ошибка в главном пайплайне: {e} !!!")
        traceback.print_exc()
        # Attempt to show whatever results were generated before the crash

    finally:
        # --- Final Output Presentation (Steps 10 & 11) ---
        print("\n" + "="*30 + " ИТОГОВЫЕ РЕЗУЛЬТАТЫ " + "="*30)
        
        pdf_report_path = f"{report_output_base_path}.pdf"
        if os.path.exists(pdf_report_path):
            print(f"\n✅ PDF Отчет: {os.path.abspath(pdf_report_path)}")
        else:
            tex_report_path = f"{report_output_base_path}.tex"
            if os.path.exists(tex_report_path):
                 print(f"\n⚠️ PDF Отчет не сгенерирован. LaTeX файл доступен: {os.path.abspath(tex_report_path)}")
            else:
                 print("\n❌ Отчет (PDF/LaTeX) не был сгенерирован.")
            
        if os.path.exists(heatmap_output_path):
             print(f"\n✅ Тепловая карта: {os.path.abspath(heatmap_output_path)}")
        else:
            print("\n❌ Тепловая карта не была сгенерирована.")

        if os.path.exists(interpretation_output_path):
            try:
                with open(interpretation_output_path, 'r', encoding='utf-8') as f:
                    interpretation_data = json.load(f)
                print("\n--- ✅ Стратегическая Интерпретация ---")
                print(json.dumps(interpretation_data, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"\n⚠️ Ошибка загрузки файла интерпретации ({interpretation_output_path}): {e}")
        else:
            print("\n❌ Файл интерпретации не был сгенерирован.")

        if os.path.exists(recommendations_output_path):
            try:
                with open(recommendations_output_path, 'r', encoding='utf-8') as f:
                    recommendations_data = json.load(f)
                print("\n--- ✅ Стратегические Рекомендации ---")
                print(json.dumps(recommendations_data, indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"\n⚠️ Ошибка загрузки файла рекомендаций ({recommendations_output_path}): {e}")
        else:
            print("\n❌ Файл рекомендаций не был сгенерирован.")

        print("\n" + "="*30 + " ЗАВЕРШЕНИЕ ПАЙПЛАЙНА " + "="*30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Запуск полного пайплайна анализа UI.")
    parser.add_argument("image_path", help="Путь к файлу скриншота для анализа.")
    args = parser.parse_args()
    
    run_pipeline(args.image_path) 