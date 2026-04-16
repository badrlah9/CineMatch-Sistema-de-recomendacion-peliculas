FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY data ./data
COPY artifacts ./artifacts

EXPOSE 8000

CMD ["uvicorn", "cinematch.fastapi_app:app", "--host", "0.0.0.0", "--port", "8000"]
