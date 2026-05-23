FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY ml/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the ml package
COPY ml/ ./ml/

# uvicorn imports from ml.api.main
ENV PYTHONPATH=/app

EXPOSE 8000

CMD [ "uvicorn", "ml.api.main:app", "--host", "0.0.0.0", "--port", "8000" ]
