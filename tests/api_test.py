#!/usr/bin/env python3
"""
API Testing Script for Visual Interface Analyzer - Refactored for Import

This script contains functions for core API integrations with GPT-4.1 and Gemini 2.5,
designed to be called by an external orchestration script.
"""

import os
import base64
import json
import sys
from pathlib import Path
from PIL import Image
import matplotlib.pyplot as plt
import numpy as np
import requests # Keep requests if it's used elsewhere, otherwise remove
from dotenv import load_dotenv
import openai
import google.generativeai as genai
import traceback
import io
# import google.api_core.retry as retry # Not used currently
# from google.api_core import timeout # Not used currently
import datetime
import shutil # Needed for heatmap saving

# Load environment variables
load_dotenv()

# Define Model constants
GPT_MODEL = "gpt-4.1"
GEMINI_MODEL = "gemini-2.5-pro-preview-03-25" # Ensure correct model

# API Keys - Initialize clients immediately
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not OPENAI_API_KEY or not GEMINI_API_KEY:
    print("Error: API keys not found in environment variables.")
    print("Please set OPENAI_API_KEY and GEMINI_API_KEY in your .env file.")
    # Raise an error instead of exiting, allows calling script to handle
    raise EnvironmentError("Missing API Keys in .env file")

# Initialize API clients
openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    raise

def encode_image(image_path):
    """Encode an image to base64 for API submission."""
    if not Path(image_path).exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# --- Refactored GPT Analysis Function ---
