# Maintain only these OS fixes over the reviewed upstream application.
FROM lscr.io/linuxserver/jackett@sha256:d1b82a9c5bbaea44284a550af739bd838749b72f15b10ef61b6c9d9d1b2f1ed7
RUN apk add --upgrade --no-cache brotli-libs=1.2.1-r0 musl=1.2.6-r3 musl-utils=1.2.6-r3 curl=8.23.0-r0 libcurl=8.23.0-r0
