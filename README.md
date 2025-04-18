# Visual Interface Analyzer Bot

This Telegram bot analyzes UI screenshots by using advanced AI models (GPT-4.1 and Gemini 2.5) to identify usability issues and visualize them with heatmaps.

## Project Overview

The bot works through the following process:
1. User sends a screenshot and provides information about the user flow/interface
2. Bot processes this input and sends it to GPT-4.1 with a specialized prompt
3. GPT-4.1 returns a structured JSON with identified UI issues
4. Bot extracts the issues and sends them to Gemini 2.5 to get coordinate data
5. Bot generates a heatmap overlay highlighting the problem areas
6. Bot returns to the user:
   - Original screenshot with heatmap overlay
   - Interface evaluation score
   - Detailed description of identified issues

## Architecture

### Components

1. **Telegram Bot Interface**
   - Handles user interactions
   - Manages conversation flow
   - Processes incoming images
   - Sends responses back to users

2. **GPT-4.1 Integration**
   - Communicates with OpenAI API
   - Sends formatted prompts with context and screenshots
   - Processes JSON responses with UI issues

3. **Gemini 2.5 Integration**
   - Communicates with Google Gemini API
   - Receives UI issues and original image
   - Returns coordinate data for each issue

4. **Heatmap Generator**
   - Processes coordinate data
   - Creates visual heatmap overlay
   - Combines overlay with original image

5. **Data Processing Module**
   - Parses JSON responses
   - Formats data between services
   - Structures final output for users

6. **Firebase Integration (Optional)**
   - Stores analysis history
   - Manages user data and preferences
   - Provides backup for screenshots and results

### Data Flow

```
User → Telegram Bot → GPT-4.1 → Parser → Gemini 2.5 → Heatmap Generator → User
                     ↕
                  Firebase
```

## Technical Stack

- **Language**: Python
- **Bot Framework**: python-telegram-bot
- **AI Services**:
  - OpenAI API (GPT-4.1)
  - Google Gemini API (gemini-2.5-pro-preview-03-25)
- **Image Processing**: Pillow/OpenCV
- **Configuration**: Environment variables for API keys and settings
- **Deployment**: Railway
- **Storage (Optional)**: Firebase

## Setup and Deployment

1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment variables:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram bot token
   - `OPENAI_API_KEY`: Your OpenAI API key
   - `GEMINI_API_KEY`: Your Google Gemini API key
   - `FIREBASE_CONFIG` (if using Firebase): Your Firebase config JSON
3. Run the bot locally: `python main.py`
4. Deploy to Railway:
   - Connect your repository to Railway
   - Configure environment variables in Railway dashboard
   - Railway will automatically build and deploy

## Usage Guide

1. Start a conversation with the bot on Telegram
2. Send a screenshot of the UI you want to analyze
3. Provide a brief description of the user flow and interface context
4. Wait for processing (typically 1-2 minutes)
5. Receive analysis results with heatmap visualization

For detailed implementation status, see [implementation_plan.md](implementation_plan.md).

<!-- redeploy trigger: cosmetic bump --> 