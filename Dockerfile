# Use official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE=mhe_backend.settings

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Convert line endings and make entrypoint executable
RUN sed -i 's/\r$//g' entrypoint.sh && \
    chmod +x entrypoint.sh

# Use Render's PORT environment variable
CMD gunicorn mhe_backend.wsgi:application --bind 0.0.0.0:$PORT --workers 4

