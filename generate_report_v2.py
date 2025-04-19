#!/usr/bin/env python3
"""
Report Generator for Visual Interface Analyzer

This script generates a comprehensive LaTeX report based on GPT-4 analysis
of user interface issues.
"""

import os
import json
import argparse
from datetime import datetime
import re
import math
import subprocess
import shutil  # Для проверки наличия приложений
from PIL import Image
import base64
import io
import tempfile
from urllib.parse import urlparse
import sys

def load_analysis_data(json_file_path):
    """Load analysis data from a JSON file."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Error loading analysis data: {e}")
        return None

def sanitize_latex(text):
    """Sanitize text for LaTeX."""
    if not text:
        return ""
    
    # Replace special LaTeX characters
    replacements = {
        '&': r'\\&',
        '%': r'\\%',
        '$': r'\\$',
        '#': r'\\#',
        '_': r'\\_',
        '{': r'\\{',
        '}': r'\\}',
        '~': r'\\textasciitilde{}',
        '^': r'\\textasciicircum{}',
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text

def generate_introduction(data):
    """Generate introduction section."""
    interface_type = data.get("metaInfo", {}).get("interfaceType", "Неизвестный тип интерфейса")
    
    introduction = f"""
\\section{{Введение}}

\\subsection{{О проекте}}
Данный отчет содержит результаты комплексного анализа пользовательского интерфейса 
типа "{sanitize_latex(interface_type)}". Анализ выполнен с использованием 
передовых методов оценки юзабилити, основанных на исследованиях в области 
человеко-компьютерного взаимодействия, когнитивной психологии и информационного дизайна.

\\subsection{{Методология}}
Для оценки сложности интерфейса применялся структурированный подход, 
включающий анализ по шести основным категориям:

\\begin{{itemize}}
\\item Структурная визуальная организация
\\item Визуальная перцептивная сложность
\\item Типографическая сложность
\\item Информационная нагрузка
\\item Когнитивная нагрузка
\\item Операционная сложность
\\end{{itemize}}

Каждая категория оценивалась по шкале от 1 до 100, где 1 означает минимальную сложность, 
а 100 — максимальную. Выявленные проблемные области также получили оценку критичности от 1 до 100.
"""
    return introduction

def process_heatmap_for_report(heatmap_path, output_path=None):
    """Обрабатывает тепловую карту для включения в отчет.
    
    Функция обрезает длинное изображение тепловой карты, оставляя только наиболее значимые области
    с высокой плотностью проблем.
    """
    try:
        from PIL import Image
        import tempfile
        import os
        
        if not os.path.exists(heatmap_path):
            print(f"Ошибка: Файл тепловой карты {heatmap_path} не найден")
            return None
            
        img = Image.open(heatmap_path)
        width, height = img.size
        print(f"Обработка тепловой карты размером {width}x{height}")
        
        # Определяем область для обрезки (первые 6000 пикселей высоты)
        # Это должно содержать наиболее важные области тепловой карты
        crop_height = min(6000, height)
        cropped_img = img.crop((0, 0, width, crop_height))
        
        # Масштабируем изображение для лучшего отображения в отчете
        max_width = 1800
        if width > max_width:
            ratio = max_width / width
            new_height = int(crop_height * ratio)
            cropped_img = cropped_img.resize((max_width, new_height), Image.LANCZOS)
            print(f"Масштабировано до {max_width}x{new_height}")
        
        # Сохраняем обработанное изображение
        if output_path is None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png", prefix="report_heatmap_")
            output_path = temp_file.name
            temp_file.close()
        
        cropped_img.save(output_path, format="PNG")
        print(f"Обработанная тепловая карта сохранена как {output_path}")
        return output_path
        
    except Exception as e:
        print(f"Ошибка при обработке тепловой карты: {e}")
        return None

def generate_heatmap_section(data, heatmap_path):
    """Генерирует раздел с тепловой картой для отчета."""
    if not heatmap_path or not os.path.exists(heatmap_path):
        return ""
    
    # Обрабатываем тепловую карту
    report_dir = os.path.dirname(latex_path) if 'latex_path' in globals() and latex_path else '.'
    images_subdir = os.path.join(report_dir, "report_images")
    if not os.path.exists(images_subdir):
        try:
            os.makedirs(images_subdir)
        except OSError:
            pass
    
    processed_heatmap = process_heatmap_for_report(
        heatmap_path, 
        os.path.join(images_subdir, "report_heatmap.png")
    )
    
    if not processed_heatmap:
        return ""
    
    # Создаем путь, безопасный для LaTeX
    latex_safe_path = processed_heatmap.replace("\\", "/")
    if os.path.isabs(latex_safe_path):
        # Создаем относительный путь
        latex_safe_path = os.path.relpath(latex_safe_path, report_dir).replace("\\", "/")
    
    section = f"""
\\section{{Визуализация проблемных областей}}

\\begin{{figure}}[H]
\\centering
\\includegraphics[width=0.95\\textwidth, keepaspectratio]{{{latex_safe_path}}}
\\caption{{Тепловая карта проблемных областей интерфейса}}
\\label{{fig:heatmap}}
\\end{{figure}}

\\begin{{tcolorbox}}[colback=blue!5, colframe=blue!40, title=Интерпретация тепловой карты, fonttitle=\\bfseries]
Тепловая карта визуализирует наиболее проблемные зоны интерфейса, где яркость и насыщенность цвета 
соответствуют уровню критичности проблем. Красным цветом отмечены области с наибольшей концентрацией
критичных проблем (80+ баллов), требующие первоочередного внимания при оптимизации интерфейса. 
\\end{{tcolorbox}}

