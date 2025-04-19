# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install essential packages including libmagic for the 'magic' Python module
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
# Explicitly install python-magic first, then the rest
RUN pip install --no-cache-dir python-magic==0.4.27 && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "bot.py"]

# redeploy trigger: cosmetic bump 