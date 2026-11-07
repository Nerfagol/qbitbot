# Maintain only these OS fixes over the reviewed upstream application.
FROM lscr.io/linuxserver/jackett@sha256:f235901dce0b102b2e8da55420d4a9b8d183dc8fff1e89bb6215209e066924cc
RUN apk add --upgrade --no-cache brotli-libs=1.2.1-r0 musl=1.2.6-r3 musl-utils=1.2.6-r3 curl=8.23.0-r0 libcurl=8.23.0-r0
