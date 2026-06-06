FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY backend/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the python package
COPY backend/python/ ./python/

# uvicorn imports from ml.api.main
ENV PYTHONPATH=/app

EXPOSE 8000

CMD [ "uvicorn", "python.api.main:app", "--host", "0.0.0.0", "--port", "8000" ]
