#!/usr/bin/env python3
"""
Script to generate recommendations and identify key problems using Gemini API.

This script takes the JSON output from the GPT-4.1 analysis as input,
loads a prompt from a specified file, and queries the Gemini API
to obtain insights and recommendations based on the analysis data.
"""

import os
import json
import argparse
from dotenv import load_dotenv
# Assuming google.generativeai will be used for the API call
import google.generativeai as genai

def load_gpt_analysis(json_file_path):
    """Load analysis data from the GPT-4.1 JSON file."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Successfully loaded GPT analysis data from: {json_file_path}")
        return data
    except FileNotFoundError:
        print(f"Error: Input JSON file not found at {json_file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {json_file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while loading JSON: {e}")
        return None

def load_prompt(prompt_file_path):
    """Load the prompt template from a file."""
    try:
        with open(prompt_file_path, 'r', encoding='utf-8') as f:
            # Remove <prompt> tags if they exist
            prompt_content = f.read()
            if prompt_content.startswith('<prompt>') and prompt_content.endswith('</prompt>'):
                 prompt_content = prompt_content[len('<prompt>'):-len('</prompt>')].strip()
            prompt = prompt_content
        print(f"Successfully loaded prompt from: {prompt_file_path}")
        return prompt
    except FileNotFoundError:
        print(f"Error: Prompt file not found at {prompt_file_path}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while loading the prompt: {e}")
        return None

def query_gemini(prompt_template, analysis_data):
    """Query the Gemini API with the analysis data and prompt."""
    print("\n--- Querying Gemini API ---")
    
    # 1. Configure the Gemini API client
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment variables.")
        return None
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
        return None
        
    # 2. Prepare the combined prompt
    try:
        formatted_data = json.dumps(analysis_data, indent=2, ensure_ascii=False)
        # Use str.replace instead of format to avoid issues with {} in JSON
        full_prompt = prompt_template.replace("{analysis_json}", formatted_data)
    except Exception as e:
        print(f"Error formatting prompt with analysis data: {e}")
        return None
        
    # 3. Select the Gemini model
    # Use the exact model name provided
    model_name = 'gemini-2.5-pro-preview-03-25'
    try:
        model = genai.GenerativeModel(model_name)
        print(f"Using Gemini model: {model_name}")
    except Exception as e:
        print(f"Error creating Gemini model instance: {e}")
        return None

    # 4. Make the API call
    try:
        print("Sending request to Gemini...")
        # Add safety settings if needed, otherwise use defaults
        response = model.generate_content(
            full_prompt,
            # safety_settings=[
            #     { "category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE" },
            #     { "category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE" },
            #     { "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE" },
            #     { "category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE" },
            # ]
        )
        print("Received response from Gemini.")
        
        # Basic check if response has text (might need more robust checks)
        if hasattr(response, 'text'):
            # Attempt to clean the response: remove potential markdown code block fences
            cleaned_response = response.text.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[len('```json'):].strip()
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-len('```')].strip()
            return cleaned_response
        elif hasattr(response, 'prompt_feedback'):
             print(f"Gemini request blocked. Feedback: {response.prompt_feedback}")
             return None
        else:
             print("Gemini response structure unexpected or missing text.")
             print(f"Full response object: {response}")
             return None
             
    except Exception as e:
        print(f"Error during Gemini API call: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description="Generate recommendations using Gemini based on GPT analysis.")
    parser.add_argument('--input', '-i', type=str, required=True, 
                        help="Path to the input JSON file from GPT-4.1 analysis.")
    parser.add_argument('--prompt-file', '-p', type=str, 
                        required=True, # Make prompt file required
                        help="Path to the file containing the Gemini prompt template (e.g., gemini_interpretation_prompt.md or gemini_recommendations_only_prompt.md).")
    parser.add_argument('--output', '-o', type=str, 
                        help="Optional: Path to save the Gemini response JSON file.")
    
    args = parser.parse_args()

    # Load data and prompt
    analysis_data = load_gpt_analysis(args.input)
    if not analysis_data:
        return

    prompt_template = load_prompt(args.prompt_file)
    if not prompt_template:
        return

    # Query Gemini (using placeholder function for now)
    gemini_response_text = query_gemini(prompt_template, analysis_data)

    if gemini_response_text:
        print("\n--- Gemini Response ---")
        print(gemini_response_text)
        
        # Optionally save the response to a file
        if args.output:
            try:
                with open(args.output, 'w', encoding='utf-8') as f:
                    # Assuming the response is already a JSON string
                    # If not, you might need json.dump(json.loads(gemini_response_text), f, ...)
                    f.write(gemini_response_text)
                print(f"\nSuccessfully saved Gemini response to: {args.output}")
            except Exception as e:
                print(f"Error saving Gemini response to file: {e}")
    else:
        print("\nFailed to get a response from Gemini.")

if __name__ == "__main__":
    main() 