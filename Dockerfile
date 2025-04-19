# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install essential packages including libmagic for the 'magic' Python module
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Install TeX Live with support for Cyrillic/Russian and all necessary packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-latex-base \
    texlive-latex-recommended \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-lang-cyrillic \
    && rm -rf /var/lib/apt/lists/*

# Create a simple test to verify LaTeX installation with Cyrillic support
RUN echo '\\documentclass{article}\\usepackage[T2A]{fontenc}\\usepackage[utf8]{inputenc}\\usepackage[russian]{babel}\\begin{document}Тест русского языка\\end{document}' > /tmp/test.tex \
    && pdflatex -output-directory=/tmp /tmp/test.tex \
    && ls -la /tmp/test.pdf \
    && echo "LaTeX Cyrillic support verified"

WORKDIR /app

COPY requirements.txt ./
# Explicitly install python-magic first, then the rest
RUN pip install --no-cache-dir python-magic==0.4.27 && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Make sure scripts are executable
RUN chmod +x *.py

CMD ["python", "bot.py"]

# redeploy trigger: with LaTeX Cyrillic support 