FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DATABASE_PATH=/app/data/bmd.db
ENV WORKFLOW_WAIT_TIME=20

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create data directory
RUN mkdir -p /app/data /app/static

# Copy application code
COPY app/ /app/

# Copy static assets
COPY static/ /app/static/

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Run the application
#CMD ["uvicorn", "main:fastapi_app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
CMD ["uvicorn", "main:fastapi_app", "--host", "0.0.0.0", "--port", "8080"]
