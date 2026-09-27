FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PTB_USE_AIOHTTP=0 \
    WATCH_DB_PATH=/state/watches.sqlite3

COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r /app/requirements.lock
COPY qbitbot /app/qbitbot

CMD ["python", "-m", "qbitbot"]
COPY LICENSE THIRD_PARTY_NOTICES.md /app/