def run_gpt_analysis(image_path, interface_type, user_scenario, output_json_path):
    """Runs GPT-4.1 UI analysis and saves the result to a JSON file.
    Returns:
        tuple: (bool, dict | None): (success_status, analysis_data) or (False, None) on error.
    """
    print(f"--- Запуск GPT-4.1 Анализа для: {image_path} ---")
    print(f"    Тип интерфейса: {interface_type}")
    print(f"    Сценарий: {user_scenario}")

    # --- Schema Definition (keep as is) ---
    analysis_schema = {
        "type": "object",
        "properties": {
            "metaInfo": {
                "type": "object",
                "properties": {
                    "interfaceType": {"type": "string", "description": "Type of interface (e.g., Search Results Page, Dashboard)"},
                    "userScenarios": {"type": "array", "items": {"type": "string"}, "description": "Typical user scenarios"},
                    "overallComplexityScore": {"type": "number", "format": "float", "description": "Overall complexity score (1-100)", "minimum": 1, "maximum": 100},
                    "analysisTimestamp": {"type": "string", "format": "date-time", "description": "Timestamp of the analysis"}
                },
                "required": ["interfaceType", "userScenarios", "overallComplexityScore", "analysisTimestamp"]
            },
            # ...(rest of schema definition)...
            "complexityScores": {
                "type": "object",
                "description": "Detailed complexity scores by category (1-100 scale)",
                "properties": {
                    "overall": {"type": "number", "format": "float", "description": "Overall score (1-100)", "minimum": 1, "maximum": 100},
                    "structuralVisualOrganization": {
                        "type": "object", "properties": {
                            "score": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                            "components": {"type": "object", "properties": {
                                "gridStructure": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "elementDensity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "whiteSpace": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "colorEntropy": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "visualSymmetry": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "statisticalAnalysis": {"type": "number", "format": "float", "minimum": 1, "maximum": 100}}, "required": ["gridStructure", "elementDensity", "whiteSpace", "colorEntropy", "visualSymmetry", "statisticalAnalysis"]},
                            "reasoning": {"type": "string"},
                            "componentReasonings": {"type": "object", "additionalProperties": {"type": "string"}}}, "required": ["score", "components", "reasoning", "componentReasonings"]},
                    "visualPerceptualComplexity": {
                        "type": "object", "properties": {
                            "score": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                            "components": {"type": "object", "properties": {
                                "edgeDensity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "colorComplexity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "visualSaliency": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "textureComplexity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "perceptualContrast": {"type": "number", "format": "float", "minimum": 1, "maximum": 100}}, "required": ["edgeDensity", "colorComplexity", "visualSaliency", "textureComplexity", "perceptualContrast"]},
                            "reasoning": {"type": "string"},
                            "componentReasonings": {"type": "object", "additionalProperties": {"type": "string"}}}, "required": ["score", "components", "reasoning", "componentReasonings"]},
                    "typographicComplexity": {
                        "type": "object", "properties": {
                            "score": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                            "components": {"type": "object", "properties": {
                                "fontDiversity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "textScaling": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "textDensity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "textAlignment": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "textHierarchy": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "readability": {"type": "number", "format": "float", "minimum": 1, "maximum": 100}}, "required": ["fontDiversity", "textScaling", "textDensity", "textAlignment", "textHierarchy", "readability"]},
                            "reasoning": {"type": "string"},
                            "componentReasonings": {"type": "object", "additionalProperties": {"type": "string"}}}, "required": ["score", "components", "reasoning", "componentReasonings"]},
                    "informationLoad": {
                        "type": "object", "properties": {
                            "score": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                            "components": {"type": "object", "properties": {
                                "informationDensity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "informationStructure": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "informationNoise": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "informationRelevance": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "informationProcessingComplexity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100}}, "required": ["informationDensity", "informationStructure", "informationNoise", "informationRelevance", "informationProcessingComplexity"]},
                            "reasoning": {"type": "string"},
                            "componentReasonings": {"type": "object", "additionalProperties": {"type": "string"}}}, "required": ["score", "components", "reasoning", "componentReasonings"]},
                    "cognitiveLoad": {
                        "type": "object", "properties": {
                            "score": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                            "components": {"type": "object", "properties": {
                                "intrinsicLoad": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "extrinsicLoad": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "germaneCognitiveLoad": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "workingMemoryLoad": {"type": "number", "format": "float", "minimum": 1, "maximum": 100}}, "required": ["intrinsicLoad", "extrinsicLoad", "germaneCognitiveLoad", "workingMemoryLoad"]},
                            "reasoning": {"type": "string"},
                            "componentReasonings": {"type": "object", "additionalProperties": {"type": "string"}}}, "required": ["score", "components", "reasoning", "componentReasonings"]},
                    "operationalComplexity": {
                        "type": "object", "properties": {
                            "score": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                            "components": {"type": "object", "properties": {
                                "decisionComplexity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "physicalComplexity": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "operationalSequence": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "interactionEfficiency": {"type": "number", "format": "float", "minimum": 1, "maximum": 100},
                                "feedbackVisibility": {"type": "number", "format": "float", "minimum": 1, "maximum": 100}}, "required": ["decisionComplexity", "physicalComplexity", "operationalSequence", "interactionEfficiency", "feedbackVisibility"]},
                            "reasoning": {"type": "string"},
                            "componentReasonings": {"type": "object", "additionalProperties": {"type": "string"}}}, "required": ["score", "components", "reasoning", "componentReasonings"]}
                },
                "required": ["overall", "structuralVisualOrganization", "visualPerceptualComplexity", "typographicComplexity", "informationLoad", "cognitiveLoad", "operationalComplexity"]
            },
            "problemAreas": {
                "type": "array",
                "description": "List of identified usability problem areas",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": ["integer", "string"], "description": "Unique identifier for the problem area"},
                        "category": {"type": "string", "description": "Main complexity category"},
                        "subcategory": {"type": "string", "description": "Specific subcategory within the main category"},
                        "description": {"type": "string", "description": "Detailed description of the problem"},
                        "location": {"type": "string", "description": "Location of the problem on the interface"},
                        "severity": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Severity score (1-100)"},
                        "scientificReasoning": {"type": "string", "description": "Scientific explanation based on HCI principles"}
                    },
                    "required": ["id", "category", "subcategory", "description", "location", "severity", "scientificReasoning"]
                }
            }
        },
        "required": ["metaInfo", "complexityScores", "problemAreas"]
    }
    # --- Tool Definition (keep as is) ---
    tools_definition = [
        {
            "type": "function",
            "function": {
                "name": "record_ui_analysis",
                "description": "Records the detailed UI analysis results based on the provided schema.",
                "parameters": analysis_schema
            }
        }
    ]
    tool_choice_definition = {"type": "function", "function": {"name": "record_ui_analysis"}}
    # --- End Schema/Tool Definition ---

    try:
        base64_image = encode_image(image_path)
        
        # Load system prompt from file
        prompt_file_path = os.path.join(os.path.dirname(__file__), "gpt_full_prompt.txt")
        try:
            with open(prompt_file_path, "r", encoding="utf-8") as prompt_file:
                system_prompt = prompt_file.read()
                print(f"    Загружен GPT промпт из: {prompt_file_path}")
        except Exception as e:
            print(f"    !!! Ошибка загрузки GPT промпта ({prompt_file_path}): {e} !!!")
            return False, None # Return error status

        # Construct user message
        user_message_text = f"""
        Analyze the provided user interface screenshot.
        Interface Type Hint: {interface_type}
        User Scenario Hint: {user_scenario}

        Perform a detailed analysis based on the system prompt and return the results using the 'record_ui_analysis' tool.
        """

        # Make API call
        response = openai_client.chat.completions.create(
            model=GPT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": [
                    {"type": "text", "text": user_message_text},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]}
            ],
            tools=tools_definition,
            tool_choice=tool_choice_definition
        )

        # Parse response
        message = response.choices[0].message
        analysis_result = None
        if message.tool_calls and message.tool_calls[0].function.name == "record_ui_analysis":
            try:
                analysis_result = json.loads(message.tool_calls[0].function.arguments)
            except json.JSONDecodeError as e:
                print(f"    !!! Ошибка декодирования JSON из GPT ответа: {e} !!!")
                print(f"    Raw arguments: {message.tool_calls[0].function.arguments}")
                return False, None # Return error status
        else:
            print("    !!! Ошибка: GPT не вернул ожидаемый tool_call 'record_ui_analysis'. !!!")
            return False, None # Return error status

        if analysis_result is None:
             # Error already printed in parsing/checking steps
             return False, None # Return error status

        # Add timestamp if missing
        if "metaInfo" in analysis_result and "analysisTimestamp" not in analysis_result["metaInfo"]:
             analysis_result["metaInfo"]["analysisTimestamp"] = datetime.datetime.now().isoformat()

        # Save result to specified file
        try:
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_result, f, indent=2, ensure_ascii=False)
            print(f"    Результат GPT анализа сохранен в: {output_json_path}")
            return True, analysis_result # Return success and the data
        except Exception as e:
            print(f"    !!! Ошибка сохранения GPT результата в {output_json_path}: {e} !!!")
            return False, None # Return error status

    except FileNotFoundError as e:
        print(f"    !!! Ошибка: Файл не найден (вероятно, изображение): {e} !!!")
        return False, None
    except Exception as e:
        print(f"    !!! Неожиданная ошибка в GPT анализе: {e} !!!")
        traceback.print_exc()
        return False, None

