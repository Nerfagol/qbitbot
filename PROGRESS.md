# Project Progress

## 2026-09-27 — Operator-confirmed live v0.3.0 acceptance

- Operator confirmed live Telegram menus, both languages, search/download controls,
  health-card interaction, completion delivery and normal restart recovery for
  exact release `18e940b` on Linux amd64 NAS.
- Added a public acceptance record and replaced the outdated blanket statement
  that live Telegram acceptance had not occurred. Scope distinguishes operator
  observations, agent checks and automated coverage; crash duplicates and ARM
  limitations remain documented. No private setup data was copied.
- Runtime/tag unchanged. Documentation-only validation: reviewed scope and relative
  links, whitespace checks. Previous release tests remain the runtime evidence.
- Next: apply relevant verification to future changes; no live v0.3.0 test stack
  needs to keep running after acceptance.

## 2026-09-27 — Runtime package and file organization

- Moved all 12 root Python modules into `qbitbot/`; maintenance commands live in
  `qbitbot/cli/`, catalogs in `qbitbot/locales/`. Docker starts `python -m qbitbot`.
- Updated imports, tests, build context, container probes and bilingual CLI guides.
  Added placement rules in `AGENTS.md` and `docs/development/layout.md`.
- Runtime bodies differ only in import paths; CRLF, configuration/state locations,
  schema compatibility and historical rollback-reader coverage are preserved.
- Verification: 543 offline tests; lint/format/compile/dependency checks; Compose,
  real isolated API/restart/rollback, fresh EN/RU stacks, backup/restore and scoped
  cleanup all passed. Independent read-only review found no actionable issues.
- Current state: ready for integration on `refactor/project-layout`; no blockers.
  Next: review/merge the layout change. Existing v0.3.0 tag is unchanged.

## 2026-09-27 — Public v0.3.0 released

- Published [repository](https://github.com/Nerfagol/qbitbot) and [v0.3.0](https://github.com/Nerfagol/qbitbot/releases/tag/v0.3.0). Annotated tag targets `18e940b1db491b7a87874585a65e48930dc9b965`; downloaded GitHub archive matches every audited source file.
- Release-commit CI passed: [539-test/check workflow](https://github.com/Nerfagol/qbitbot/actions/runs/36342508084), [container workflow](https://github.com/Nerfagol/qbitbot/actions/runs/36342508054). Container checks include both languages, both Compose modes, real isolated APIs, outages, restart, backup, rollback and new-volume restore.
- Source/history/private-marker/image-layer/release-archive audits passed; independent review findings were fixed with regressions. No unresolved release blockers or deferred review findings.
- Next: optional real Telegram acceptance with a new dedicated test bot; other CPU architectures remain unverified. No private deployment configuration or history was published.

## 2026-09-27 — Version 0.3.0 prepared

- Published the independently audited source at https://github.com/Nerfagol/qbitbot; remote tree/root history match the public checkout.
- Independent review fixes cover qBittorrent version compatibility, timeout cleanup ownership and saved-language edge cases. All 539 offline tests and affected Docker checks passed; renewed source/history/image audits are clean.
- Initial public CI passed: [check](https://github.com/Nerfagol/qbitbot/actions/runs/36342282037) and [containers](https://github.com/Nerfagol/qbitbot/actions/runs/36342282034).
- Prepared VERSION/CHANGELOG for 0.3.0. Next: require CI on this release commit, then tag and publish https://github.com/Nerfagol/qbitbot/releases/tag/v0.3.0.
- Live Telegram acceptance for the public version remains unperformed; Linux amd64 is the accepted container platform.

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
