# Dockerfile (development)
FROM python:3.12-slim

# Thiết lập biến môi trường
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.dev

WORKDIR /app

# Cài đặt system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements/base.txt requirements/dev.txt ./requirements/
RUN pip install \
    --default-timeout=1000 \
    --retries 10 \
    --no-cache-dir \
    -r requirements/dev.txt

# Copy source code
COPY . .

# Copy và cấp quyền entrypoint script
COPY docker/scripts/entrypoint.dev.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
