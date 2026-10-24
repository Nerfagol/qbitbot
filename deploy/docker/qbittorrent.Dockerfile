# Maintain only these OS fixes over the reviewed upstream application.
FROM lscr.io/linuxserver/qbittorrent@sha256:e887804fa9de4c60f5f0fb1f3a7e4febe40a8f69fe736f70c4e8589b1f868dab
RUN apk add --upgrade --no-cache brotli-libs=1.2.1-r0 musl=1.2.6-r3 musl-utils=1.2.6-r3
