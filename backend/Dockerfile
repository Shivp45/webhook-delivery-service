# Dockerfile for both the FastAPI app and the Celery worker
# (the CMD is overridden per service in docker-compose.yml)

FROM python:3.12-slim

# Set working directory inside the container
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY app/ ./app/

# Default command — runs the FastAPI server
# The Celery worker service overrides this in docker-compose.yml
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
