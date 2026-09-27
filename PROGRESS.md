# Project Progress

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
