#!/usr/bin/env python3
"""
Create Sample UI Image

This script generates a sample login UI screen for testing the visual analysis functionality.
"""

from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

# Ensure output directory exists
os.makedirs("tests/fixtures", exist_ok=True)

# Create a new image with white background
width, height = 1080, 1920  # Standard mobile resolution
image = Image.new('RGB', (width, height), color='white')
draw = ImageDraw.Draw(image)

# Try to load a font, fall back to default if not available
try:
    # Attempt to load a system font
    font_large = ImageFont.truetype("Arial", 60)
    font_medium = ImageFont.truetype("Arial", 40)
    font_small = ImageFont.truetype("Arial", 30)
except IOError:
    # Fall back to default font
    font_large = ImageFont.load_default()
    font_medium = ImageFont.load_default()
    font_small = ImageFont.load_default()

# Add app header/logo area
draw.rectangle([0, 0, width, 200], fill="#4285F4")
draw.text((width//2, 100), "Login", fill="white", font=font_large, anchor="mm")

# Add email input field
draw.rectangle([100, 300, width-100, 400], outline="#CCCCCC", width=2)
draw.text((120, 320), "Email", fill="#888888", font=font_medium)

# Add password input field with deliberate UX issues (too close to email field)
draw.rectangle([100, 420, width-100, 520], outline="#CCCCCC", width=2)
draw.text((120, 440), "Password", fill="#888888", font=font_medium)

# Add login button (deliberately making it too small for easy clicking - a UX issue)
button_width, button_height = 120, 60
button_x = (width - button_width) // 2
button_y = 580
draw.rectangle([button_x, button_y, button_x + button_width, button_y + button_height], 
               fill="#4285F4")
draw.text((button_x + button_width//2, button_y + button_height//2), 
          "LOGIN", fill="white", font=font_small, anchor="mm")

# Add "Forgot Password" link (deliberately poor contrast - a UX issue)
draw.text((width//2, 700), "Forgot Password?", fill="#DDDDDD", font=font_small, anchor="mm")

# Add social login options (deliberately too close together - a UX issue)
# Google
draw.ellipse([width//2 - 150 - 40, 800 - 40, width//2 - 150 + 40, 800 + 40], fill="#DB4437")
draw.text((width//2 - 150, 800), "G", fill="white", font=font_medium, anchor="mm")

# Facebook - placed too close to Google button
draw.ellipse([width//2 - 40, 800 - 40, width//2 + 40, 800 + 40], fill="#3b5998")
draw.text((width//2, 800), "f", fill="white", font=font_medium, anchor="mm")

# Twitter/X - also too close
draw.ellipse([width//2 + 150 - 40, 800 - 40, width//2 + 150 + 40, 800 + 40], fill="#000000")
draw.text((width//2 + 150, 800), "X", fill="white", font=font_medium, anchor="mm")

# Add "Sign Up" text (deliberately making it small and hard to find - a UX issue)
draw.text((width//2, 950), "Don't have an account? Sign Up", fill="#999999", font=font_small, anchor="mm")

# Save the image
output_path = "tests/fixtures/sample_ui_1.png"
image.save(output_path)
print(f"Sample UI image created at: {output_path}") 