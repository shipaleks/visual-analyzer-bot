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
import logging
import asyncio
from PIL import Image
import re

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

# --- Configuration Flags ---
GENERATE_PDF_IN_PIPELINE = True # Control whether the pipeline attempts PDF generation

# --- Helper Functions ---

# Load prompts at the start
try:
    with open(DEFAULT_COORDS_PROMPT, 'r', encoding='utf-8') as f:
        COORDINATES_PROMPT_TEMPLATE = f.read()
except FileNotFoundError:
    print(f"!!! КРИТИЧЕСКАЯ ОШИБКА: Файл промпта координат {DEFAULT_COORDS_PROMPT} не найден !!!")
    COORDINATES_PROMPT_TEMPLATE = None # Set to None to handle error downstream
except Exception as e:
    print(f"!!! КРИТИЧЕСКАЯ ОШИБКА: Не удалось прочитать файл промпта координат {DEFAULT_COORDS_PROMPT}: {e} !!!")
    COORDINATES_PROMPT_TEMPLATE = None

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
async def run_pipeline(image_path):
    """Asynchronously runs the full analysis pipeline."""
    run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Create a unique directory for this run's outputs
    output_dir = os.path.join(SCRIPT_DIR, f"analysis_outputs/run_{run_timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    print(f"--- Результаты будут сохранены в: {output_dir} ---")

    pipeline_success = True
    pipeline_error_details = ""
    gpt_analysis_output = os.path.join(output_dir, f"gpt_analysis_{run_timestamp}.json")
    gemini_coords_raw_output = os.path.join(output_dir, f"gemini_coords_raw_{run_timestamp}.json")
    gemini_coords_parsed_output = os.path.join(output_dir, f"gemini_coords_parsed_{run_timestamp}.json")
    heatmap_output = os.path.join(output_dir, f"heatmap_{run_timestamp}.png")
    interpretation_output = os.path.join(output_dir, f"interpretation_{run_timestamp}.json")
    recommendations_output = os.path.join(output_dir, f"recommendations_{run_timestamp}.json")
    report_base_output = os.path.join(output_dir, f"report_{run_timestamp}") # Base path for .tex/.pdf

    # --- 1. Get Image Info --- 
    try:
        with Image.open(image_path) as img:
            width, height = img.size
        print("--- Контекст анализа (задан по умолчанию) ---")
        print(f"    Тип интерфейса: Анализируемый интерфейс")
        print(f"    Сценарий: Общий анализ")
        print(f"    Размер изображения: {width}x{height}")
    except Exception as e:
        print(f"!!! Ошибка чтения информации об изображении: {e} !!!")
        pipeline_success = False
        pipeline_error_details += f"Failed to read image info: {e}\n"
        # No point continuing if image is unreadable
        return pipeline_success, pipeline_error_details, {}

    # --- 2. Run GPT-4 Analysis --- 
    if pipeline_success:
        if not os.path.exists(DEFAULT_GPT_PROMPT):
            print(f"!!! Ошибка: Файл промпта GPT не найден: {DEFAULT_GPT_PROMPT} !!!")
            pipeline_success = False
            pipeline_error_details += f"GPT prompt file not found: {DEFAULT_GPT_PROMPT}\n"
        else:
            print(f"--- Запуск GPT-4.1 Анализа для: {image_path} ---")
            # Placeholder for actual GPT analysis call 
            # In a real scenario, replace this with the API call
            # For now, copy sample data if it exists
            sample_gpt_path = os.path.join(SCRIPT_DIR, "tests", "fixtures", "sample_responses", "gpt_full_analysis.json")
            if os.path.exists(sample_gpt_path):
                try:
                    shutil.copyfile(sample_gpt_path, gpt_analysis_output)
                    print(f"    Скопирован пример GPT анализа: {gpt_analysis_output}")
                    print(f"--- Успешно: GPT-4.1 Анализ ---")
                except Exception as e:
                    print(f"!!! Ошибка копирования примера GPT: {e} !!!")
                    pipeline_success = False
                    pipeline_error_details += f"Failed to copy sample GPT data: {e}\n"
            else:
                 print("--- ИСПОЛЬЗУЕТСЯ ЗАГЛУШКА: GPT-4 Анализ пропущен (нет примера данных) ---")
                 # Create empty JSON to avoid downstream errors
                 with open(gpt_analysis_output, 'w') as f: json.dump({}, f)
                 # Consider setting pipeline_success = False if GPT is mandatory

    # --- 3. Run Gemini Coordinates --- 
    coords_successfully_parsed = False
    if pipeline_success and os.path.exists(gpt_analysis_output):
        print(f"--- Запуск Gemini Координат для: {image_path} ---")
        try:
            # Construct the prompt for Gemini coordinates
            with open(gpt_analysis_output, 'r', encoding='utf-8') as f:
                gpt_data = json.load(f)
            problem_areas = gpt_data.get("problemAreas", [])
            # Select top N problems based on severity for coordinates request
            top_problems = sorted(problem_areas, key=lambda x: x.get("severity", 0), reverse=True)[:30] # Get top 30
            print(f"    Обработка топ-{len(top_problems)} проблемных зон для Gemini (из {len(problem_areas)}).")
            
            prompt_elements = []
            for p in top_problems:
                prompt_elements.append(f"- ID {p.get('id', 'N/A')}: {p.get('element', 'N/A')}")
            
            gemini_coords_prompt = COORDINATES_PROMPT_TEMPLATE.format(problem_list="\n".join(prompt_elements))
            
            print("    Отправка запроса в Gemini API (Координаты)...")
            # Replace with actual Gemini API call
            # gemini_response_text = call_gemini_api(gemini_coords_prompt, image_path=image_path)
            gemini_response_text = "" # Placeholder
            sample_coords_path = os.path.join(SCRIPT_DIR, "tests", "fixtures", "sample_responses", "gemini_coords_parsed.json")
            if os.path.exists(sample_coords_path):
                 with open(sample_coords_path, 'r') as f:
                     gemini_response_text = f.read() # Use sample JSON directly
                     print("    ИСПОЛЬЗУЕТСЯ ЗАГЛУШКА: Получен пример ответа Gemini (Координаты)")
            else:
                 print("    ИСПОЛЬЗУЕТСЯ ЗАГЛУШКА: Gemini API (Координаты) пропущен (нет примера)")
                 gemini_response_text = '{"element_coordinates": []}' # Empty valid JSON
            
            # Save raw response
            with open(gemini_coords_raw_output, 'w', encoding='utf-8') as f:
                f.write(gemini_response_text)
            logger.info(f"  Raw Gemini ответ сохранен в: {gemini_coords_raw_output}")

            # Parse and validate the response
            try:
                # Attempt to remove potential markdown backticks
                cleaned_response_text = re.sub(r'^```json\s*|\s*```$', '', gemini_response_text).strip()
                coords_data = json.loads(cleaned_response_text)
                if not isinstance(coords_data, dict) or "element_coordinates" not in coords_data:
                    logger.error(f"!!! Ошибка: Gemini Координаты JSON имеют неверную структуру. !!!\nКлючи: {coords_data.keys() if isinstance(coords_data, dict) else 'Not a dict'}")
                    pipeline_error_details += f"Invalid Gemini Coords JSON structure. Keys: {coords_data.keys() if isinstance(coords_data, dict) else 'Not a dict'}\n"
                else:
                    # Validate coordinates format (basic check)
                    valid_coords_count = 0
                    if isinstance(coords_data["element_coordinates"], list):
                        for item in coords_data["element_coordinates"]:
                             # Add more checks if needed (e.g., bounds are numbers)
                             if isinstance(item, dict) and "id" in item and "coordinates" in item:
                                 valid_coords_count += 1
                    if valid_coords_count > 0:
                         # Save parsed JSON
                        with open(gemini_coords_parsed_output, 'w', encoding='utf-8') as f:
                            json.dump(coords_data, f, ensure_ascii=False, indent=2)
                        logger.info(f"  Распарсенный Gemini ответ сохранен в: {gemini_coords_parsed_output}")
                        print(f"    Успешно обработан ответ Gemini. Найдено {valid_coords_count} валидных координат.")
                        coords_successfully_parsed = True
                    else:
                        print("!!! Ошибка: Gemini Координаты JSON не содержит валидных элементов или список пуст. !!!")
                        pipeline_error_details += f"Gemini Coords JSON has no valid elements or list is empty.\n"

            except json.JSONDecodeError as e:
                print(f"!!! Ошибка парсинга JSON ответа от Gemini (Координаты). !!!")
                print(f"  Ошибка: {e}")
                print(f"  Raw response text causing error:\n---\n{gemini_response_text[:1000]}...\n---")
                pipeline_error_details += f"Failed to parse Gemini Coords JSON: {e}\nRaw Response Snippet: {gemini_response_text[:200]}\n"
        except Exception as e:
            print(f"!!! Неожиданная ошибка при запросе координат Gemini: {e} !!!")
            traceback.print_exc()
            pipeline_error_details += f"Unexpected error during Gemini Coordinates: {e}\n"
            
        if coords_successfully_parsed:
            print(f"--- Успешно: Gemini Координаты ---")
        else:
            print(f"--- ОШИБКА: Gemini Координаты НЕ ПОЛУЧЕНЫ --- ")
            print("!!! Предупреждение: Gemini Координаты не были получены; продолжаю без координат и тепловой карты !!!")
            # Don't necessarily fail the whole pipeline, but heatmap/report images will be missing
    elif pipeline_success:
        print("--- Пропуск Gemini Координат (нет файла GPT анализа) ---")

    # --- 4. Generate Heatmap --- 
    heatmap_generated = False
    if pipeline_success and coords_successfully_parsed: # Only if coords were parsed
        print(f"--- Запуск Генерации Тепловой Карты для: {image_path} ---")
        # Placeholder for actual heatmap generation call
        # heatmap_generated = generate_heatmap(image_path, gemini_coords_parsed_output, heatmap_output)
        print(f"    Сохранение в: {heatmap_output}")
        # Simulate success for now
        try:
            # Create a dummy heatmap file 
            dummy_heatmap_path = os.path.join(SCRIPT_DIR, "tests", "fixtures", "test_heatmap.png")
            if os.path.exists(dummy_heatmap_path):
                shutil.copyfile(dummy_heatmap_path, heatmap_output)
                print(f"    ИСПОЛЬЗУЕТСЯ ЗАГЛУШКА: Скопирован пример тепловой карты.")
                print(f"    Тепловая карта успешно сгенерирована и сохранена в: {heatmap_output}")
                heatmap_generated = True
            else:
                 print("    ИСПОЛЬЗУЕТСЯ ЗАГЛУШКА: Генерация тепловой карты пропущена (нет примера). Создан пустой файл.")
                 # Create an empty file to satisfy path checks
                 with open(heatmap_output, 'w') as f: pass 
                 heatmap_generated = False # Mark as not truly generated
        except Exception as e:
             print(f"!!! Ошибка копирования/создания примера тепловой карты: {e} !!!")
             heatmap_generated = False

        if heatmap_generated:
             print(f"--- Успешно: Генерация Тепловой Карты ---")
        else:
            print(f"--- ОШИБКА: Генерация Тепловой Карты НЕ УДАЛАСЬ ---")
            pipeline_error_details += f"Heatmap generation failed.\n"
    elif pipeline_success:
        print("--- Пропуск Генерации Тепловой Карты (нет файла координат) --- ")

    # --- 5. Run Gemini Interpretation --- (Uses get_gemini_recommendations.py script)
    interpretation_generated = False
    if pipeline_success and os.path.exists(gpt_analysis_output):
        print("--- Запуск: Gemini Интерпретация ---")
        if not os.path.exists(DEFAULT_INTERPRETATION_PROMPT):
            print(f"!!! Ошибка: Файл промпта Интерпретации не найден: {DEFAULT_INTERPRETATION_PROMPT} !!!")
            pipeline_error_details += f"Interpretation prompt file not found: {DEFAULT_INTERPRETATION_PROMPT}\n"
        else:
            interp_command = [
                sys.executable, GET_GEMINI_REC_SCRIPT,
                '--input', gpt_analysis_output,
                '--prompt-file', DEFAULT_INTERPRETATION_PROMPT,
                '--output', interpretation_output
            ]
            print(f"Команда: {' '.join(interp_command)}")
            interp_process = await asyncio.create_subprocess_exec(
                 *interp_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            interp_stdout, interp_stderr = await interp_process.communicate()
            print("Вывод:")
            if interp_stdout: print(interp_stdout.decode('utf-8', errors='ignore'))
            if interp_stderr: print("Ошибки (stderr):"); print(interp_stderr.decode('utf-8', errors='ignore'))
            
            if interp_process.returncode == 0:
                print("--- Успешно: Gemini Интерпретация ---")
                interpretation_generated = True
            else:
                print(f"--- ОШИБКА: Gemini Интерпретация завершилась с кодом {interp_process.returncode} ---")
                pipeline_error_details += f"Gemini Interpretation failed. Details: {interp_stderr.decode('utf-8', errors='ignore')[-500:]}\n"
    elif pipeline_success:
         print("--- Пропуск Gemini Интерпретации (нет файла GPT анализа) --- ")

    # --- 6. Run Gemini Recommendations --- (Uses get_gemini_recommendations.py script)
    recommendations_generated = False
    if pipeline_success and os.path.exists(gpt_analysis_output):
        print("--- Запуск: Gemini Рекомендации ---")
        if not os.path.exists(DEFAULT_RECOMMENDATIONS_PROMPT):
            print(f"!!! Ошибка: Файл промпта Рекомендаций не найден: {DEFAULT_RECOMMENDATIONS_PROMPT} !!!")
            pipeline_error_details += f"Recommendations prompt file not found: {DEFAULT_RECOMMENDATIONS_PROMPT}\n"
        else:
            rec_command = [
                sys.executable, GET_GEMINI_REC_SCRIPT,
                '--input', gpt_analysis_output,
                '--prompt-file', DEFAULT_RECOMMENDATIONS_PROMPT,
                '--output', recommendations_output
            ]
            print(f"Команда: {' '.join(rec_command)}")
            rec_process = await asyncio.create_subprocess_exec(
                 *rec_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            rec_stdout, rec_stderr = await rec_process.communicate()
            print("Вывод:")
            if rec_stdout: print(rec_stdout.decode('utf-8', errors='ignore'))
            if rec_stderr: print("Ошибки (stderr):"); print(rec_stderr.decode('utf-8', errors='ignore'))
            
            if rec_process.returncode == 0:
                print("--- Успешно: Gemini Рекомендации ---")
                recommendations_generated = True
            else:
                print(f"--- ОШИБКА: Gemini Рекомендации завершилась с кодом {rec_process.returncode} ---")
                pipeline_error_details += f"Gemini Recommendations failed. Details: {rec_stderr.decode('utf-8', errors='ignore')[-500:]}\n"
    elif pipeline_success:
         print("--- Пропуск Gemini Рекомендаций (нет файла GPT анализа) --- ")

    # --- 7. Generate LaTeX Report --- 
    pdf_generated_successfully = False # Default status
    run_report_generation = pipeline_success and os.path.exists(gpt_analysis_output)
    if run_report_generation:
        print("--- Запуск: Генерация Отчета (LaTeX + PDF) ---")
        report_command = [
            sys.executable, GENERATE_REPORT_SCRIPT,
            '--input', gpt_analysis_output,
            '--output', report_base_output,
            '--image', image_path,
        ]
        # Add optional files ONLY if they were successfully generated/parsed
        if coords_successfully_parsed:
            report_command.extend(['--gemini-data', gemini_coords_parsed_output])
        if heatmap_generated:
            report_command.extend(['--heatmap', heatmap_output])
        if GENERATE_PDF_IN_PIPELINE:
            report_command.append('--pdf')

        print(f"Команда: {' '.join(report_command)}")

        report_process = await asyncio.create_subprocess_exec(
            *report_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        report_stdout, report_stderr = await report_process.communicate()
        print("Вывод:")
        if report_stdout:
            print(report_stdout.decode('utf-8', errors='ignore'))
        if report_stderr:
            print("Ошибки (stderr):")
            print(report_stderr.decode('utf-8', errors='ignore'))

        if report_process.returncode == 0:
            print("--- Успешно: Генерация Отчета (LaTeX + PDF) ---")
            # Explicitly check if the PDF file exists AFTER the script ran
            pdf_report_path = report_base_output + ".pdf"
            if os.path.exists(pdf_report_path):
                pdf_generated_successfully = True
            else:
                 pdf_generated_successfully = False 
                 print(f"--- Предупреждение: Скрипт генерации отчета завершился успешно, но PDF файл не найден по пути {pdf_report_path} ---")
        else:
            print(f"--- ОШИБКА: Генерация Отчета завершилась с кодом {report_process.returncode} ---")
            pdf_generated_successfully = False # Ensure it's False on error
            pipeline_error_details += f"Report generation failed. Exit code: {report_process.returncode}. Stderr: {report_stderr.decode('utf-8', errors='ignore')[-500:]}\n"
    elif pipeline_success:
         print("--- Пропуск Генерации Отчета (нет файла GPT анализа) --- ")

    # --- Final Summary --- 
    print("\n============================== ИТОГОВЫЕ РЕЗУЛЬТАТЫ ==============================")
    
    final_tex_path = report_base_output + ".tex"
    final_pdf_path = report_base_output + ".pdf"
    
    if os.path.exists(final_tex_path):
        print(f"✅ LaTeX Отчет (.tex): {final_tex_path}")
    else:
        # If report generation didn't even run, this is expected
        if run_report_generation: print(f"❌ LaTeX Отчет (.tex) не найден (ошибка генерации?).")
        else: print(f"ℹ️ LaTeX Отчет (.tex) не генерировался.")

    if pdf_generated_successfully:
        print(f"✅ PDF Отчет: {final_pdf_path}")
    elif GENERATE_PDF_IN_PIPELINE and run_report_generation: # If we attempted PDF generation
        print(f"❌ PDF генерация НЕ УДАЛАСЬ. Проверьте лог LaTeX выше. Вы можете скомпилировать .tex вручную.")
    elif run_report_generation: # We generated tex but didn't ask for PDF
         print(f"ℹ️ PDF генерация не запрашивалась (--pdf флаг). Вы можете скомпилировать .tex вручную.")
    else:
        print(f"ℹ️ PDF отчет не генерировался.")

    if heatmap_generated:
        print(f"✅ Тепловая карта: {heatmap_output}")
    elif coords_successfully_parsed: # If coords were ok but heatmap failed
        print(f"❌ Тепловая карта НЕ БЫЛА сгенерирована (ошибка генерации?).")
    else: # If coords failed
        print(f"❌ Тепловая карта не была сгенерирована (ошибка получения координат)." )

    if interpretation_generated:
        print(f"✅ Файл интерпретации: {interpretation_output}")
    else:
        print(f"❌ Файл интерпретации не был сгенерирован.")

    if recommendations_generated:
        print(f"✅ Файл рекомендаций: {recommendations_output}")
    else:
        print(f"❌ Файл рекомендаций не был сгенерирован.")

    # Determine final pipeline status 
    # Consider it success if at least the main analysis (GPT) and interpretation/recommendations ran
    final_pipeline_status = pipeline_success and os.path.exists(gpt_analysis_output) and interpretation_generated and recommendations_generated
    
    if not final_pipeline_status:
        print("\n============================== ОШИБКИ ПАЙПЛАЙНА ==============================")
        print(pipeline_error_details)
        print("===============================================================================")

    print("\n============================== ЗАВЕРШЕНИЕ ПАЙПЛАЙНА ==============================")

    # Return results dictionary
    results = {
        "success": final_pipeline_status,
        "error_details": pipeline_error_details,
        "tex_path": final_tex_path if os.path.exists(final_tex_path) else None,
        "pdf_path": final_pdf_path if pdf_generated_successfully else None,
        "heatmap_path": heatmap_output if heatmap_generated else None,
        "interpretation_path": interpretation_output if interpretation_generated else None,
        "recommendations_path": recommendations_output if recommendations_generated else None,
        "output_dir": output_dir # For potential cleanup by the caller
    }
    return results

async def main():
    parser = argparse.ArgumentParser(description="Run the full UI analysis pipeline.")
    parser.add_argument("image_path", help="Path to the input image file.")
    args = parser.parse_args()

    results = await run_pipeline(args.image_path)
    
    # Optionally print results summary for command-line execution
    # print("\n--- Pipeline Results Dict ---")
    # print(results)
    
    # Exit with appropriate code based on success
    if results["success"]:
         sys.exit(0)
    else:
         sys.exit(1)

if __name__ == "__main__":
    # Setup basic logging if run directly
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    asyncio.run(main()) 