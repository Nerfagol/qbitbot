# Maintain reviewed OS fixes and a restart-only, opt-in startup warm-up.
FROM lscr.io/linuxserver/jackett@sha256:f235901dce0b102b2e8da55420d4a9b8d183dc8fff1e89bb6215209e066924cc
RUN apk add --upgrade --no-cache brotli-libs=1.2.1-r0 musl=1.2.6-r3 musl-utils=1.2.6-r3 curl=8.23.0-r0 libcurl=8.23.0-r0
COPY --chmod=755 deploy/docker/jackett/startup.sh /usr/local/bin/qbitbot-jackett-startup
RUN mkdir -p /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/dependencies.d \
    && printf 'oneshot\n' > /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/type \
    && printf '/usr/bin/with-contenv /usr/local/bin/qbitbot-jackett-startup warmup\n' > /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/up \
    && printf '140000\n' > /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/timeout-up \
    && touch /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/dependencies.d/svc-jackett \
    && touch /etc/s6-overlay/s6-rc.d/user/contents.d/qbitbot-jackett-warmup
