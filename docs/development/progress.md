# Project Progress

## 2026-10-24 — Prepared authorized local security/cleanup commit

- Owner requested committing the public changes. Reviewed and staged dependency,
  HTTP/container hardening, optional FlareSolverr, verification/CI and root cleanup.
- Fresh make check:621 tests plus lint/format/compile/dependency checks passed;
  staged and complete-source secret scans report no findings. Prior Docker/API,
  recovery, Compose and browser/TLS/image-scan evidence is retained in dated docs.
- Local commit only; pushing/publishing remains pending. No NAS operations or
  tokens used in this commit preparation; existing release tags remain unchanged.

## 2026-10-24 — Reduced root documentation/configuration clutter

- Confirmed origin is the intended public GitHub repository. Moved agent memory
  and handoffs into docs/development/, updated contributor paths, and consolidated
  identical pytest settings into pyproject.toml. Removed three root files without
  changing runtime, dependencies, Compose commands or state layout.
- Verification: full make check after moving pytest configuration. Existing local
  security work preserved; no commit/push, service operation or token use.

## 2026-10-24 — Public packaging of optional hardened FlareSolverr

- Preserved prior dependency/runtime hardening and added a digest-pinned official
  FlareSolverr3.5.2 source build on Python3.11.17/Alpine3.24, matching browser/driver,
  CA/urllib3 fixes, asserted strict-TLS/error-page patches and upstream MIT notice.
- Optional bundled-stack overlay isolates unauthenticated API to Jackett-only
  network with no host port; nonroot/read-only/caps/NNP/resources match tested
  constraints. Generic EN/RU guide links document setup and no-sandbox limitation.
- Recurring security CI builds/scans the optional fourth image and runs generated
  internal-network JavaScript/TLS smoke. Compose verifier checks merged isolation.
- Verification:621 tests, lint/format/compile/dependency checks; actual public build
  and Dockerignore inputs; merged base/bot-only/solver Compose; real Chromium JS
  and selfsigned-TLS rejection/owned-resource cleanup; fresh Trivy zero findings.
- Updated stale dependency attribution versions and superseded changelog link.
  Work remains local/uncommitted/unpublished; CI has not run on GitHub. No private
  configuration, accounts, logs/history, NAS operations or live pollers imported.

## 2026-10-24 — Existing-service Host header compatibility

- Actual authorized NAS checks found a published-host route unavailable from a
  Docker bridge, while the direct service route required the existing Web UI Host
  allowlist. Added optional validated QBIT_HOST_HEADER to runtime/setup without
  disabling authentication, redirects, CSRF, Host or HTTPS certificate checks.
- 12 regression cases reproduced missing/injection handling, then passed; full
  offline/lint/format/compile/dependency checks:621 passed. Updated env example and
  EN/RU setup notes with generic existing-service guidance, without private values.
- The deployed Linux-amd64 candidate passed real API readiness, source/image
  checks, native EN/RU menus, controlled restart and private SQLite integrity/
  backup checks. Application/library storage was preserved. Indexer setup and
  real download/hourly observations remain operator acceptance tasks.
- Source remains uncommitted/unpublished; existing public release tags unchanged.
  Private deployment configuration, credentials and logs are not imported here.

## 2026-10-24 — Hardened local public candidate and verified recovery

- Replaced the bot's Debian base with pinned Python3.12.15/Alpine3.24; added
  UID/GID1000, read-only application storage, tmpfs, no capabilities/escalation and
  resource limits. Added explicit offline state migration with byte preservation
  and link/special-file rejection; existing volumes are never chowned on startup.
- Derived reviewed qBit/Jackett images patch pinned Brotli/musl at build time.
  Added DNS-pinned metadata transport, exact Jackett private-origin exception,
  redirect/downgrade rules, decoded response caps and disabled ambient credentials.
  Reviews found IPv6/NAT64/manual-redirect edges; regressions failed then passed.
- Verified 609 tests/checks and all609 under non-root/read-only/network-disabled
  Alpine. Compose, real API/add/control, migration, outage/restart/rollback,
  fresh EN/RU stacks, preferences/watch/health state and backup/restore passed.
  Read-only fixture transfer uses exec stdin; scoped resource cleanup passed.
- Trivy image scans: zero OS/language vulnerability records in all3 images with
  current DB; no suppressions. Service root init and missing Dockerfile liveness
  checks remain explicit config notes, and per-read timeouts are not total deadlines.
- Added checksum-pinned weekly/on-change security CI (local only, not yet run on
  GitHub). Durable scope/migration/limitations are in the dated hardening report.
- Next: review/commit/publish locally verified work when requested; NAS rollout
  remains a separate task with state backup/migration. No NAS services, live tokens,
  existing state/torrents or real Telegram pollers were used or changed.

## 2026-10-24 — Local security updates and Docker Desktop verification

- Updated runtime/dev locks, resolved the complete closure, pinned Python 3.12.15
  and aligned CI/Compose probes. Build-only pip is updated then removed from the
  runtime image to exclude its vulnerable vendored libraries.
- Refreshed bundled service digests to qBittorrent 5.3.0 / Jackett v0.24.2900.
  Real container checks exposed HTTP 204 success responses; four failing
  regressions reproduced login/add/setup failures, then passed after the minimal
  compatibility fix. Legacy success/rejection behavior and CRLF were preserved.
- Verification: 556 offline tests/checks passed locally and all 556 also passed
  in the exact Python 3.12.15 image without network/root access. Compose checks,
  real isolated API/restart/rollback, fresh EN/RU stacks, backup/restore and
  scoped cleanup passed. Fresh pip-audit reports no dependency advisories.
- Trivy image/config scans completed. Bot Python findings are zero. Debian OS
  findings have no fixed version in the feed; both latest service images still
  carry fixable Brotli/musl findings. Root runtime remains flagged. Findings are
  explicit in docs/deployment/security-2026-10-24.md, without ignore rules.
- Next: obtain patched upstream service images or deliberately maintain derived
  images, address/review the remaining OS and runtime-privilege findings, then
  rerun relevant checks before security sign-off. No NAS deployment, live Telegram
  poller, production credential/state use or existing torrent changes occurred.

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
