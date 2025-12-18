# ArrTheAudio - Multi-stage Dockerfile
# Stage 1: Builder - compile Python dependencies
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and build wheels
COPY requirements-prod.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-prod.txt

# Stage 2: Runtime - minimal image with pre-built wheels
FROM python:3.11-slim

# Install runtime dependencies (ffmpeg and mkvtoolnix)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    mkvtoolnix \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built wheels from builder
COPY --from=builder /wheels /wheels

# Install wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

# Create application directory
WORKDIR /app

# Copy application source
COPY src/ /app/src/
COPY pyproject.toml /app/

# Install the application
RUN pip install -e .

# Create directories for config and logs
RUN mkdir -p /config /logs /media

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:9393/health || exit 1

# Expose daemon port
EXPOSE 9393

# Default command (can be overridden)
CMD ["arrtheaudio", "daemon"]
