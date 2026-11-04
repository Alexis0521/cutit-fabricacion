FROM python:3.11.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini .
CMD ["sh", "-c", "uvicorn app.main:app --host ${API_HOST:?Set API_HOST} --port ${API_PORT:?Set API_PORT}"]
