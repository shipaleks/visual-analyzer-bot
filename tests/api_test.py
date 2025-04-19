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

        # Parse JSON response - IMPROVED PARSING LOGIC
        try:
            # Get raw text without any markdown or formatting
            raw_text = response_text.strip()
            
            # Look for JSON content with multiple extraction methods
            json_str = None
            
            # Method 1: Extract from markdown code blocks
            if "```json" in raw_text:
                json_str = raw_text.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_text:
                # Try to find any code block
                parts = raw_text.split("```")
                if len(parts) >= 3:  # At least one complete code block
                    json_str = parts[1].strip()
            
            # Method 2: Find JSON by brackets if method 1 failed
            if not json_str:
                # Try to extract JSON using bracket matching
                start_idx = raw_text.find('{')
                if start_idx != -1:
                    # Find matching end bracket
                    bracket_count = 0
                    for i in range(start_idx, len(raw_text)):
                        if raw_text[i] == '{':
                            bracket_count += 1
                        elif raw_text[i] == '}':
                            bracket_count -= 1
                            if bracket_count == 0:
                                # Found matching bracket
                                json_str = raw_text[start_idx:i+1]
                                break
            
            # If still no JSON found, use the whole text as a last resort
            if not json_str:
                print("    !!! Предупреждение: не удалось выделить JSON из ответа. Используем весь текст !!!")
                json_str = raw_text
            
            # Check if the extracted text looks like JSON before trying to parse
            if not (json_str.startswith('{') and json_str.endswith('}')):
                print(f"    !!! Предупреждение: извлеченный текст не похож на JSON: {json_str[:100]}... !!!")
            
            # Try to parse with improved error handling
            try:
                coordinates_data = json.loads(json_str)
            except json.JSONDecodeError as e:
                print(f"    !!! Ошибка парсинга JSON: {e} !!!")
                print(f"    Проблемная строка: {e.doc[max(0, e.pos-30):min(len(e.doc), e.pos+30)]}")
                
                # Last resort: try to clean the string and parse again
                clean_json_str = json_str.replace('\n', ' ').replace('\r', '')
                # Remove any non-JSON characters at the beginning or end
                while clean_json_str and not clean_json_str.startswith('{'):
                    clean_json_str = clean_json_str[1:]
                while clean_json_str and not clean_json_str.endswith('}'):
                    clean_json_str = clean_json_str[:-1]
                    
                if clean_json_str and clean_json_str.startswith('{') and clean_json_str.endswith('}'):
                    print("    Attempting to parse cleaned JSON string...")
                    coordinates_data = json.loads(clean_json_str)
                else:
                    print("    !!! Не удалось очистить JSON строку !!!")
                    raise
            
            # Validate required keys
            if "element_coordinates" not in coordinates_data:
                print("    !!! Предупреждение: ответ не содержит ключ 'element_coordinates' !!!")
                # Try to fix the structure if possible
                if isinstance(coordinates_data, list):
                    # Wrap list in the expected structure
                    coordinates_data = {"element_coordinates": coordinates_data}
                    print("    Исправлена структура JSON: обернут список в 'element_coordinates'")
                else:
                    # Look for any key that might contain a list of elements
                    for key, value in coordinates_data.items():
                        if isinstance(value, list) and value and isinstance(value[0], dict):
                            coordinates_data = {"element_coordinates": value}
                            print(f"    Исправлена структура JSON: использован ключ '{key}' как 'element_coordinates'")
                            break
                    else:
                        # If we still have no element_coordinates, create an empty list
                        coordinates_data = {"element_coordinates": []}
                        print("    !!! Не удалось найти координаты в ответе, создан пустой список !!!")

            # Save parsed response
            os.makedirs(os.path.dirname(output_parsed_json_path), exist_ok=True)
            with open(output_parsed_json_path, "w", encoding="utf-8") as f:
                json.dump(coordinates_data, f, indent=2, ensure_ascii=False)
            print(f"    Распарсенный Gemini ответ сохранен в: {output_parsed_json_path}")

            # Prepare data structure for heatmap function
            valid_elements = [
                {
                    "id": elem.get("id", f"unknown_{i}"),
                    "type": "problem_area", # Consistent type
                    "name": elem.get("element", "Unknown element"),
                    "coordinates": elem.get("coordinates") # Keep normalized coords
                } for i, elem in enumerate(coordinates_data["element_coordinates"])
                  if elem.get("coordinates") is not None # Filter nulls here
            ]
            element_coordinates_for_heatmap = { "element_coordinates": valid_elements }

            print(f"    Успешно обработан ответ Gemini. Найдено {len(valid_elements)} валидных координат.")
            print(f"--- Успешно: Gemini Координаты ---")
            return element_coordinates_for_heatmap
        
        except Exception as e:
            print(f"    !!! Ошибка при обработке ответа Gemini: {e} !!!")
            traceback.print_exc()
            # Create a fallback empty coordinates structure
            fallback_coords = {"element_coordinates": []}
            try:
                with open(output_parsed_json_path, "w", encoding="utf-8") as f:
                    json.dump(fallback_coords, f, indent=2)
                print(f"    Создан пустой файл координат из-за ошибки: {output_parsed_json_path}")
            except Exception as save_e:
                print(f"    !!! Не удалось сохранить пустой файл координат: {save_e} !!!")
            
            return fallback_coords

    except FileNotFoundError as e:
        print(f"    !!! Ошибка: Файл изображения не найден: {e} !!!")
        return None
    except Exception as e:
        print(f"    !!! Неожиданная ошибка в run_gemini_coordinates: {e} !!!")
        traceback.print_exc()
        return None

