# Local security hardening implementation plan

Goal: reduce remaining image exposure and enforce least privilege and bounded,
SSRF-resistant HTTP reads; verify offline and on disposable Docker Desktop stacks.
No NAS deployment, real Telegram poller, existing volume/torrent mutations or
secrets are authorized. Preserve watch/state formats and callback control semantics.

1. Container work: choose a pinned supported minimal Python 3.12.15 base, run the
   bot as UID/GID1000 with fresh writable state, read-only application filesystem,
   temporary scratch space, dropped capabilities and no privilege escalation.
   Provide an explicit offline existing-state ownership migration, never startup
   recursive chown. Patch pinned LSIO service packages during derived-image builds.
   Update actual integration resource setup/cleanup and permission regressions.
2. HTTP work: validate URL syntax/length; only the configured Jackett origin may
   reach private network addresses. Resolve and validate DNS inside the connection
   factory, connect to those exact addresses, and retain normal HTTPS verification.
   Manually guard every redirect; disable ambient proxy/netrc credentials. Cap
   decoded torrent/search/capability bodies, close responses and sessions on errors.
   Keep service search/health redirects within their configured origin.
3. Verify: failing-then-passing policy/body/permission regressions, complete check
   suites, Docker Compose, isolated real API/restart/rollback and fresh bilingual
   backup/restore. Scan final images and configuration without suppressions.
4. Review and copy guarded diffs into the public checkout, mirror compatible private
   runtime changes, update memory/progress and a dated report. No push or NAS work.

Ownership: container worker owns Docker/Compose/integration and state-migration
files. Parent owns HTTP module/runtime integration/tests and final reports. Shared
source edits are coordinated and every persistent behavior change is tested.