# --- Refactored Gemini Coordinates Function ---
def run_gemini_coordinates(image_path, gpt_result_data, output_raw_json_path, output_parsed_json_path):
    """Runs Gemini coordinate extraction and saves raw/parsed results."""
    print(f"--- Запуск Gemini Координат для: {image_path} ---")

    if not gpt_result_data or "problemAreas" not in gpt_result_data or not gpt_result_data["problemAreas"]:
        print("    !!! Ошибка: Отсутствуют 'problemAreas' в данных GPT анализа. Невозможно запросить координаты. !!!")
        return None

    try:
        # Load image
        image = Image.open(image_path)
        original_width, original_height = image.size
        print(f"    Размер изображения: {original_width}x{original_height}")

        # Convert image to bytes
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        # Format problematic elements for prompt
        elements_text = ""
        MAX_AREAS_FOR_GEMINI = 30
        problem_areas = gpt_result_data["problemAreas"]
        try:
            sorted_areas = sorted(problem_areas, key=lambda x: x.get('severity', 0), reverse=True)
            top_areas = sorted_areas[:MAX_AREAS_FOR_GEMINI]
            print(f"    Обработка топ-{len(top_areas)} проблемных зон для Gemini (из {len(problem_areas)}).")
        except Exception as e:
            print(f"    !!! Ошибка сортировки проблемных зон: {e}. Используются все найденные. !!!")
            top_areas = problem_areas

        for i, area in enumerate(top_areas):
            desc = area.get('description', 'N/A')
            loc = area.get('location', 'N/A')
            sev = area.get('severity', 'N/A')
            area_id = area.get('id', f'unknown_{i}')
            elements_text += f"- ID: {area_id}, Severity: {sev}, Description: {desc}, Location Hint: {loc}\n"

        # --- Simplified Prompt (keep as is) ---
        prompt_simplified = f"""
        You are a specialized visual analysis system designed to extract precise coordinates for identified UI usability issues in images. Your task is to locate specific problematic elements and provide their bounding box coordinates using a normalized coordinate system.


        These are the problematic elements you need to locate:

        <problematic_elements>
        {elements_text}
        </problematic_elements>

        Instructions:

        1. Coordinate System:
           - Use a normalized coordinate system between 0-1000 for both X and Y axes.
           - The origin (0,0) is at the TOP LEFT of the image.
           - For each element, return coordinates as [y_min, x_min, y_max, x_max].
           - y_min = top edge, y_max = bottom edge, x_min = left edge, x_max = right edge.

        2. Element Location Process:
           - Carefully examine the provided image.
           - For each element ID listed in the problematic_elements, find the described element.
           - Create the MOST PRECISE, TIGHTEST possible bounding box around ONLY the specific visual element mentioned in the description. Use the 'Location Hint' to help pinpoint it.
           - **CRITICAL: AVOID creating bounding boxes that span nearly the entire width of the image content area unless the described element itself is explicitly that wide (e.g., a full-width header background). Focus on the specific, local element.**
           - **Example: If a problem description is 'misaligned button within a panel', the bounding box MUST encompass ONLY the button, NOT the entire panel or the row it sits in.**
           - If multiple instances exist, choose the one most relevant to the description.
           - If an element cannot be located, set its coordinates to null.

        3. Coordinate Validation:
           - Ensure that x_min < x_max and y_min < y_max for all bounding boxes.
           - If this condition is not met, do not include the coordinates in the final output JSON's element_coordinates list for that element.

        4. Confidence Assessment:
           - Assign a confidence score (0.0-1.0) to each element based on how certain you are of its location and bounding box accuracy.

        Output Format:
        Provide your response ONLY as valid JSON with the following structure (no other text before or after the JSON block):

        {{
          "element_coordinates": [
            {{
              "id": "problem_area_id from input",
              "element": "brief description of the identified element",
              "coordinates": [y_min, x_min, y_max, x_max], // Normalized 0-1000 or null
              "confidence": 0.0-1.0
            }}
            // ... (repeat for each element where valid coordinates were found)
          ]
        }}

        Remember:
        - Strictly adhere to the JSON format as the ONLY output.
        - Only include valid coordinates (y_min < y_max, x_min < x_max) or null in the 'coordinates' field.
        - Ensure that all coordinate values are between 0 and 1000.

        Begin your coordinate extraction now.
        """
        # --- End Prompt ---

        # Make API Call
        try:
            print("    Отправка запроса в Gemini API (Координаты)...")
            model = genai.GenerativeModel(GEMINI_MODEL) # Use configured client
            response = model.generate_content(
                contents=[
                    prompt_simplified,
                    {"mime_type": "image/png", "data": image_bytes},
                ],
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 8192,
                }
            )
            print("    Ответ от Gemini API получен.")
            # (Handle feedback/safety ratings as before if needed)

        except Exception as e:
            print(f"    !!! Ошибка при вызове Gemini API: {e} !!!")
            traceback.print_exc()
            return None

        # Process response
        if hasattr(response, 'text'):
            response_text = response.text
        elif hasattr(response, 'candidates') and len(response.candidates) > 0 and response.candidates[0].content.parts:
             response_text = response.candidates[0].content.parts[0].text
        else:
            print("    !!! Ошибка: Не получен текст ответа от Gemini API. !!!")
            # print(f"Response: {response}")
            return None

        # Save raw response
        try:
            os.makedirs(os.path.dirname(output_raw_json_path), exist_ok=True)
            with open(output_raw_json_path, "w", encoding="utf-8") as f:
                 f.write(response_text)
            print(f"    Raw Gemini ответ сохранен в: {output_raw_json_path}")
        except Exception as e:
            print(f"    !!! Ошибка сохранения raw Gemini JSON в {output_raw_json_path}: {e} !!!")

        # Parse JSON response
        try:
            # Clean potential markdown fences
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text and response_text.strip().startswith("```"):
                 json_str = response_text.split("```")[1].split("```")[0].strip()
            else:
                 json_str = response_text.strip() # Assume it's just JSON

            coordinates_data = json.loads(json_str)
            assert "element_coordinates" in coordinates_data, "Отсутствует ключ 'element_coordinates' в ответе Gemini"

            # Save parsed response
            os.makedirs(os.path.dirname(output_parsed_json_path), exist_ok=True)
            with open(output_parsed_json_path, "w", encoding="utf-8") as f:
                json.dump(coordinates_data, f, indent=2, ensure_ascii=False)
            print(f"    Распарсенный Gemini ответ сохранен в: {output_parsed_json_path}")

            # Prepare data structure for heatmap function
            valid_elements = [
                {
                    "id": elem["id"],
                    "type": "problem_area", # Consistent type
                    "name": elem["element"],
                    "coordinates": elem["coordinates"] # Keep normalized coords
                } for elem in coordinates_data["element_coordinates"]
                  if elem.get("coordinates") is not None # Filter nulls here
            ]
            element_coordinates_for_heatmap = { "element_coordinates": valid_elements }

            print(f"    Успешно обработан ответ Gemini. Найдено {len(valid_elements)} валидных координат.")
            print(f"--- Успешно: Gemini Координаты ---")
            return element_coordinates_for_heatmap

        except json.JSONDecodeError:
            print("    !!! Ошибка парсинга JSON ответа от Gemini. !!!")
            print("    Raw response text:")
            print(response_text[:1000] + "...") # Print first 1000 chars
            return None
        except AssertionError as e:
             print(f"    !!! Ошибка валидации JSON ответа Gemini: {e} !!!")
             return None
        except Exception as e:
             print(f"    !!! Ошибка сохранения распарсенного Gemini JSON в {output_parsed_json_path}: {e} !!!")
             # Decide if this is fatal, maybe return the data anyway?
             return None # Treat as fatal for now

    except FileNotFoundError as e:
        print(f"    !!! Ошибка: Файл изображения не найден: {e} !!!")
        return None
    except Exception as e:
        print(f"    !!! Неожиданная ошибка в run_gemini_coordinates: {e} !!!")
        traceback.print_exc()
        return None

