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

if ! curl --disable --noproxy '*' --proto '=http' --silent --fail \
    --connect-timeout 2 --max-time 10 --url-query "apikey@$work/key" \
    --url-query 'configured=true' --output "$work/indexers.json" \
    http://127.0.0.1:9117/api/v2.0/indexers 2>/dev/null ||
    ! jq -er 'if type == "array" and all(.[];
        (.id | type == "string" and test("^[a-z0-9_-]+$")))
        then map(.id) | unique | .[] else error("invalid indexers") end' \
        "$work/indexers.json" > "$work/ids" 2>/dev/null; then
    echo 'Jackett startup warm-up: no usable configured indexers; no tests scheduled.'
    exit 0
fi

deadline=$(($(date +%s) + 110))
attempted=0
succeeded=0
while IFS= read -r id; do
    remaining=$((deadline - $(date +%s)))
    [ "$remaining" -gt 0 ] || break
    [ "$remaining" -le 45 ] || remaining=45
    attempted=$((attempted + 1))
    # Exactly one Test invocation per configured indexer; Jackett itself owns
    # tracker pagination/challenge handling. The helper never retries it.
    code=$(curl --disable --noproxy '*' --proto '=http' --silent --fail \
        --connect-timeout 2 --max-time "$remaining" --request POST \
        --url-query "apikey@$work/key" --output /dev/null --write-out '%{http_code}' \
        "http://127.0.0.1:9117/api/v2.0/indexers/$id/test" 2>/dev/null) || code=failed
    if [ "$code" = 204 ]; then
        succeeded=$((succeeded + 1))
    fi
done < "$work/ids"
echo "Jackett startup warm-up: finished ($succeeded/$attempted tests succeeded); no retries scheduled."
