# Vertical Clipper container. FFmpeg comes from apt, so no extra setup is needed.
# Works locally (docker compose) and on Hugging Face Spaces (Docker SDK, port 7860).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLIPPER_WORK_DIR=/home/clipper/work \
    CLIPPER_MAX_UPLOAD_MB=500 \
    CLIPPER_MAX_SOURCE_MINUTES=30

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

# Spaces runs containers as uid 1000; run as the same non-root user everywhere.
RUN useradd --create-home --uid 1000 clipper

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static

RUN mkdir -p /home/clipper/work && chown -R clipper:clipper /home/clipper
USER clipper

EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}"]
