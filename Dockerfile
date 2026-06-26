FROM python:3.11-slim

# Install Node.js (for html-to-docx npm package)
RUN apt-get update && apt-get install -y \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install flask gunicorn --no-cache-dir

# Copy files
WORKDIR /app
COPY package.json /app/package.json
COPY convert.js /app/convert.js
COPY app.py /app/app.py

# Install Node.js dependencies
RUN npm install

EXPOSE 10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "--workers", "1", "app:app"]
