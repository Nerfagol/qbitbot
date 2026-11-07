#!/bin/sh
# One best-effort warm-up per container boot. Never run as an s6 longrun.
set -eu

mode=${1:-warmup}
config=${2:-/config/Jackett}
state=${3:-/run/qbitbot-jackett}
boot="$(cat /proc/sys/kernel/random/boot_id)-$(awk '{print $22}' /proc/1/stat)"

if [ "$mode" = health ]; then
    if [ "${JACKETT_WARMUP_ON_START:-0}" = 1 ]; then
        [ "$(cat "$state/complete" 2>/dev/null)" = "$boot" ] || exit 1
    fi
    exec curl --disable --noproxy '*' --fail --silent --output /dev/null \
        --max-time 4 http://127.0.0.1:9117/UI/Dashboard
fi
[ "$mode" = warmup ] || exit 2

umask 077
mkdir -p "$state"
# Atomic ownership also prevents accidental repeated/manual calls this boot.
mkdir "$state/attempt-$boot" 2>/dev/null || exit 0
work=$(mktemp -d "$state/private.XXXXXX")
finish() {
    rm -rf "$work"
    printf '%s\n' "$boot" > "$state/complete.tmp"
    mv "$state/complete.tmp" "$state/complete"
}
trap finish 0

[ "${JACKETT_WARMUP_ON_START:-0}" = 1 ] || exit 0
# Only the bundled local service origin is supported. Never infer another URL
# from configuration, follow redirects, use a proxy or print API errors/secrets.
if ! jq -e '(.Port // 9117) == 9117 and
    ((.BasePathOverride // "") == "" or .BasePathOverride == "/")' \
    "$config/ServerConfig.json" >/dev/null 2>&1 ||
    ! jq -jer '.APIKey | select(type == "string" and length > 0)' \
        "$config/ServerConfig.json" > "$work/key" 2>/dev/null; then
    echo 'Jackett startup warm-up: skipped (local configuration unavailable/unsupported).'
    exit 0
fi

# Management Test/list APIs require a dashboard cookie even with a valid API
# key. Use the same API-key-authorized manual search route as the bot instead;
# an empty query touches configured sources once without a dashboard password.
if curl --disable --noproxy '*' --proto '=http' --silent --fail \
    --connect-timeout 2 --max-time 110 --url-query "apikey@$work/key" \
    --url-query 'query=' --output "$work/response.json" \
    http://127.0.0.1:9117/api/v2.0/indexers/all/results 2>/dev/null &&
    sources=$(jq -er '.Indexers | if type == "array" then length
        else error("invalid response") end' "$work/response.json" 2>/dev/null); then
    echo "Jackett startup warm-up: finished ($sources sources reported); no retries scheduled."
else
    echo 'Jackett startup warm-up: failed; no retries scheduled.'
fi
