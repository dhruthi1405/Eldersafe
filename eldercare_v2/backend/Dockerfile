# Backend Dockerfile
FROM python:3.9-slim

WORKDIR /app

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=1200 \
    PIP_PROGRESS_BAR=off

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifests separately so Docker can cache lightweight
# app/auth packages independently from the heavy ML stack.
COPY requirements.app.txt requirements.ml.txt requirements.txt ./

# Install Python dependencies in two layers. This keeps torch/opencv/mediapipe
# cached even when we only tweak API/auth packages.
RUN pip install --no-cache-dir --retries 10 -r requirements.app.txt
RUN pip install --no-cache-dir --retries 10 -r requirements.ml.txt

# Copy application
COPY . .

# Create upload/output directories
RUN mkdir -p uploads outputs logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')"

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
