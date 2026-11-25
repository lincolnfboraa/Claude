# Editor do Bora Studio: ffmpeg + transcrição + scripts de edição
FROM python:3.11-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg git zip && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir faster-whisper==1.2.1 numpy pillow anthropic==2.7.0 openai==3.57.0 requests "rembg==2.0.67" onnxruntime pywebpush==2.0.3
RUN python3 -c "from rembg import new_session; new_session('u2net_human_seg')"
RUN pip install --no-cache-dir --force-reinstall --no-deps opencv-python-headless==4.10.0.84 && python3 -c "import cv2; cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_alt2.xml')" || true
WORKDIR /app
COPY . /app
ENV PYTHONUNBUFFERED=1
ENV BORA_IMAGEM=1
EXPOSE 8787
CMD ["python3", "bora_estudio/worker/servidor.py"]
