# Visual Analyzer Bot Data Flow

```
┌──────────┐     ┌───────────────┐     ┌───────────────┐
│  User    │────▶│ Telegram Bot  │────▶│ Image         │
│          │◀────│ Interface     │◀────│ Processing    │
└──────────┘     └───────────────┘     └───────────────┘
                                              │
                                              ▼
┌──────────────────┐     ┌───────────────┐     ┌───────────────┐
│ Heatmap          │◀────│ Coordinate    │◀────│ GPT-4.1       │
│ Generation       │     │ Extraction    │     │ Analysis      │
└──────────────────┘     └───────────────┘     └───────────────┘
      │                         ▲
      │                         │
      │                  ┌──────────────┐
      └─────────────────▶│ Gemini 2.5   │
                         │ Localization │
                         └──────────────┘
```

## Process Flow Description

1. **User Interaction**
   - User sends a screenshot and description to the Telegram bot
   - Bot validates the input and initiates the analysis process

2. **Image Processing**
   - Image is processed (resizing, encoding) for API submission
   - User description is formatted for inclusion in prompts

3. **GPT-4.1 Analysis**
   - Screenshot and description are sent to GPT-4.1
   - GPT-4.1 analyzes the UI based on UX principles
   - Response includes issues, severity, and recommendations
   - JSON response is parsed and validated

4. **Coordinate Extraction**
   - Issues identified by GPT-4.1 are sent to Gemini 2.5
   - Original screenshot is included for reference
   - Gemini 2.5 identifies coordinates for each issue
   - Coordinate data is validated and filtered

5. **Heatmap Generation**
   - Issue coordinates are converted to a heatmap
   - Severity levels determine intensity of the heatmap
   - Original image is overlaid with the heatmap

6. **Response Delivery**
   - Overlay image is sent to the user
   - Analysis summary with overall score is provided
   - Detailed issue descriptions are formatted and sent

## Error Handling Routes

- If GPT-4.1 fails to analyze the UI: fallback to basic image description
- If Gemini 2.5 fails to locate elements: provide text-only analysis
- If heatmap generation fails: send original image with text markers
- If network errors occur: implement retry mechanism with exponential backoff

## Performance Considerations

- Image resizing to optimize API costs
- Parallel processing where possible
- Caching of responses for repeated analyses
- Rate limiting to prevent API quota exhaustion 