# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install essential packages and TeX Live for PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install minimal TeX Live for PDF generation
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-recommended \
    && rm -rf /var/lib/apt/lists/*

# Install additional packages only if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-fonts-recommended \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]

# redeploy trigger: cosmetic bump 