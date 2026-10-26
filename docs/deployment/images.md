# Container inputs

Resolved on 2026-10-24 for Linux amd64. These are immutable upstream manifest digests.

| Component | Input |
| --- | --- |
| Python | `python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d` |
| qBittorrent | `lscr.io/linuxserver/qbittorrent@sha256:e887804fa9de4c60f5f0fb1f3a7e4febe40a8f69fe736f70c4e8589b1f868dab` (5.3.0) |
| Jackett | `lscr.io/linuxserver/jackett@sha256:d1b82a9c5bbaea44284a550af739bd838749b72f15b10ef61b6c9d9d1b2f1ed7` |

Both service images contain `/usr/bin/curl`, verified in network-disabled temporary
containers. Readiness checks use that client without credentials. Jackett in-container
updates are disabled. Record full-stack verification separately; image selection is
not evidence that every supported platform has been tested.

Re-resolve and test deliberately before changing these pins. Upstream image/platform
availability does not establish qbitbot support on that platform.

Compose builds the service inputs through `deploy/docker/qbittorrent.Dockerfile` and
`deploy/docker/jackett.Dockerfile`. These derived images pin Brotli libraries 1.2.1-r0 and
musl/musl-utils 1.2.6-r3 at build time; the application versions remain unchanged.
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
