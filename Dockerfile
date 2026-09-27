# NeuroLens — one image: Angular dashboard + FastAPI API + model inference
#
# Build and push (run from the code/ folder):
#   docker build -t mlprojectdocker.azurecr.io/neurolens:latest .
#   docker login mlprojectdocker.azurecr.io
#   docker push mlprojectdocker.azurecr.io/neurolens:latest

# ---------- 1. Build the Angular dashboard ----------
FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npx ng build --configuration production

# ---------- 2. Python API (serves the dashboard too) ----------
FROM python:3.12-slim

# Prevent Python from writing .pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TF_CPP_MIN_LOG_LEVEL=3 \
    HF_HOME=/app/.cache/huggingface \
    STATIC_DIR=/app/static

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# Copy the API code and the built dashboard (see .dockerignore for exclusions)
COPY backend/ .
COPY --from=frontend /frontend/dist/neurolens-dashboard/browser ./static

# Run as a non-root user
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /app/logs /app/.cache/huggingface \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# The API answers immediately; the model loads in the background
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
