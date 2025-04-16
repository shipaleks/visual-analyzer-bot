# API Testing

This directory contains tests for the Visual Interface Analyzer, with a focus on validating API integrations before building the complete Telegram bot.

## Setup

1. Make sure you have set up your virtual environment and installed the required dependencies:
   ```
   pip install -r ../requirements.txt
   ```

2. Create a `.env` file in the project root with your API keys:
   ```
   OPENAI_API_KEY=your_openai_api_key
   GEMINI_API_KEY=your_gemini_api_key
   ```

3. Add sample UI screenshots to the `fixtures` directory:
   ```
   mkdir -p fixtures
   # Copy your test UI screenshots to fixtures/sample_ui_1.png, etc.
   ```

## Running the API Tests

To test the API integrations, run:

```bash
python api_test.py
```

This script performs the following tests:
1. Tests the GPT-4.1 API for UI analysis
2. Tests the Gemini 2.5 API for coordinate extraction
3. Tests the heatmap generation functionality

## Test Output

The tests will generate the following outputs:
- `fixtures/sample_responses/gpt_response.json` - JSON response from GPT-4.1
- `fixtures/sample_responses/gemini_response.json` - JSON response from Gemini 2.5
- `fixtures/test_heatmap.png` - Generated heatmap based on the coordinates

## Troubleshooting

### Common Issues

1. **API Key Errors**:
   - Ensure your API keys are correctly set in the `.env` file
   - Check that you have the necessary API access (e.g., GPT-4.1 may require specific access)

2. **Image Not Found**:
   - Ensure you have placed a sample UI screenshot at `fixtures/sample_ui_1.png`
   - Or modify the `TEST_IMAGE_PATH` in the script to point to your image

3. **JSON Parsing Errors**:
   - If either API returns non-JSON responses, the script will report the error
   - This may indicate an issue with the prompt or response format

4. **Coordinate Formatting**:
   - If the heatmap generation fails, check that the coordinate format is correct (should be [x1, y1, x2, y2])

## Customizing Tests

To test with different images or prompts:

1. Add your image files to the `fixtures` directory
2. Modify the `description` variable in `run_full_test()` to match your UI
3. If needed, adjust the prompt templates in the test functions 