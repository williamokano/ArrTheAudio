# ArrTheAudio - Dockerfile
FROM python:3.14-slim

# Install system dependencies (ffmpeg and mkvtoolnix)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    mkvtoolnix \
    && rm -rf /var/lib/apt/lists/*

# Create application directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements-prod.txt .
RUN pip install --no-cache-dir -r requirements-prod.txt

# Copy application source
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the application
RUN pip install -e .

# Create directories for config and logs
RUN mkdir -p /config /logs /media

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden)
CMD ["arrtheaudio", "--help"]
