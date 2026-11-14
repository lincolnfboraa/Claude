# Editor do Bora Studio: ffmpeg + transcrição + scripts de edição
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-inter git && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir faster-whisper==1.0.3 numpy pillow anthropic==0.39.0 requests
WORKDIR /app
COPY . /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8787
CMD ["python3", "bora_estudio/worker/servidor.py"]
