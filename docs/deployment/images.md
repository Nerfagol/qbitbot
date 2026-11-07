# Container inputs

Resolved on 2026-10-24 for Linux amd64, with Jackett refreshed on 2026-11-07.
These are immutable upstream manifest digests.

| Component | Input |
| --- | --- |
| Python | `python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d` |
| qBittorrent | `lscr.io/linuxserver/qbittorrent@sha256:e887804fa9de4c60f5f0fb1f3a7e4febe40a8f69fe736f70c4e8589b1f868dab` (5.3.0) |
| Jackett | `lscr.io/linuxserver/jackett@sha256:f235901dce0b102b2e8da55420d4a9b8d183dc8fff1e89bb6215209e066924cc` (0.24.3025, bundled .NET 9.0.22) |

Both service images contain `/usr/bin/curl`, verified in network-disabled temporary
containers. Readiness checks use that client without credentials. Jackett in-container
updates are disabled. Record full-stack verification separately; image selection is
not evidence that every supported platform has been tested.

The derived Jackett image also includes an opt-in native s6 startup oneshot
(`JACKETT_WARMUP_ON_START=1`, enabled by bundled Compose). It waits for the
service's readiness notification, privately reads the existing local API key and
makes one empty API-key search across configured indexers within a bounded budget. It installs no
packages or schedules at runtime. Its health helper gates on completion for the
current container boot, then probes only the Dashboard. See [operation and
limits](../troubleshooting.en.md#slow-first-search). Verify native startup and
restart behavior with `python integration/jackett_startup.py --image <image>`;
this uses synthetic loopback HTTP in a network-disabled namespace.

Re-resolve and test deliberately before changing these pins. Upstream image/platform
availability does not establish qbitbot support on that platform.

Compose builds the service inputs through `deploy/docker/qbittorrent.Dockerfile` and
`deploy/docker/jackett.Dockerfile`. These derived images pin Brotli libraries 1.2.1-r0 and
musl/musl-utils 1.2.6-r3 at build time. qBittorrent retains version 5.3.0;
Jackett's security refresh is described below.
The bot uses UID/GID 1000:1000. See [runtime restrictions and offline migration](container-hardening.md)
and the [dated security review](../archive/security/security-2026-10-24.md) for verification and scope.

Optional FlareSolverr3.5.2 upstream source digest:
`sha256:c80ae007ce2ccdcd217a12426e4f039ef763ff90738c808d38810c3e59323767`.
Its separate Python3.11.17/Alpine3.24 base digest:
`sha256:5fb4bc53dd0180955e31e5245b648bbb24a4ac4ab03a1de81513642325220bcd`.
See [build, setup and security limits](flaresolverr.md).

## curl security maintenance — 2026-10-26

Both LinuxServer-derived service recipes additionally pin curl/libcurl8.23.0-r0.
The scheduled scan on unchanged source e66c5b8 began reporting48 curl/libcurl
records (two high; package duplicates included) in the qBittorrent image. curl
upstream lists8.23.0 as fixing the affected range, including CVE-2026-92392.
Application versions/upstream digests remain unchanged. Fresh Trivy scans of all4
candidate images report zero findings with the2026-10-26 database, no ignores.
The scan loop now continues after findings to report every image, then fails if
any scan failed. Existing deployments require a separate image update; changing
these recipes does not mutate already running containers.

References: [failed scheduled run](https://github.com/Nerfagol/qbitbot/actions/runs/40329899239),
[curl advisory](https://curl.se/docs/CVE-2026-92392.html).

## Expat, Python and .NET security maintenance — 2026-11-07

The [security run on 0515b13](https://github.com/Nerfagol/qbitbot/actions/runs/42314915135)
passed bot/FlareSolverr scans and browser smoke checks, but reported 16 qBittorrent
OS records and two Jackett .NET records (one each in server/updater manifests).
The workflow itself was correctly enforcing the existing vulnerability gate.

The qBittorrent recipe now additionally pins libexpat2.10.0-r0 and the complete
Python3/pyc package family at3.14.10-r1. A fresh local baseline scan also reported
a zlib record, addressed by the explicit zlib1.4-r0 pin. These are image-build
updates; no package installation or state migration runs at application startup.
The bot's Python3.12 runtime and reviewed Python dependency locks are unchanged.

Jackett's old self-contained .NET9.0.21 runtime cannot be repaired by updating
Alpine's Brotli library. The upstream image is now digest-pinned to Jackett
0.24.3025-ls29, which bundles .NET9.0.22 in the server and updater. See the
[Microsoft advisory](https://github.com/advisories/GHSA-p3jp-9v83-76w9).
The full existing scan gate remains enabled without ignores or severity changes.
Updating these build inputs does not update an existing deployment automatically.

The newer2026-11-07 database additionally flags zlib in the pinned bot base and
Expat/zlib in an existing cached FlareSolverr build. Both bot build stages now
pin zlib1.4-r0; FlareSolverr explicitly pins libexpat2.10.0-r0 and zlib1.4-r0.
These declared inputs also invalidate the affected old cached build layers.

Local verification with checksum-pinned Trivy0.76.1 and database updated
2026-11-07T12:52Z reports zero records in all four rebuilt images, without
suppression. All633 offline tests/checks, disposable API/restart/rollback checks,
fresh EN/RU stacks, outage/bot-only/backup recovery and browser JavaScript/invalid
TLS tests passed. Hosted results for the repair commit must be verified separately.