На тепловой карте отчетливо видны следующие проблемные зоны:
\\begin{{itemize}}
\\item \\textbf{{Рекламные блоки}} в верхней части страницы, которые создают избыточную плотность элементов 
и конкурируют за внимание с органическими результатами. 
\\item \\textbf{{Блок видео}} с высокой плотностью краев, множеством цветов и перегруженным контентом.
\\item \\textbf{{Зона органических результатов}} с высокой информационной плотностью.
\\end{{itemize}}

Эта визуализация дополняет количественную оценку и помогает определить приоритетные зоны для 
оптимизации интерфейса.
"""
    return section

def generate_overall_score_section(data):
    """Generate overall score section using 1-100 scale."""
    overall_score = data.get("complexityScores", {}).get("overall", 0)
    
    # Convert to float for calculations
    try:
        overall_score_float = float(overall_score)
    except ValueError:
        overall_score_float = 0

    # Categorization based on 1-100 scale
    score_interpretation = ""
    if overall_score_float <= 30:
        score_interpretation = "Интерфейс имеет низкий уровень сложности и, вероятно, обеспечивает хороший пользовательский опыт."
        chart_color = "green!70"
    elif overall_score_float <= 50:
        score_interpretation = "Интерфейс имеет умеренную сложность с некоторыми областями для улучшения."
        chart_color = "yellow!70" # Changed color for 31-50 range
    elif overall_score_float <= 70:
        score_interpretation = "Интерфейс имеет повышенную сложность, что может значительно влиять на пользовательский опыт."
        chart_color = "orange!80" # Adjusted threshold
    else:
        score_interpretation = "Интерфейс чрезмерно сложен и нуждается в серьезной переработке."
        chart_color = "red!70"
    
    # Darken color for better visibility
    chart_fill_color = chart_color.replace("!70", "!60!black").replace("!80", "!70!black")
        
    # Calculate end angle for the circular diagram (0-100 scale)
    end_angle_calc = 90 - overall_score_float * 3.6 # Adjusted multiplier for 100 scale
    
    section = f"""    
\\section{{Общая оценка сложности}}

\\begin{{figure}}[H] % Keep forced placement
\\centering
\\begin{{tikzpicture}}
% Fixed diagram size
\\def\\radius{{3.5cm}} 

% Outer circle (gray)
\\draw[line width=3mm, black!20] (0,0) circle (\\radius);

% Fill based on score (draw arc)
\\draw[line width=3mm, {chart_fill_color}] (90:\\radius) arc (90:{end_angle_calc}:\\radius);

% Score text in the center, larger
\\node[] at (0,0) {{\\fontsize{{36}}{{40}}\selectfont {overall_score:.0f}}}; 
\\node[] at (0,-1.0) {{\\large из 100}}; % Updated scale text

\\end{{tikzpicture}}
\\caption{{Общая оценка сложности интерфейса (1-100)}} % Updated caption
\\end{{figure}}

\\begin{{tcolorbox}}[colback={chart_color}!5, colframe={chart_color}, title=Интерпретация, fonttitle=\\bfseries] % Lighten background
{score_interpretation}
\\end{{tcolorbox}}

Данная оценка представляет совокупность всех аспектов сложности интерфейса, 
включая структурную организацию, визуальную сложность, информационную и когнитивную нагрузку, 
а также операционную сложность взаимодействия.
"""
    return section

def generate_key_findings(data):
    """Generate key findings section using 1-100 scale for severity."""
    problem_areas = data.get("problemAreas", [])
    
    # Sort by severity (1-100)
    high_severity_issues = sorted(
        [issue for issue in problem_areas if issue.get("severity", 0) >= 80], # Adjusted threshold
        key=lambda x: x.get("severity", 0),
        reverse=True
    )
    
    # Take top 5 issues
    top_issues = high_severity_issues[:5]
    
    findings_text = ""
    if not top_issues:
         findings_text = "Критических проблем (80 баллов и выше) не выявлено."
    else:
        for i, issue in enumerate(top_issues):
            category = issue.get("category", "Unknown category")
            subcategory = issue.get("subcategory", "Unknown subcategory")
            description = issue.get("description", "No description")
            severity = issue.get("severity", 0)
            reasoning = issue.get("scientificReasoning", "No reasoning provided")
            
            # Adjust color based on severity (1-100 scale)
            box_color = "red!70!black" 
            back_color = "red!5"
            if severity < 90: # Adjusted threshold
                box_color = "orange!80!black"
                back_color = "orange!5"
            
            findings_text += f"""
\\begin{{tcolorbox}}[colback={back_color}, colframe={box_color}, title=Проблема {i+1}: {sanitize_latex(category)} — {sanitize_latex(subcategory)}, fonttitle=\\bfseries]
\\begin{{itemize}}
\\item \\textbf{{Описание:}} {sanitize_latex(description)}
\\item \\textbf{{Критичность:}} {severity}/100 
\\item \\textbf{{Научное обоснование:}} {sanitize_latex(reasoning)}
\\end{{itemize}}
\\end{{tcolorbox}}\n"""
    
    section = f"""
\\section{{Ключевые выводы}}

\\begin{{tcolorbox}}[colback=white, colframe=black!50, title=Наиболее критичные проблемы (80+ баллов), fonttitle=\\bfseries] % Neutral block, updated title
В ходе анализа выявлены следующие критические проблемы, требующие первоочередного внимания (при наличии):
\\end{{tcolorbox}}

{findings_text}

