# Образ для запуска NOWA на любом хостинге с Docker
# (Timeweb Cloud Apps, Selectel, Yandex Cloud Serverless Containers и т.п.)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

COPY web/requirements.txt web/requirements.txt
RUN pip install --no-cache-dir -r web/requirements.txt

COPY web/ web/

EXPOSE 8000

CMD gunicorn --chdir web --preload --workers 3 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT app:app
