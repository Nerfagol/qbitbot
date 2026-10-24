FROM python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d AS package
WORKDIR /build
COPY requirements/build.lock /build/requirements.build.lock
RUN python -m pip install --no-cache-dir pip==26.2.2 \
    && python -m pip install --no-cache-dir --no-deps -r /build/requirements.build.lock
COPY pyproject.toml README.md LICENSE /build/
COPY docs/licenses/THIRD_PARTY_NOTICES.md /build/docs/licenses/THIRD_PARTY_NOTICES.md
COPY src/qbitbot /build/src/qbitbot
RUN python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir /dist .

FROM python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PTB_USE_AIOHTTP=0 \
    WATCH_DB_PATH=/state/watches.sqlite3
COPY requirements/runtime.lock /app/requirements.lock
COPY --from=package /dist/*.whl /tmp/package/
# Build tooling lives in the package stage; runtime contains installed wheel/deps only.
RUN python -m pip install --no-cache-dir pip==26.2.2 \
    && python -m pip install --no-cache-dir -r /app/requirements.lock \
    && python -m pip install --no-index --no-deps /tmp/package/*.whl \
    && python -m pip uninstall --yes pip \
    && rm -rf /tmp/package
RUN addgroup -g 1000 bot && adduser -D -u 1000 -G bot bot \
    && mkdir /state && chown 1000:1000 /state && chmod 700 /state
USER 1000:1000
CMD ["python", "-m", "qbitbot"]
COPY LICENSE docs/licenses/THIRD_PARTY_NOTICES.md /app/