Эти проблемы требуют первоочередного внимания при оптимизации интерфейса.
"""
    return section

def generate_category_scores(data):
    """Generate category scores section using 1-100 scale."""
    complexity_scores = data.get("complexityScores", {})
    categories = [
        ("structuralVisualOrganization", "Структурная виз. организация"), 
        ("visualPerceptualComplexity", "Визуальная перцеп. сложность"), 
        ("typographicComplexity", "Типографическая сложность"),
        ("informationLoad", "Информационная нагрузка"),
        ("cognitiveLoad", "Когнитивная нагрузка"),
        ("operationalComplexity", "Операционная сложность")
    ]
    
    radar_data = ""
    radar_labels = ""
    score_points = ""
    score_labels = ""
    category_lines = ""
    num_categories = len(categories)
    angle_step = 360 / num_categories

    for i, (key, label) in enumerate(categories):
        score = complexity_scores.get(key, {}).get("score", 0)
        score = min(max(score, 0), 100) # Ensure score is within 0-100
        angle = 90 - i * angle_step
        
        max_radius = 5
        # Calculate coordinates for the score point (scaled to 0-100)
        xscore = score / 100 * max_radius * math.cos(math.radians(angle)) # Divide by 100
        yscore = score / 100 * max_radius * math.sin(math.radians(angle)) # Divide by 100
        
        radar_data += f"({xscore:.2f},{yscore:.2f}) "
        score_points += f"\\fill[red] ({xscore:.2f},{yscore:.2f}) circle (0.15);\\n"
        category_lines += f"\\draw[blue!40, dashed] (0,0) -- ({xscore:.2f},{yscore:.2f});\\n"
        
        label_offset = 0.4
        xoffset = label_offset * math.cos(math.radians(angle))
        yoffset = label_offset * math.sin(math.radians(angle))
        score_labels += f"\\node[font=\\small, fill=white, inner sep=1pt, text=red] at ({xscore+xoffset:.2f},{yscore+yoffset:.2f}) {{{score:.0f}}};\\n" # Display score as integer
        
        label_radius = max_radius + 0.8
        x_label = label_radius * math.cos(math.radians(angle))
        y_label = label_radius * math.sin(math.radians(angle))
        if abs(x_label) < 0.1: anchor = "middle"
        elif x_label > 0: anchor = "west"
        else: anchor = "east"
        radar_labels += f"\\node[anchor={anchor}, align=center, font=\\small, text width=2.5cm] at ({x_label:.2f},{y_label:.2f}) {{{sanitize_latex(label)}}};\\n"
    
    first_point = radar_data.split(' ')[0]
    radar_data += first_point

    # Generate table rows with color coding (1-100 scale)
    table_rows = ""
    for key, label in categories:
        score = complexity_scores.get(key, {}).get("score", 0)
        score = min(max(score, 0), 100) 
        
        cell_color = "white"
        if score >= 80: cell_color = "red!30"      # Adjusted thresholds and colors
        elif score >= 60: cell_color = "orange!30"
        elif score >= 40: cell_color = "yellow!30"
        else: cell_color = "green!15"
            
        table_rows += f"{sanitize_latex(label)} & \\cellcolor{{{cell_color}}}{score:.0f} \\\\" # Removed trailing \n
    
    section = f"""
\\section{{Оценки по категориям}}

\\begin{{figure}}[H]
\\centering
\\begin{{tikzpicture}}[scale=0.9]
\\def\\MaxRadius{{5}}

% Draw scale circles (0-100 scale)
\\foreach \\r in {{1, 2, 3, 4, 5}} {{
    \\pgfmathsetmacro{{\\circleRadius}}{{\\r}}
    \\draw[lightgray, dashed] (0,0) circle (\\circleRadius);
    \\pgfmathsetmacro{{\\scaleValue}}{{\\r*20}} % Scale labels 20, 40, ..., 100
    \\node[font=\\tiny, text=gray] at (45:\\circleRadius) {{\\scaleValue}};
}}

% Draw axes
\\foreach \\i in {{0,...,{num_categories-1}}} {{
    \\pgfmathsetmacro{{\\currentangle}}{{90-\\i*{angle_step}}}
    \\draw[lightgray] (0,0) -- ({{\\currentangle}}:\\MaxRadius);
    % Add scale markers on axes
    \\foreach \\r in {{1, ..., 5}} {{
        \\pgfmathsetmacro{{\\markerX}}{{\\r * cos(\\currentangle)}}
        \\pgfmathsetmacro{{\\markerY}}{{\\r * sin(\\currentangle)}}
        \\fill[black, opacity=0.5] (\\markerX,\\markerY) circle (0.05);
    }}
}}

{category_lines}
\\draw[blue!60, thick, fill=blue!20, opacity=0.7] {radar_data} -- cycle;
{score_points}
{score_labels}
{radar_labels}

\\node[font=\\footnotesize, align=center] at (0,-6) {{Шкала: 1-100 (от центра к краям)}}; % Updated scale text
\\node[draw, font=\\footnotesize, align=left, fill=white, rounded corners] at (4.5, -5) {{
  \\textcolor{{red}}{{\\textbullet}} - Значение категории (от 1 до 100) % Updated scale text
}};

\\end{{tikzpicture}}
\\caption{{Распределение оценок сложности по категориям (1-100)}} % Updated caption
\\end{{figure}}

\\begin{{table}}[H]
\\centering
\\begin{{tabular}}{{|l|c|}}
\\hline
\\rowcolor{{gray!15}}
\\textbf{{Категория}} & \\textbf{{Оценка (1-100)}} \\\\\\\\ % Updated scale text
\\hline
{table_rows}
\\hline
\\end{{tabular}}
\\caption{{Количественные оценки по категориям}}
\\end{{table}}

