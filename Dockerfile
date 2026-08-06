FROM python:3.12-slim

# System deps: ffmpeg + fonts (Vietnamese)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-liberation \
    fonts-noto-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/outputs /app/cache /app/logs /app/assets/music /app/workflows

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV AVA_GRADIO_SERVER_NAME=0.0.0.0
ENV AVA_GRADIO_SERVER_PORT=7860
ENV AVA_RENDER_MODE=cpu
ENV AVA_COMFYUI_ENABLED=false

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/')" || exit 1

CMD ["python", "run.py"]
