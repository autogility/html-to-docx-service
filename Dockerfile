FROM python:3.11-slim

# Install LibreOffice + dependencies
RUN apt-get update && apt-get install -y \
    libreoffice \
    libreoffice-writer \
    fonts-liberation \
    fonts-dejavu \
    wget \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install flask gunicorn --no-cache-dir

# Copy app
COPY app.py /app.py

# Render.com free tier requires port 10000
EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "--workers", "1", "app:app"]