# --- Refactored Heatmap Generation Function ---
def generate_heatmap(image_path, coordinates_data, gpt_result_data, output_heatmap_path):
    """Generates a heatmap visualization and saves it."""
    print(f"--- Запуск Генерации Тепловой Карты для: {image_path} ---")
    print(f"    Сохранение в: {output_heatmap_path}")

    # Check prerequisites
    if not coordinates_data or "element_coordinates" not in coordinates_data or not coordinates_data["element_coordinates"]:
        print("    Предупреждение: Нет данных координат для генерации тепловой карты.")
        return False # Cannot generate heatmap without coordinates

    if not gpt_result_data or "problemAreas" not in gpt_result_data:
        print("    Предупреждение: Нет данных GPT анализа ('problemAreas') для определения severity. Будет использовано значение по умолчанию (50).")
        problem_areas_map = {} # Empty map, will use default severity
    else:
        problem_areas_map = {str(area["id"]): area.get("severity", 50)
                             for area in gpt_result_data["problemAreas"]}

    try:
        # Load image
        original_img = Image.open(image_path)
        img_array = np.array(original_img)
        height, width = img_array.shape[:2]
        print(f"    Изображение загружено: {width}x{height}")

        # Create heatmap array
        heatmap = np.zeros((height, width), dtype=np.float64) # Use float64 for accumulation

        element_count = len(coordinates_data["element_coordinates"])
        print(f"    Обработка {element_count} элементов для тепловой карты...")

        processed_count = 0
        # Add gaussian for each coordinate set
        for element in coordinates_data["element_coordinates"]:
            coords_norm = element.get("coordinates")
            if coords_norm is None: continue # Should already be filtered, but check

            element_id_str = str(element.get("id")) if element.get("id") is not None else None
            severity = problem_areas_map.get(element_id_str, 50) if element_id_str else 50

            try:
                # Denormalize coordinates (0-1000 -> pixels)
                y_min_norm, x_min_norm, y_max_norm, x_max_norm = coords_norm
                x1 = int(x_min_norm / 1000 * width)
                y1 = int(y_min_norm / 1000 * height)
                x2 = int(x_max_norm / 1000 * width)
                y2 = int(y_max_norm / 1000 * height)

                # Clamp to bounds and validate
                x1 = max(0, min(x1, width - 1))
                y1 = max(0, min(y1, height - 1))
                x2 = max(0, min(x2, width - 1))
                y2 = max(0, min(y2, height - 1))
                if x1 >= x2 or y1 >= y2: continue # Skip invalid box

                # Calculate center and sigma
                center_x = (x1 + x2) // 2
                center_y = (y1 + y2) // 2
                size = max(x2 - x1, y2 - y1, 1) # Avoid size 0
                sigma = max(size / 10, 3) # Minimum sigma 3px
                sigma_sq = sigma ** 2

                # Add gaussian influence weighted by severity squared
                y, x = np.ogrid[:height, :width]
                # Optimized calculation? Maybe not necessary unless very slow.
                gaussian = np.exp(-(((x - center_x)**2 + (y - center_y)**2) / (2 * sigma_sq)))
                heatmap += gaussian * (float(severity) ** 2) # Ensure severity is float
                processed_count += 1

            except (ValueError, TypeError) as e:
                print(f"    Предупреждение: Ошибка обработки координат для элемента {element_id_str}: {coords_norm}. Ошибка: {e}. Пропуск.")
                continue

        print(f"    Добавлено {processed_count} гауссиан в тепловую карту.")

        # Normalize heatmap only if it has values
        if heatmap.max() > 1e-9: # Use a small threshold instead of == 0
            # Clip extreme peaks for better visualization (e.g., 98th percentile)
            upper_bound = np.percentile(heatmap[heatmap > 1e-9], 98)
            clipped_heatmap = np.clip(heatmap, 0, upper_bound)
            # Normalize clipped heatmap
            heatmap_norm = (clipped_heatmap - clipped_heatmap.min()) / (clipped_heatmap.max() - clipped_heatmap.min() + 1e-9) # Add epsilon
        else:
            print("    Тепловая карта пуста, нормализация пропущена.")
            heatmap_norm = heatmap # Keep it as zeros

        # Create visualization
        plt.figure(figsize=(width / 100, height / 100), dpi=150) # Use slightly higher DPI
        plt.imshow(original_img)
        plt.imshow(heatmap_norm, alpha=0.7, cmap='viridis')
        plt.colorbar(label='Относительная критичность проблемы (Intensity)')
        plt.title('Тепловая карта проблемных зон UI')
        plt.axis('off')

        # Save directly to output path
        os.makedirs(os.path.dirname(output_heatmap_path), exist_ok=True)
        plt.savefig(output_heatmap_path, bbox_inches='tight', dpi=150) # Save final version
        plt.close() # Close plot to free memory

        print(f"    Тепловая карта успешно сгенерирована и сохранена в: {output_heatmap_path}")
        print(f"--- Успешно: Генерация Тепловой Карты ---")
        return True

    except FileNotFoundError as e:
        print(f"    !!! Ошибка: Файл изображения не найден: {e} !!!")
        return False
    except ImportError:
        print("    !!! Ошибка: Библиотеки Matplotlib/Numpy/Pillow не найдены. Пожалуйста, установите их. !!!")
        return False
    except Exception as e:
        print(f"    !!! Неожиданная ошибка в generate_heatmap: {e} !!!")
        traceback.print_exc()
        return False

# --- Removed run_full_test() and __main__ block ---
# This script is now intended to be imported as a module.
# The calling script (e.g., run_analysis_pipeline.py) is responsible
# for orchestrating these functions. 