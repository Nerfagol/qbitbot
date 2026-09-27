FROM python:3.12.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PTB_USE_AIOHTTP=0 \
    WATCH_DB_PATH=/state/watches.sqlite3

COPY requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r /app/requirements.lock
COPY tg_torrent_bot.py watch_store.py monitoring.py downloads.py search_ui.py health.py settings.py setup_check.py /app/

CMD ["python", "/app/tg_torrent_bot.py"]
