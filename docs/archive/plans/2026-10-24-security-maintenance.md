# Security maintenance plan

> Historical record: paths and commands describe their original revision. Use the
> [current guides](../../README.md) for the current source layout.

Scope: update the audited Python dependency pins and Python 3.12 container base;
verify locally with Docker Desktop. No NAS deployment, service restarts, production
credentials or torrent mutations. Existing application behavior/state is preserved.

1. Update both dependency locks, resolve the complete dependency closure and use
   a fresh environment. Keep unaffected direct versions stable.
2. Pin the official Python 3.12.15 base by registry digest; align CI and disposable
   Compose verification. Mirror relevant pins/base into the private repository.
3. Run both offline suites/checks and fresh advisory scans. Run public Compose,
   isolated real API/restart/rollback and fresh stack/backup/restore checks.
4. Scan the built bot and pinned qBittorrent/Jackett images for OS/library CVEs;
   review findings and record limitations rather than claim blanket security.
5. Review the diff, copy verified public changes back, and update handoff records.

Dependency audit failure is the initial regression evidence. Existing behavior
and container checks verify compatibility; no runtime feature code is planned.

Outcome: completed local dependency/base updates and verification. Refreshed the
bundled service pins after scans found extensive old-image advisories. Real
qBittorrent 5.3 API verification required a small HTTP 204 compatibility fix,
proved by failing-then-passing regressions. Image security residuals remain
explicit; downstream image builds, privilege migration and NAS deployment are
not introduced by this change. See the dated deployment/security report.
