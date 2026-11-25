FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PORT=8000

WORKDIR /app

# Install Python dependencies first for better layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY engine/ ./engine/
COPY server/ ./server/
COPY frontend/ ./frontend/

# Ensure writable local data directory for SQLite mirror & runtime proxy file
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn server.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
