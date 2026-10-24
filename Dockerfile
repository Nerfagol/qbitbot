FROM python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PTB_USE_AIOHTTP=0 \
    WATCH_DB_PATH=/state/watches.sqlite3

COPY requirements.lock /app/requirements.lock
# The installer is build-only; exclude pip and its vendored libraries from runtime.
RUN python -m pip install --no-cache-dir pip==26.2.2 \
    && python -m pip install --no-cache-dir -r /app/requirements.lock \
    && python -m pip uninstall --yes pip
RUN addgroup -g 1000 bot && adduser -D -u 1000 -G bot bot \
    && mkdir /state && chown 1000:1000 /state && chmod 700 /state
COPY qbitbot /app/qbitbot

USER 1000:1000

CMD ["python", "-m", "qbitbot"]
COPY LICENSE THIRD_PARTY_NOTICES.md /app/
