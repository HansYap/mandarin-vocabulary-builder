FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt && \
    pip install sacremoses

RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('Helsinki-NLP/opus-mt-zh-en')"

COPY . /app/backend/

ENV PYTHONPATH=/app

CMD ["python", "-m", "backend.run"]