\\begin{{tcolorbox}}[colback=blue!5, colframe=blue!40, title=Интерпретация, fonttitle=\\bfseries]
Эти оценки отражают уровень сложности интерфейса в каждой из категорий по 100-балльной шкале. 
Более высокие значения указывают на большую сложность.
\\end{{tcolorbox}}
"""
    return section

def generate_component_table(data):
    """Generate table with all components using 1-100 scale."""
    complexity_scores = data.get("complexityScores", {})
    categories_data_list = [
        ("structuralVisualOrganization", "Структурная визуальная организация", [
            "gridStructure", "elementDensity", "whiteSpace", "colorEntropy", "visualSymmetry", "statisticalAnalysis"
        ]),
        ("visualPerceptualComplexity", "Визуальная перцептивная сложность", [
            "edgeDensity", "colorComplexity", "visualSaliency", "textureComplexity", "perceptualContrast"
        ]),
        ("typographicComplexity", "Типографическая сложность", [
            "fontDiversity", "textScaling", "textDensity", "textAlignment", "textHierarchy", "readability"
        ]),
        ("informationLoad", "Информационная нагрузка", [
            "informationDensity", "informationStructure", "informationNoise", "informationRelevance", "informationProcessingComplexity"
        ]),
        ("cognitiveLoad", "Когнитивная нагрузка", [
            "intrinsicLoad", "extrinsicLoad", "germaneCognitiveLoad", "workingMemoryLoad"
        ]),
        ("operationalComplexity", "Операционная сложность", [
            "decisionComplexity", "physicalComplexity", "operationalSequence", "interactionEfficiency", "feedbackVisibility"
        ])
    ]
    
    left_categories = categories_data_list[:3] 
    right_categories = categories_data_list[3:] 
    
    def generate_category_content(categories):
        content = ""
        for category_key, category_name, components in categories:
            category_data = complexity_scores.get(category_key, {})
            category_score = category_data.get("score", 0)
            components_data = category_data.get("components", {})
            
            content += f"\\rowcolor{{gray!10}}\\multicolumn{{2}}{{|l|}}{{\\textbf{{{sanitize_latex(category_name)}}}}} \\\\ \\hline\n"
            content += f"\\textbf{{Общая оценка}} & {category_score:.0f} \\\\ \\hline\n" # Display as integer

            for component in components:
                if component in components_data:
                    component_score = components_data.get(component, 0)
                    component_name = ' '.join(word.capitalize() for word in re.findall(r'[A-Z]?[a-z]+|[A-Z]+', component))
                    content += f"{sanitize_latex(component_name)} & {component_score:.0f} \\\\ \\hline\n" # Display as integer
        return content
                
    left_content = generate_category_content(left_categories)
    right_content = generate_category_content(right_categories)
    
    section = f"""
\\section{{Детальная оценка компонентов}}

\\begin{{table}}[H]
\\centering
\\small
\\setlength{{\\tabcolsep}}{{5pt}}
\\renewcommand{{\\arraystretch}}{{1.2}}
\\begin{{tabular}}{{|p{{0.42\\textwidth}}|c|}}
\\hline
\\rowcolor{{gray!15}}
\\textbf{{Компонент}} & \\textbf{{Оценка (1-100)}} \\\\ \\hline
{left_content}
\\end{{tabular}}
\\hfill
\\begin{{tabular}}{{|p{{0.42\\textwidth}}|c|}}
\\hline
\\rowcolor{{gray!15}}
\\textbf{{Компонент}} & \\textbf{{Оценка (1-100)}} \\\\ \\hline
{right_content}
\\end{{tabular}}
\\caption{{Детальные оценки всех компонентов интерфейса (1-100)}} % Updated caption
\\end{{table}}

