FROM ghcr.io/flaresolverr/flaresolverr@sha256:c80ae007ce2ccdcd217a12426e4f039ef763ff90738c808d38810c3e59323767 AS upstream
FROM python:3.11.17-alpine3.24@sha256:5fb4bc53dd0180955e31e5245b648bbb24a4ac4ab03a1de81513642325220bcd
WORKDIR /app
COPY --from=upstream /app/ /app/
COPY --from=upstream /package.json /package.json
RUN apk upgrade --no-cache \
    && apk add --no-cache chromium chromium-chromedriver xvfb xauth dumb-init procps font-noto ca-certificates \
    && addgroup -g 1000 flaresolverr \
    && adduser -D -u 1000 -G flaresolverr -h /app flaresolverr \
    && cp /usr/bin/chromedriver /app/chromedriver \
    && sed -i 's/certifi==2026.7.22/certifi==2026.10.19/' /app/requirements.txt \
    && python -m pip install --no-cache-dir -r /app/requirements.txt urllib3==2.8.0 \
    && python -m pip check \
    && python -m pip uninstall -y pip setuptools wheel \
    && rm -rf /usr/local/lib/python3.11/site-packages/selenium/webdriver/common/linux/selenium-manager \
              /usr/local/lib/python3.11/site-packages/selenium/webdriver/common/macos/selenium-manager \
              /usr/local/lib/python3.11/site-packages/selenium/webdriver/common/windows/selenium-manager.exe \
              /usr/local/lib/python3.11/site-packages/selenium/webdriver/common/selenium-manager.cdx.json \
    && HOME=/tmp python -c 'from undetected_chromedriver.patcher import Patcher; p=Patcher(executable_path="/app/chromedriver"); p.auto(); assert p.is_binary_patched()' \
    && chown -R root:root /app \
    && chmod 755 /app/chromedriver \
    && mkdir /config && chown 1000:1000 /config
COPY docker/flaresolverr/LICENSE /usr/share/licenses/flaresolverr/LICENSE
COPY docker/flaresolverr/strict_tls.py /tmp/strict_tls.py
RUN python /tmp/strict_tls.py && rm /tmp/strict_tls.py
ENV HOME=/tmp PYTHONDONTWRITEBYTECODE=1
USER 1000:1000
EXPOSE 8191
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["/usr/local/bin/python", "-u", "/app/flaresolverr.py"]
