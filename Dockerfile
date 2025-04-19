# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install TeX Live for PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    # Dependencies for libraries like Pillow, numpy (often needed)
    libjpeg-dev \
    zlib1g-dev \
    # LaTeX dependencies
    texlive-latex-base \
    texlive-fonts-recommended \
    texlive-latex-extra \
    texlive-fonts-extra \
    lmodern \
    # For Cyrillic support
    texlive-lang-cyrillic \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]

# redeploy trigger: cosmetic bump 