Таблица представляет подробную разбивку оценок (1-100) по всем компонентам.
"""
    return section

def generate_detailed_category_sections(data):
    """Generate detailed sections for each category using 1-100 scale."""
    complexity_scores = data.get("complexityScores", {})
    problem_areas = data.get("problemAreas", [])
    coordinates = data.get("coordinates", {}).get("element_coordinates", [])
    image_path = data.get("metaInfo", {}).get("imagePath", "")
    
    print("--- Debug: Entering generate_detailed_category_sections ---")
    print(f"  Image path from data: {image_path}")
    print(f"  Number of coordinates loaded: {len(coordinates)}")
    
    coordinate_map = {}
    if coordinates and image_path:
        if not os.path.exists(image_path):
            print(f"  ERROR: Image path {image_path} does not exist! Cannot create coordinate map.")
        else:
            print(f"  Image exists at {image_path}. Creating coordinate map...")
            for coord in coordinates:
                element_id = coord.get("id") 
                if element_id:
                    coordinate_map[str(element_id)] = coord # Ensure key is string
            print(f"  Coordinate map created with {len(coordinate_map)} entries.")
    else:
        print("  Coordinates or image path missing, coordinate map not created.")

    def get_problem_image(problem, original_image_path):
        print(f"\nAttempting to find image for problem ID: {problem.get('id', 'N/A')} (Subcategory: {problem.get('subcategory', 'N/A')})")
        if not coordinate_map:
            print("  Coordinate map is empty.")
            return None
        if not os.path.exists(original_image_path):
            print(f"  Original image path does not exist: {original_image_path}")
            return None
            
        problem_id = str(problem.get("id")) 
        if not problem_id:
             print("  Problem has no ID. Cannot find coordinates.")
             return None
             
        matched_coord_data = coordinate_map.get(problem_id)
        
        if not matched_coord_data:
             print(f"  No coordinates found in map for problem ID '{problem_id}'.")
             return None
             
        print(f"  Found coordinate data for ID '{problem_id}': {matched_coord_data}")
        bounds = matched_coord_data.get("coordinates")
        
        if bounds is None:
            print(f"  Coordinates for ID '{problem_id}' are null. Skipping image.")
            return None
            
        if bounds: 
            try:
                original_img = Image.open(original_image_path)
                
                if not (isinstance(bounds, list) and len(bounds) == 4 and all(isinstance(b, (int, float)) for b in bounds)):
                     print(f"    Invalid bounding box format: {bounds}. Skipping image.")
                     return None
                
                if all(0 <= b <= 1 for b in bounds):
                    print(f"    Warning: bounds seem to be in 0-1 range: {bounds}. Converting to 0-1000.")
                    bounds = [b * 1000 for b in bounds]
                
                if all(0 <= b <= 1000 for b in bounds):
                    width, height = original_img.size
                    # Правильный порядок координат: координаты в формате [y_min, x_min, y_max, x_max]
                    # Но для обработки изображения нам нужен формат [x_min, y_min, x_max, y_max]
                    y_min, x_min, y_max, x_max = bounds
                    # Преобразуем нормализованные координаты в пиксельные
                    pixel_bounds = [
                        int(y_min * height / 1000), 
                        int(x_min * width / 1000),
                        int(y_max * height / 1000), 
                        int(x_max * width / 1000)
                    ]
                    print(f"    Converted normalized bounds {bounds} to pixel bounds {pixel_bounds}")
                else:
                    print(f"    Using bounds as pixel coordinates: {bounds}")
                    pixel_bounds = [int(b) for b in bounds]
                
                padding = 30 
                y_min_p, x_min_p, y_max_p, x_max_p = pixel_bounds
                
                # Проверка на корректность координат
                if x_min_p >= x_max_p or y_min_p >= y_max_p:
                    print(f"    Degenerate pixel bounds: {pixel_bounds}. Skipping image.")
                    return None
                
                # Проверим, может быть координаты перепутаны местами
                if x_max_p - x_min_p < 10 or y_max_p - y_min_p < 10:
                    print(f"    Very small bounding box. Swapping coordinates to try to fix.")
                    # Попробуем поменять xy местами
                    x_min_p, y_min_p, x_max_p, y_max_p = y_min_p, x_min_p, y_max_p, x_max_p
                    pixel_bounds = [y_min_p, x_min_p, y_max_p, x_max_p]
                    
                # Обрезаем изображение с отступами
                y_min_crop = max(0, y_min_p - padding)
                x_min_crop = max(0, x_min_p - padding)
                y_max_crop = min(height, y_max_p + padding)
                x_max_crop = min(width, x_max_p + padding)
                
                print(f"    Cropping area (with padding): ({x_min_crop}, {y_min_crop}, {x_max_crop}, {y_max_crop})")
                cropped_img = original_img.crop((x_min_crop, y_min_crop, x_max_crop, y_max_crop))
                
                from PIL import ImageDraw
                draw = ImageDraw.Draw(cropped_img)
                rect_x_min = x_min_p - x_min_crop
                rect_y_min = y_min_p - y_min_crop
                rect_x_max = x_max_p - x_min_crop
                rect_y_max = y_max_p - y_min_crop
                draw.rectangle([rect_x_min, rect_y_min, rect_x_max, rect_y_max], outline="red", width=3)
                
                report_dir = os.path.dirname(latex_path) if 'latex_path' in globals() and latex_path else '.'
                images_subdir = os.path.join(report_dir, "report_images")
                if not os.path.exists(images_subdir):
                    try:
                        os.makedirs(images_subdir)
                        print(f"    Created image subdirectory: {images_subdir}")
                    except OSError as e:
                        print(f"    ERROR: Could not create image subdirectory {images_subdir}: {e}. Saving to report dir.")
                        images_subdir = report_dir 
                
                if not os.path.isdir(images_subdir):
                     print(f"    ERROR: Target image directory is not valid: {images_subdir}. Cannot save image.")
                     return None
                     
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir=images_subdir, prefix="problem_img_")
                temp_path = temp_file.name
                cropped_img.save(temp_path, format="PNG")
                temp_file.close() 
                
                report_dir = os.path.dirname(latex_path) if 'latex_path' in globals() and latex_path else '.'
                relative_image_dir_path = os.path.relpath(images_subdir, report_dir)
                relative_image_path = os.path.join(relative_image_dir_path, os.path.basename(temp_path))
                return relative_image_path.replace("\\", "/")
            except Exception as e:
                print(f"    Error processing image for problem: {e}")
        else:
            print("  No suitable coordinate match found for this problem.")
        
        return None
    
    category_mapping = {
        "структурная визуальная организация": ["структур", "организац"],
        "визуальная перцептивная сложность": ["визуал", "перцептив"],
        "типографическая сложность": ["типограф", "шрифт"],
        "информационная нагрузка": ["информаци", "информационная"],
        "когнитивная нагрузка": ["когнитив", "ментал"],
        "операционная сложность": ["операцион", "взаимодейств"]
    }
    
    def determine_category(problem):
        category_text = problem.get("category", "").lower()
        category_name_en = problem.get("category", "")
        if category_name_en == "Structural Visual Organization": return "структурная визуальная организация"
        if category_name_en == "Visual Perceptual Complexity": return "визуальная перцептивная сложность"
        if category_name_en == "Typographic Complexity": return "типографическая сложность"
        if category_name_en == "Information Load": return "информационная нагрузка"
        if category_name_en == "Cognitive Load": return "когнитивная нагрузка"
        if category_name_en == "Operational Complexity": return "операционная сложность"
        
        for full_name, substrings in category_mapping.items():
            if any(substr in category_text for substr in substrings):
                print(f"  [Category Match Debug] Matched '{category_text}' to '{full_name}' by substring")
                return full_name
                
        print(f"  [Category Match Debug] Could not match category: '{category_text}'") 
        return "другое"  
    
    categories = [
        ("structuralVisualOrganization", "Структурная визуальная организация"),
        ("visualPerceptualComplexity", "Визуальная перцептивная сложность"),
        ("typographicComplexity", "Типографическая сложность"),
        ("informationLoad", "Информационная нагрузка"),
        ("cognitiveLoad", "Когнитивная нагрузка"),
        ("operationalComplexity", "Операционная сложность")
    ]
    
    all_sections = ""
    
    for category_key, category_name in categories:
        print(f"--- Debug: Processing category: {category_name} ({category_key}) ---")
        category_data = complexity_scores.get(category_key, {})
        category_score = category_data.get("score", 0)
        category_reasoning = category_data.get("reasoning", "")
        components_data = category_data.get("components", {})
        component_reasonings = category_data.get("componentReasonings", {})
        
        category_problems = [
            problem for problem in problem_areas 
            if determine_category(problem) == category_name.lower()
        ]
        category_problems.sort(key=lambda x: x.get("severity", 0), reverse=True)
        print(f"  Found {len(category_problems)} problems for this category.")
        
        components_text = ""
        for component, score in components_data.items():
            component_name = ' '.join(word.capitalize() for word in re.findall(r'[A-Z]?[a-z]+|[A-Z]+', component))
            
            # Поиск релевантной информации о компоненте в проблемных областях
            component_problems = [p for p in category_problems if p.get("subcategory", "").lower() == component_name.lower()]
            
            if component_problems:
                # Если есть связанные проблемы, используем их описание
                description = component_problems[0].get("description", "")
                reasoning = component_problems[0].get("scientificReasoning", "")
                component_reasoning = f"{description} {reasoning}"
            else:
                # Если для компонента нет конкретной проблемы, используем общее описание категории
                component_reasoning = f"Является частью общей оценки категории. {category_reasoning}"
            
            if not component_reasoning:
                component_reasoning = f"Компонент '{component_name}' имеет оценку сложности {score:.0f} из 100."
            
            components_text += f"""
