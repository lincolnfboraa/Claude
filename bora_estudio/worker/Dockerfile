# Editor do Bora Studio: ffmpeg + transcrição + scripts de edição
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git zip && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir faster-whisper==1.2.1 numpy pillow anthropic==2.7.0 requests "rembg==2.0.67" onnxruntime
RUN python3 -c "from rembg import new_session; new_session('u2net_human_seg')"
WORKDIR /app
COPY . /app
ENV PYTHONUNBUFFERED=1
EXPOSE 8787
CMD ["python3", "bora_estudio/worker/servidor.py"]
