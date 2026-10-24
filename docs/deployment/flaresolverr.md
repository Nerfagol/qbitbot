# Optional FlareSolverr

Some Jackett indexers need a browser to handle Cloudflare challenges. Enable this
only when required. FlareSolverr does not guarantee support for every challenge
or solve ordinary account CAPTCHA prompts. Tracker accounts stay in Jackett.

## Bundled stack

Use the overlay on every Compose command while the optional service is enabled:

```sh
docker compose -f compose.yaml -f compose.flaresolverr.yaml up -d --build
```

In Jackett's server settings, set **FlareSolverr API URL** to
`http://flaresolverr:8191` (no `/v1` suffix). Save, then test each indexer in Jackett
and try a Telegram search. Keep the management UI password-protected and bound
to loopback or a trusted management interface. No solver port needs publishing.
Existing services require equivalent private network connectivity configured by
their operator; the overlay is for the bundled stack, not bot-only mode.

For Kinozal, the magnet variant avoids the tracker's daily torrent-file download
limit. Preserve Cyrillic titles; title-rewriting options are unnecessary for this
bot. Site authentication/CAPTCHA may still require operator input.

To disable, clear Jackett's solver URL, stop/remove only `flaresolverr` using the
overlay, then recreate Jackett with the base Compose. Retain all state volumes;
never use `down -v` as a maintenance shortcut.

## Build and security

`docker/flaresolverr.Dockerfile` copies official FlareSolverr3.5.2 source from a
pinned release digest onto pinned Python3.11.17/Alpine3.24. Chromium155.0.8059.84
and its matching Alpine driver replace the vulnerable Debian browser/packages.
CA/urllib3 fixes are applied and unused installer/SeleniumManager binaries removed.
Two asserted patches enable certificate verification and reject Chromium internal
error documents, preventing invalid certificates from becoming false API success.
This is a local derivative that requires deliberate maintenance as upstream changes.

The API has no authentication. Only Jackett and FlareSolverr join its separate
Docker network; the API has **no published host port**. It intentionally accepts
arbitrary destination URLs, potentially including LAN services, so trust and
protect Jackett administration. The browser needs outbound Internet access.

UID/GID1000, read-only filesystem, dropped capabilities, no-new-privileges, default
Docker seccomp, bounded tmpfs,256MiB shared memory,1GiB RAM,1.5CPU and256PIDs
are enforced. No persistent solver data or credentials are mounted. Upstream
Chromium `--no-sandbox` remains a limitation: outer Docker isolation is enforced,
but browser-internal sandboxing is not claimed. Never add privileged mode,
host networking or unconfined security profiles to work around startup issues.

## Verification, 2026-10-24

Trivy0.76.1 database updated2026-10-24 07:11UTC found zero OS/Python vulnerability
records in the reviewed derived image, without suppressions. The stock release
had32 critical and1091 high records, including duplicated browser/package records.
Scan evidence is dated, not a guarantee against unknown vulnerabilities. Rebuild
and rescan when updating packages; package repositories can change between builds.

Linux amd64 browser JavaScript rendering and selfsigned-TLS rejection passed on
an isolated generated fixture under the runtime restrictions. Authorized live
amd64 acceptance also passed HTTPS navigation, challenge handling and Torznab
search responses for two indexers. No private deployment information, accounts,
response bodies or logs are included here. Other architectures remain unverified.

Run the synthetic smoke check against a newly built image:

```sh
docker build -f docker/flaresolverr.Dockerfile -t qbitbot-flaresolverr:local .
python3 integration/flaresolverr.py --image qbitbot-flaresolverr:local
```

The check requires Docker and host OpenSSL, creates only its own internal network
and generated fixtures, publishes no ports, and cleans up its own containers.
Weekly/on-change security CI builds/scans this optional image and runs this check.

References: [FlareSolverr](https://github.com/FlareSolverr/FlareSolverr),
[Jackett troubleshooting](https://github.com/Jackett/Jackett/wiki/Troubleshooting#challenge-detected-but-flaresolverr-is-not-configured).
