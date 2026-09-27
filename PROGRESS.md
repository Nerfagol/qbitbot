# Project Progress

## 2026-09-27 — Public install and recovery acceptance

- Both Compose modes passed from an empty exported checkout with fresh isolated volumes. Both languages exercised real handlers, search/add and download controls. Real qBittorrent/Jackett readiness, outage/recovery and cleanup passed.
- Added online SQLite backup with integrity/hash checks, private permissions and no overwrite; original-public-code rollback retained state and deliberate restore used a new volume.
- Verification: 531 offline tests and full local checks; Compose credential/path checks and fresh+recovery Docker scenarios passed.
- Next: finish CI/documentation/privacy audit, independent review and GitHub publication. No live Telegram acceptance for the public version.

## 2026-09-27 — Bilingual interface verified

- English/Russian menus, search, controls, progress, health cards and setup diagnostics use explicit owner language. Saved preferences survive restart.
- Pending notices retain their original text/buttons after language changes. Watch schema remains v1.
- Verification: 518 offline tests and lint/format/compile/dependency checks; rebuilt image, real isolated API/restart/rollback checks and scoped cleanup passed.
- Next: public Compose fresh-install/recovery verification, documentation/privacy audit and publication. Live Telegram acceptance for this public version has not been performed.

## 2026-09-27 — Public packaging verified

- Added strict settings, safe setup checks, pinned three-service and bot-only Compose files, and EN/RU setup guides.
- Verification: 450 offline tests; lint/format/compile/dependencies; actual Compose parsing and literal-credential delivery; dependency-only startup with blank credentials.
- Real isolated qBittorrent API, restart and rollback checks passed. Test resources were removed. Native Linux Docker CLI worked against Docker Desktop.
- Next: translation catalogs, durable language preferences and complete bilingual UI. No public remote exists yet.

## 2026-09-27 — Public source baseline

- Exported individually reviewed runtime/build/test files into independent history.
- Replaced identifying fixture names and wrote generic public contributor guidance.
- Packaging, bilingual UI and publication remain in progress; follow the release plan.
- Verification: 423 offline tests passed; lint/format, compilation and dependency checks passed.
- Omitted 16 private manual-launcher tests; identity fixtures were extracted as pure generators.
