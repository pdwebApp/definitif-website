FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

COPY requirements.txt ./

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && playwright install chromium

COPY . ./

CMD ["sh", "-c", "gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app"]