# FastAPI backend + the AI package (ai/ is installed from source, like in dev).
# Build from the repo root:  docker build -f backend/Dockerfile -t oppradar-api .
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# OpenCV (pulled in by rapidocr for scanned CVs) needs these system libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# sentence-transformers (from ai/) pulls in PyTorch; the default wheel bundles
# CUDA (several GB). The API only needs the CPU build.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Dependencies first (cached until these files change), then the code.
COPY ai/pyproject.toml ai/README.md ai/
COPY ai/oppradar_ai ai/oppradar_ai
COPY backend/requirements.txt backend/
RUN cd backend && pip install -r requirements.txt

COPY ai/data ai/data
COPY backend/app backend/app
COPY backend/scripts backend/scripts

RUN useradd --create-home --uid 10001 oppradar && chown -R oppradar /app/ai/data
USER oppradar
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