\\subsubsection{{{sanitize_latex(component_name)} ({score:.0f}/100)}} 
{sanitize_latex(component_reasoning)}
"""
        
        problems_text = ""
        for i, problem in enumerate(category_problems):
            print(f"  Processing problem {i+1}/{len(category_problems)}: {problem.get('subcategory', 'N/A')}")
            subcategory = problem.get("subcategory", "")
            description = problem.get("description", "")
            severity = problem.get("severity", 0)
            location = problem.get("location", "")
            reasoning = problem.get("scientificReasoning", "")
            
            print(f"    Calling get_problem_image for problem subcategory: {subcategory}")
            image_path_for_problem = get_problem_image(problem, image_path)
            image_latex = ""
            if image_path_for_problem:
                latex_safe_path = image_path_for_problem.replace("\\", "/")
                image_latex = f"""
\\begin{{figure}}[H] 
\\centering
\\includegraphics[width=0.8\\textwidth, keepaspectratio]{{{latex_safe_path}}}
\\caption{{Визуализация проблемы: {sanitize_latex(subcategory)}}}
\\label{{fig:problem_{problem.get('id', i)}}} 
\\end{{figure}}
"""
            
            # Color based on severity (1-100 scale)
            box_color = "red!70!black"
            back_color = "red!5"
            if severity < 90: 
                box_color = "orange!80!black"
                back_color = "orange!5"
            if severity < 70:
                box_color = "yellow!80!black" # Adjusted thresholds
                back_color = "yellow!5"
            if severity < 40:
                box_color = "green!70!black"
                back_color = "green!5"
            
            problems_text += f"""
\\begin{{tcolorbox}}[colback={back_color}, colframe={box_color}, title=Проблема {i+1}: {sanitize_latex(subcategory)} (Критичность: {severity}/100), fonttitle=\\bfseries] 
\\begin{{itemize}}
\\item \\textbf{{Описание:}} {sanitize_latex(description)}
\\item \\textbf{{Местоположение:}} {sanitize_latex(location)}
\\item \\textbf{{Научное обоснование:}} {sanitize_latex(reasoning)}
\\end{{itemize}}
{image_latex}
\\end{{tcolorbox}}
"""
        
        section = f"""
\\section{{{sanitize_latex(category_name)}}}

\\subsection{{Общая оценка: {category_score:.0f}/100}} 
{sanitize_latex(category_reasoning)}

\\subsection{{Компоненты}}
{components_text}

\\subsection{{Выявленные проблемы ({len(category_problems)})}}
{problems_text or "В этой категории не выявлено проблем."}
"""
        all_sections += section
    
    return all_sections

def generate_conclusions(data):
    """Generate conclusions section using 1-100 scale."""
    overall_score = data.get("complexityScores", {}).get("overall", 0)
    try:
        overall_score_float = float(overall_score)
    except ValueError:
        overall_score_float = 0
        
    problem_areas = data.get("problemAreas", [])
    # Adjust severity thresholds for 1-100 scale
    high_severity_count = len([p for p in problem_areas if p.get("severity", 0) >= 80])
    medium_severity_count = len([p for p in problem_areas if 50 <= p.get("severity", 0) < 80])
    low_severity_count = len([p for p in problem_areas if p.get("severity", 0) < 50])
    
    section = f"""
\\section{{Заключение}}