# --- Refactored Heatmap Generation Function ---
def generate_heatmap(image_path, coordinates_data, gpt_result_data, output_heatmap_path):
    """
    Generate a heatmap visualization of UI issues.
    This function is enhanced to work with empty coordinates data.
    """
    import matplotlib.pyplot as plt
    import numpy as np
    from PIL import Image
    import os
    
    try:
        print(f"    Изображение загружено: {image_path}")
        
        # Make sure output directory exists
        output_dir = os.path.dirname(output_heatmap_path)
        os.makedirs(output_dir, exist_ok=True)
        
        # Load the original image and get dimensions
        try:
            img = Image.open(image_path)
            width, height = img.size
            print(f"    Изображение загружено: {width}x{height}")
        except Exception as e:
            print(f"    !!! Ошибка при загрузке изображения: {e} !!!")
            # Create a blank image as fallback
            width, height = 800, 600
            img = Image.new('RGB', (width, height), color='white')
            print(f"    Создано пустое изображение: {width}x{height}")
        
        # Get coordinates from the Gemini data
        elements = coordinates_data.get("element_coordinates", [])
        valid_count = len([e for e in elements if e.get("coordinates")])
        
        if valid_count == 0:
            # No valid coordinates. Create a simple heatmap with a warning message
            print(f"    !!! Предупреждение: нет валидных координат для тепловой карты. Создание пустой карты !!!")
            
            # Create a simple heatmap with text
            plt.figure(figsize=(width/100, height/100), dpi=100)
            plt.imshow(np.array(img))
            
            # Add text warning
            plt.text(width/2, height/2, "Нет данных для тепловой карты", 
                     color="red", fontsize=24, ha="center", va="center",
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.7))
            
            plt.axis('off')
            plt.savefig(output_heatmap_path, bbox_inches='tight', pad_inches=0)
            plt.close()
            
            print(f"    Создана пустая тепловая карта: {output_heatmap_path}")
            return True
        
        # Process the elements with valid coordinates
        print(f"    Обработка {valid_count} элементов для тепловой карты...")
        
        # Create a heatmap array
        heatmap = np.zeros((height, width))
        
        added_gaussians = 0
        for element in elements:
            coords = element.get("coordinates")
            if not coords or len(coords) != 4:
                continue
                
            # Extract coordinates - handle both formats
            if isinstance(coords, list) and len(coords) == 4:
                y_min, x_min, y_max, x_max = coords
                
                # Check if normalized (0-1000)
                if all(0 <= c <= 1000 for c in coords):
                    # Convert normalized coordinates to actual pixels
                    y_min = int(y_min * height / 1000)
                    x_min = int(x_min * width / 1000)
                    y_max = int(y_max * height / 1000)
                    x_max = int(x_max * width / 1000)
            else:
                # Skip invalid coordinates
                continue
            
            # Additional validation
            if y_min >= y_max or x_min >= x_max:
                continue
                
            # Ensure coordinates are within image bounds
            y_min = max(0, min(y_min, height-1))
            x_min = max(0, min(x_min, width-1))
            y_max = max(0, min(y_max, height-1))
            x_max = max(0, min(x_max, width-1))
            
            # Find center point
            center_y = (y_min + y_max) // 2
            center_x = (x_min + x_max) // 2
            
            # Calculate sigma based on the size of the area
            area_width = x_max - x_min
            area_height = y_max - y_min
            sigma = max(area_width, area_height) / 4
            
            # Get problem severity to scale the intensity
            severity = 0.7  # Default if not found
            problem_id = element.get("id")
            if problem_id and gpt_result_data and "problemAreas" in gpt_result_data:
                for problem in gpt_result_data["problemAreas"]:
                    if str(problem.get("id")) == str(problem_id):
                        # Convert severity to 0-1 scale
                        severity = min(1.0, max(0.1, problem.get("severity", 70) / 100.0))
                        break
            
            # Create a gaussian centered on this element
            y, x = np.ogrid[:height, :width]
            gaussian = np.exp(-(
                ((x - center_x) ** 2) / (2 * sigma ** 2) + 
                ((y - center_y) ** 2) / (2 * sigma ** 2)
            )) * severity  # Scale by severity
            
            # Add to the heatmap
            heatmap += gaussian
            added_gaussians += 1
        
        print(f"    Добавлено {added_gaussians} гауссиан в тепловую карту.")
        
        # If no gaussians were added (e.g., all had invalid coordinates), create a simple overlay
        if added_gaussians == 0:
            plt.figure(figsize=(width/100, height/100), dpi=100)
            plt.imshow(np.array(img))
            plt.text(width/2, height/2, "Некорректные координаты элементов", 
                     color="red", fontsize=24, ha="center", va="center",
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.7))
            plt.axis('off')
            plt.savefig(output_heatmap_path, bbox_inches='tight', pad_inches=0)
            plt.close()
            print(f"    Создана тепловая карта с предупреждением: {output_heatmap_path}")
            return True
        
        # Normalize the heatmap
        heatmap = (heatmap - heatmap.min()) / (heatmap.max() - heatmap.min() + 1e-8)
        
        # Create the visualization
        plt.figure(figsize=(width/100, height/100), dpi=100)
        
        # Display the original image
        plt.imshow(np.array(img))
        
        # Overlay the heatmap with a colormap
        plt.imshow(heatmap, alpha=0.6, cmap='hot')
        
        # Remove axes
        plt.axis('off')
        
        # Save the result
        plt.savefig(output_heatmap_path, bbox_inches='tight', pad_inches=0)
        plt.close()
        
        print(f"    Тепловая карта успешно сгенерирована и сохранена в: {output_heatmap_path}")
        return True
        
    except Exception as e:
        print(f"    !!! Ошибка при генерации тепловой карты: {e} !!!")
        traceback.print_exc()
        
        try:
            # Fallback: Create a simple image with error message
            img = Image.new('RGB', (800, 600), color='white')
            plt.figure(figsize=(8, 6), dpi=100)
            plt.imshow(np.array(img))
            plt.text(400, 300, f"Ошибка при создании тепловой карты:\n{str(e)}", 
                     color="red", fontsize=18, ha="center", va="center",
                     bbox=dict(boxstyle="round,pad=0.5", facecolor="white", alpha=0.7))
            plt.axis('off')
            plt.savefig(output_heatmap_path, bbox_inches='tight', pad_inches=0)
            plt.close()
            print(f"    Создана карта с сообщением об ошибке: {output_heatmap_path}")
            return True
        except Exception as fallback_e:
            print(f"    !!! Критическая ошибка при создании карты ошибки: {fallback_e} !!!")
            return False

# --- Removed run_full_test() and __main__ block ---
# This script is now intended to be imported as a module.
# The calling script (e.g., run_analysis_pipeline.py) is responsible
# for orchestrating these functions. 