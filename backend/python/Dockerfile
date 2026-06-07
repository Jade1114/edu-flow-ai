FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY backend/python/pyproject.toml .
RUN pip install --no-cache-dir hatchling && pip install --no-cache-dir .

# Copy the app package
COPY backend/python/app/ ./app/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD [ "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" ]