\\subsection{{Итоговая оценка}}
Проведенный анализ показал, что интерфейс имеет общую оценку сложности {overall_score:.0f}/100. 
Всего выявлено {len(problem_areas)} проблемных областей, из которых:
\\begin{{itemize}}
\\item Критических проблем (80-100 баллов): {high_severity_count}
\\item Проблем средней критичности (50-79 баллов): {medium_severity_count}
\\item Проблем низкой критичности (1-49 баллов): {low_severity_count}
\\end{{itemize}}
"""
    return section

def generate_latex_document(data):
    """Generate the complete LaTeX document."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    global latex_path 
    latex_path = "" 
    
    latex_document = f"""
\\documentclass[10pt, a4paper]{{article}}
\\usepackage[T2A]{{fontenc}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{cmap}}
\\usepackage{{geometry}}
\\usepackage{{graphicx}}
\\usepackage{{xcolor}}
\\usepackage{{hyperref}}
\\usepackage{{array}}
\\usepackage{{longtable}}
\\usepackage{{booktabs}}
\\usepackage{{colortbl}}
\\usepackage{{fancyhdr}}
\\usepackage{{lastpage}}
\\usepackage{{multirow}}
\\usepackage[english, russian]{{babel}}
\\usepackage{tikz} % For drawing diagrams
\\usepackage{float} % For [H] placement
\\usepackage{tcolorbox} % For colored blocks

\\geometry{{ a4paper, top=2.5cm, bottom=2.5cm, left=2.5cm, right=2.5cm }}
\\hypersetup{{ colorlinks=true, linkcolor=blue, filecolor=magenta, urlcolor=cyan, 
    pdftitle={{Отчет об анализе пользовательского интерфейса}}, pdfauthor={{Visual Interface Analyzer}} }}

\\pagestyle{{fancy}}
\\fancyhf{{}}
\\rhead{{Отчет об анализе UI}}
\\lhead{{Visual Interface Analyzer}}
\\cfoot{{Страница \\thepage}}

\\begin{{document}}

\\begin{{titlepage}}
\\centering
{{\\LARGE \\textbf{{Отчет об анализе пользовательского интерфейса}}\\par}}
\\vspace{{1.5cm}}
{{\\Large Комплексная оценка юзабилити и визуальной сложности\\par}}
\\vspace{{1.5cm}}
\\begin{{tikzpicture}}
\\draw[rounded corners=20pt, fill=black!5, draw=black!40, line width=1pt] (0,0) rectangle (10,4);
\\node at (5,2) {{\\Large \\textbf{{Visual Interface Analyzer}}\\\\ \\vspace{{0.5cm}} \\normalsize Аналитический отчет}};
\\end{{tikzpicture}}
\\vfill
{{\\large Дата анализа: {timestamp}\\par}}

\\vspace{{0.7cm}}
\\begin{{center}}
\\begin{{minipage}}{{0.8\\textwidth}}
\\centering
\\textit{{Отчет сгенерирован службой UX Яндекса}}\\\\
\\href{{https://wiki.yandex-team.ru/ux/}}{{wiki.yandex-team.ru/ux}}\\\\
\\vspace{{0.3cm}}
\\textit{{По всем вопросам обращаться:}}\\\\
Лёша Шипулин — \\href{{https://staff.yandex-team.ru/shipaleks}}{{staff.yandex-team.ru/shipaleks}}
\\end{{minipage}}
\\end{{center}}

\\vspace{{0.5cm}}
\\end{{titlepage}}

\\tableofcontents
\\newpage

{generate_introduction(data)}
{generate_overall_score_section(data)}
{generate_heatmap_section(data, data.get("metaInfo", {}).get("heatmapPath"))}
{generate_key_findings(data)}
{generate_category_scores(data)}
{generate_component_table(data)}
{generate_detailed_category_sections(data)}
{generate_conclusions(data)}

\\end{{document}}
"""
    return latex_document

def save_latex_to_file(content, output_path):
    """Save the generated LaTeX content to a file."""
    global latex_path
    latex_path = os.path.abspath(output_path)
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"LaTeX report saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving LaTeX file: {e}")
        return False

def generate_pdf(latex_path):
    """Generate PDF from LaTeX using Python."""
    pdf_path = latex_path.replace(".tex", ".pdf")
    log_path = latex_path.replace(".tex", ".log") # Define log file path
    aux_path = latex_path.replace(".tex", ".aux") # Define aux file path
    toc_path = latex_path.replace(".tex", ".toc") # Define toc file path
    out_path = latex_path.replace(".tex", ".out") # Define out file path
    report_dir = os.path.dirname(latex_path)
    images_subdir = os.path.join(report_dir, "report_images")
    
    if not os.path.exists(images_subdir):
        try:
            os.makedirs(images_subdir)
            print(f"Created directory for images: {images_subdir}")
        except OSError as e:
            print(f"Error creating directory {images_subdir}: {e}")
            pass 
    
    pdflatex_path = shutil.which("pdflatex")
    if not pdflatex_path:
        if os.path.exists("/Library/TeX/texbin/pdflatex"):
            pdflatex_path = "/Library/TeX/texbin/pdflatex"
            print(f"Using pdflatex from /Library/TeX/texbin/")
    
    pdf_generated_successfully = False
    if pdflatex_path:
        try:
            final_return_code = 0
            for i in range(2):
                print(f"Running pdflatex attempt {i+1}...")
                # Ensure output directory exists for pdflatex
                os.makedirs(report_dir, exist_ok=True)
                result = subprocess.run(
                    [pdflatex_path,
                     "-interaction=nonstopmode",
                     "-output-directory", report_dir, # Ensure output goes here
                      latex_path],
                    capture_output=True, text=False, check=False # text=False to handle potential encoding issues in log
                )
                final_return_code = result.returncode # Store the code from the last run
                if result.returncode != 0:
                    print(f"Warning: pdflatex (attempt {i+1}) returned non-zero exit code: {result.returncode}")
                    # Don't break, try second run for references
                else:
                    print(f"pdflatex attempt {i+1} successful.")
            
            # Check final status after potentially two runs
            if os.path.exists(pdf_path) and final_return_code == 0:
                print(f"PDF successfully generated at {pdf_path}")
                pdf_generated_successfully = True
            else:
                print(f"PDF generation failed or pdflatex reported errors (last exit code: {final_return_code}).")
                # --- Read and print last part of log file on error --- START ---
                if os.path.exists(log_path):
                    print(f"--- Last lines of {os.path.basename(log_path)}: ---")
                    try:
                        with open(log_path, 'r', encoding='utf-8', errors='ignore') as log_file:
                            lines = log_file.readlines()
                            # Print last ~20 lines to stderr
                            for line in lines[-20:]:
                                sys.stderr.write(line)
                        sys.stderr.flush()
                    except Exception as log_e:
                        print(f"Error reading log file {log_path}: {log_e}", file=sys.stderr)
                else:
                     print(f"Log file {log_path} not found.", file=sys.stderr)
                # --- Read and print last part of log file on error --- END ---

        except Exception as e:
            print(f"Error running pdflatex: {e}")
    else:
        print("pdflatex not found in system PATH or in /Library/TeX/texbin/.")
    
    # --- Cleanup Logic --- START ---
    # Clean up aux/log/toc/out files regardless of success
    for ext_path in [log_path, aux_path, toc_path, out_path]:
        if os.path.exists(ext_path):
            try:
                os.remove(ext_path)
                # print(f"Removed temporary file: {os.path.basename(ext_path)}")
            except OSError as e:
                print(f"Warning: Could not remove temporary file {ext_path}: {e}")
                
    # Clean up image directory if it was created and is empty
    # Keep images if PDF generation failed for debugging
    if pdf_generated_successfully:
        print(f"Cleaning up temporary images from {images_subdir}...")
        if os.path.exists(images_subdir) and os.path.isdir(images_subdir):
            try:
                shutil.rmtree(images_subdir) # Remove directory and its contents
                print(f"Removed temporary image directory: {images_subdir}")
            except OSError as e:
                 print(f"Warning: Could not remove image directory {images_subdir}: {e}")
    else:
         print(f"Skipping image cleanup as PDF generation failed ({images_subdir}).")
    # --- Cleanup Logic --- END ---
    
    return pdf_generated_successfully

