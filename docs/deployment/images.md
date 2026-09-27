# Container inputs

Resolved on 2026-09-27 for Linux amd64. These are immutable upstream manifest digests.

| Component | Input |
| --- | --- |
| Python | `python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c` |
| qBittorrent | `lscr.io/linuxserver/qbittorrent@sha256:7034f73a3c6fa4ea40fd67df462939d1665d765231b572523921c98c2db5362e` (5.1.2) |
| Jackett | `lscr.io/linuxserver/jackett@sha256:c10a9a66fe0b2dba71b0b78b38797b0b218bf9d565af7e66c5dfbfa83c6dbe45` |

Both service images contain `/usr/bin/curl`, verified in network-disabled temporary
containers. Readiness checks use that client without credentials. Jackett in-container
updates are disabled. Record full-stack verification separately; image selection is
not evidence that every supported platform has been tested.

Re-resolve and test deliberately before changing these pins. Upstream image/platform
availability does not establish qbitbot support on that platform.
