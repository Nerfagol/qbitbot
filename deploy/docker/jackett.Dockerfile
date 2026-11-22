# Maintain reviewed OS fixes and a restart-only, opt-in startup warm-up.
FROM lscr.io/linuxserver/jackett@sha256:6ff71f9c754a64190874851b726461b16e18b7680f237fd6eb9225a0622ec193
RUN apk add --upgrade --no-cache brotli-libs=1.2.1-r0 musl=1.2.6-r3 musl-utils=1.2.6-r3 curl=8.23.0-r0 libcurl=8.23.0-r0 \
    libcrypto3=3.5.9-r1 libssl3=3.5.9-r1
COPY --chmod=755 deploy/docker/jackett/startup.sh /usr/local/bin/qbitbot-jackett-startup
RUN mkdir -p /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/dependencies.d \
    && printf 'oneshot\n' > /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/type \
    && printf '/usr/bin/with-contenv /usr/local/bin/qbitbot-jackett-startup warmup\n' > /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/up \
    && printf '140000\n' > /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/timeout-up \
    && touch /etc/s6-overlay/s6-rc.d/qbitbot-jackett-warmup/dependencies.d/svc-jackett \
    && touch /etc/s6-overlay/s6-rc.d/user/contents.d/qbitbot-jackett-warmup
