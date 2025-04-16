visual_analyzer/
├── .env                        # Environment variables (API keys, etc.)
├── .gitignore                  # Git ignore file
├── README.md                   # Project documentation
├── implementation_plan.md      # Implementation plan with status
├── requirements.txt            # Project dependencies
├── main.py                     # Entry point for the application
├── config.py                   # Configuration management
├── Procfile                    # For Railway deployment
├── railway.json                # Railway configuration
├── firebase_config.py          # Firebase configuration and setup
├── bot/
│   ├── __init__.py
│   ├── handlers.py             # Telegram bot handlers
│   ├── conversation.py         # Conversation management
│   └── responses.py            # Response formatting
├── services/
│   ├── __init__.py
│   ├── openai_service.py       # GPT-4.1 API integration
│   ├── gemini_service.py       # Gemini API integration
│   ├── firebase_service.py     # Firebase integration
│   └── image_processor.py      # Image encoding/processing
├── analysis/
│   ├── __init__.py
│   ├── gpt_prompt.py           # GPT prompt templates
│   ├── gemini_prompt.py        # Gemini prompt templates
│   ├── parser.py               # JSON response parser
│   └── heatmap.py              # Heatmap generation
├── utils/
│   ├── __init__.py
│   ├── logger.py               # Logging utilities
│   ├── error_handler.py        # Error handling
│   └── validators.py           # Input/output validation
├── deploy/
│   ├── railway_deploy.md       # Railway deployment guide
│   └── firebase_setup.md       # Firebase setup instructions
└── tests/
    ├── __init__.py
    ├── test_bot.py             # Bot tests
    ├── test_services.py        # API service tests
    ├── test_analysis.py        # Analysis module tests
    └── fixtures/               # Test fixtures and sample images
        ├── sample_ui_1.png
        ├── sample_ui_2.png
        └── sample_responses/
            ├── gpt_response.json
            └── gemini_response.json 