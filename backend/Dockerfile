# RSC Administrative Productivity Suite — Backend
# Deploy-agnostic: works on Render (Docker runtime), Cloud Run, and HF Spaces.
# Lightweight by design: no LibreOffice — PDF annex is generated with fpdf2.
FROM python:3.10-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Minimal system deps (none required for parsing — kept tiny on purpose)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Non-root user (Hugging Face Spaces convention: UID 1000)
RUN useradd -m -u 1000 user
COPY --chown=user:user . /app
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860

EXPOSE 7860

# $PORT is provided by Render/Cloud Run; HF Spaces uses 7860 (our default)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-7860}"]