def main():
    parser = argparse.ArgumentParser(description="Generate LaTeX report from GPT analysis data")
    parser.add_argument('--input', '-i', type=str, required=True, help="Path to JSON file with GPT analysis data")
    parser.add_argument('--output', '-o', type=str, default="ui_analysis_report", help="Base output path for report files (e.g., /path/to/report_base)")
    parser.add_argument('--pdf', '-p', action='store_true', help="Try to generate PDF after creating LaTeX file")
    parser.add_argument('--gemini-data', '-g', type=str, help="Path to JSON file with Gemini coordinates data")
    parser.add_argument('--image', '-img', type=str, help="Path to the analyzed image for illustrations")
    parser.add_argument('--heatmap', type=str, help="Path to the heatmap image for report visualization")
    args = parser.parse_args()

    # --- Determine full .tex path --- START ---    
    output_base_path = args.output
    # Ensure the base path doesn't somehow end with .tex already
    if output_base_path.lower().endswith('.tex'):
        output_base_path = output_base_path[:-4]
        
    # Construct the explicit .tex file path
    latex_output_path = f"{output_base_path}.tex"
    # --- Determine full .tex path --- END ---
    
    print("--- Debug: Starting main function ---")
    print(f"  Input GPT data: {args.input}")
    print(f"  Output .tex file: {latex_output_path}")
    print(f"  Generate PDF: {args.pdf}")
    print(f"  Gemini data file: {args.gemini_data}")
    print(f"  Image file: {args.image}")
    print(f"  Heatmap file: {args.heatmap}")
    
    data = load_analysis_data(args.input)
    if not data:
        print("Failed to load analysis data. Exiting.")
        return
    print(f"  GPT data loaded successfully.")
    
    if args.gemini_data and os.path.exists(args.gemini_data):
        print(f"  Attempting to load Gemini data from {args.gemini_data}...")
        try:
            with open(args.gemini_data, 'r', encoding='utf-8') as f:
                gemini_data = json.load(f)
                if isinstance(gemini_data, dict) and "element_coordinates" in gemini_data:
                    data["coordinates"] = gemini_data
                    print(f"  Loaded coordinates data from {args.gemini_data}. Found {len(gemini_data['element_coordinates'])} elements.")
                else:
                    print(f"  ERROR: Gemini data file {args.gemini_data} has unexpected structure. Expected a dict with 'element_coordinates'.")
        except Exception as e:
            print(f"  ERROR: Error loading Gemini data: {e}")
    elif args.gemini_data:
        print(f"  WARNING: Gemini data file not found at {args.gemini_data}")
    else:
        print("  No Gemini data file provided.")
        
    if args.image and os.path.exists(args.image):
        print(f"  Image file found at {args.image}. Adding path to data.")
        if "metaInfo" not in data: data["metaInfo"] = {}
        data["metaInfo"]["imagePath"] = os.path.abspath(args.image)
        print(f"  Added absolute image path to data: {data['metaInfo']['imagePath']}")
    elif args.image:
         print(f"  WARNING: Image file not found at {args.image}")
    else:
        print("  No image file provided.")
        
    # Добавляем путь к тепловой карте в данные
    if args.heatmap and os.path.exists(args.heatmap):
        print(f"  Heatmap file found at {args.heatmap}. Adding path to data.")
        if "metaInfo" not in data: data["metaInfo"] = {}
        data["metaInfo"]["heatmapPath"] = os.path.abspath(args.heatmap)
    elif args.heatmap:
        print(f"  WARNING: Heatmap file not found at {args.heatmap}")
    
    print("--- Debug: Proceeding to generate LaTeX document ---")
    latex_content = generate_latex_document(data)
    
    if save_latex_to_file(latex_content, latex_output_path):
        print(f"Report generation complete. LaTeX file saved to {latex_output_path}")
        if args.pdf:
            generate_pdf(latex_output_path)
        else:
            print(f"To convert to PDF, run: pdflatex {os.path.basename(latex_output_path)}")
            print("Or run this script with --pdf flag.")

if __name__ == "__main__":
    main() 