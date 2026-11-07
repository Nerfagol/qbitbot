# Project Progress

## 2026-11-07 — Preparing one GHCR package with component tags

- Owner explicitly selected one package with separate containers. Preserve bot
  tags in ghcr.io/nerfagol/qbitbot; companion version/source tags get component
  prefixes. No image rebuild, Git retag, live service restart or tracker query.
- Added a main-only manual consolidation workflow with checksum-pinned regctl,
  exact current CI gate and a public lock copied from the published0.4.0 digest
  asset. Copy rejects conflicting tags, preserves equal ones and verifies copied
  digests. Future publishing preflights all8 tags in the single canonical package.
- Optional legacy cleanup remains unauthorized and undispatched. Its owner-only
  path verifies every canonical tag and all legacy versions against copied
  manifest graphs/known tags before deleting only the3 named companion packages.
  Ask explicit owner approval after migration because old pull URLs will break.
- Verified675 tests/normal checks,29 focused registry regressions, actionlint and
  resolved Compose equivalence/context exclusions. Independent review found no
  blockers. Read-only regctl verified all4 original root digests/raw manifest
  graphs. No scanner exclusions or runtime changes were introduced.
- Publication is phased: push migration/publisher code first, wait for hosted
  checks, run default copy, verify anonymous/QNAP access, then publish new overlays
  and current guides. The2 overlay files and compose_check assertion are held
  locally until aliases exist; primary owns these edits, no other writers.

## 2026-11-07 — Removed the CodeQL integration credential-to-file flow

- Owner requested a source fix for CodeQL#1. Replaced the generated credential
  write in public_stack.py with explicit child-process environment injection.
  Bundled test Compose and bot-only overrides interpolate dedicated fixture names;
  generated files contain only placeholders and the retained0600 bot.env is empty.
  No global environment mutation or production configuration import was added.
- A regression first failed on the plaintext password persisted in bot.env, then
  passed with the source fix. It verifies file contents, child env delivery and
  secret-free Docker argv. Retained the empty file's0600 protection after a
  separate red/green check. Independent review found no blockers;11 focused tests
  and the final full660 tests/lint/format/compile/dependency checks passed.
- Real disposable public-stack acceptance passed both languages, authenticated
  services, bot-only mode, outage/recovery, state/rollback/backup and scoped cleanup.
  These checks use only owned fixtures and generate no real tracker traffic.
- Published source4966021. Hosted CodeQL run42412642819 succeeded; GitHub marks
  alert#1 fixed at2026-11-07T20:47:04Z and reports0 open alerts on main, with no
  replacement finding. No dismissal or scanner-rule change was made; the earlier
  administrative approval request is obsolete. Published0.4.0 images and the live
  QNAP deployment need no runtime update.

## 2026-11-07 — Published GHCR0.4.0 and verified QNAP registry rollout

- Published exact sourcee342894, new immutablev0.4.0 and public release with a
  digest-manifest asset. All4 main-commit workflows passed, along with tag checks.
  Publisher's first attempt failed before upload on the known intermittent
  Chrome-not-reachable browser startup; one failed-job rerun passed every gate
  unchanged and uploaded all4 amd64 images. No root-cause browser fix is claimed.
- Confirmed all4 public manifests anonymously, hashing them against the exact
  successful upload digests. The images were already public: no owner visibility
  change was required. Keep visibility guidance conditional on actual state.
- Pulled all4 images on QNAP using an empty registry config. Verified manifest/
  config digests, OCI source/version labels and Linux amd64; bot wheel0.4.0/UID,
  qBit5.3.0, Jackett runtime files and Chromium version probes passed. All24 bot
  source/catalog hashes match the release. Private probe shell/path assumptions
  were corrected without service changes; these were not image/runtime defects.
- Switched only the bot to its public digest-pinned image with a fresh verified
  offline backup. State schema/counts and configuration bytes were retained;
  source hashes, running image, UID/read-only state mount and clean startup were
  verified. qBit/Jackett/solver container IDs and start times stayed unchanged,
  so this rollout caused no additional tracker warm-up or real search requests.
- Open CodeQL#1 flags only generated credentials written for isolated disposable
  integration services. Independent review traced the private temporary directory,
  0600 env file, fresh volumes/internal network and synthetic Telegram token;
  production config is not imported. Automatic approval review rejected changing
  this high-rated alert's security state without explicit user authorization.
  Approval was requested asynchronously; alert remains open, no rules weakened.
- Updated public registry/setup/release records to actual publication and QNAP
  evidence. Real Telegram/search acceptance and formal test-alert dismissal remain
  separate; private snapshots/descriptors/logs/helpers stay outside Git.

## 2026-11-07 — Prepared GHCR release0.4.0 for publication

- Owner explicitly authorized the proposed workflow/version/changelog/publication
  and QNAP pull test. Selected0.4.0 for accumulated changes; existingv0.3.0 is
  unchanged. No new runtime features, periodic tracker requests or state migrations.
- Added tag-only publication with exact main-commit check/containers/security/
  codeql gate, aligned package/changelog/tag validation and existing-version-tag
  refusal. Only the upload job receives packages:write via ephemeral GITHUB_TOKEN.
  Four amd64 images get version/source tags and OCI metadata; exact built images
  undergo synthetic startup/browser tests and vulnerability/secret scans first.
- Registry overlays remove builds while preserving all deployment settings;
  resolved-config equivalence across0.4.0/0.4.1 passed. Added setup/registry guides,
  version/changelog and third-party redistribution/source notices without changing
  existing Compose defaults or project/state identities. Host jq remains required.
- Verification:659 tests/lint/format/compile/dependency checks, make compose-check,
  make integration, make integration-public, wheel0.4.0 and candidate native-s6/
  real-dashboard-auth/browser-JS/TLS fixtures passed. All4 candidate Trivy scans
  found0 vulnerabilities/secrets. Independent workflow review found no blockers.
- Redacted source/history/staged Gitleaks and private-identifier comparison over
  public Git/source and17171 regular files/blobs across43 unique layers passed.
  Layer Gitleaks's5 findings were4 upstream public signing fingerprints and an
  official Alpine libmagic header database. Independent equality review cleared
  exact anchored artifact-only exceptions; final layer scan passed. Repository
  source-scanner rules remain unchanged. No raw findings/private data enter Git.
- Next: publish reviewed source, wait for exact-commit hosted checks, create new
  version tag and verify real GHCR upload/API behavior. New personal GHCR packages
  default private; official GitHub docs provide only an owner UI visibility change.
  Complete all available work before requesting that one-time external action;
  anonymous public/QNAP pulls and GitHub release publication remain pending.
- Sourcee342894 was pushed and all4 exact main-commit workflows passed. Created
  new annotatedv0.4.0 at that commit and a draft GitHub release;v0.3.0 unchanged.
  Downloaded GitHub tag archive matches every tracked file. First publish attempt
  stopped before scans/upload because the existing solver browser test hit the
  known intermittent Chrome-not-reachable startup failure. Main/tag security and
  local browser checks passed on the same source. One failed-job rerun is active;
  no source change, relaxed check or production retry loop was introduced.
- Private anonymous-registry manifest/digest verification, QNAP pull/probe and
  backed-up bot-only registry rollout helpers are prepared outside Git. Current
  NAS services are unchanged. Public visibility/anonymous pulls and final release
  publication remain pending; do not treat the draft/tag as a completed release.

## 2026-11-07 — Corrected warm-up API authorization after NAS acceptance

- The first warm-up source1538285 passed all4 hosted workflows, but real NAS
  acceptance showed management Test/list returns302 with a dashboard password
  despite the API key. No tracker warm-up tests were scheduled. The synthetic
  HTTP fixture had incorrectly assumed API-key access to management routes.
- Keep dashboard authentication unchanged: replaced that approach with one empty
  search across configured sources using the same API-key manual-search endpoint
  as the bot. One request per container boot,110s max wait, no helper retries or
  periodic traffic. Normal user searches still retain complete-source behavior.
- Three revised regressions failed against the old route, then9 helper tests
  passed. Native s6 fixture now rejects management requests and counts aggregate
  searches per boot; added a real Jackett fixture with synthetic admin password
  in network-none, verifying management stays302 and warm-up finishes0sources.
  Corrected Docker fixture and645 tests/lint/format/compile/dependency checks
  passed; independent review found no blockers. Fresh disposable EN/RU stack,
  authenticated APIs, outage/recovery and bot-only checks passed. Corrected image
  scan found0 records with the current dated database.
- First private rollout backup guard failed before image change because root
  with cap-drop ALL could not read owner-only Jackett configuration. Services
  resumed safely; a fresh backup attempt using its verified existing owner
  succeeded without chmod/chown. The deployed first image is healthy but its
  skipped warm-up did not establish successful warming.
- Published corrected5644275; all4 hosted workflows passed. Deployed only the
  Jackett image after verifying transfer/config/layer/source identities and a
  fresh offline SQLite/config backup. Existing image, state volume and security
  restrictions of the bot were retained; solver container identity was unchanged.
  Normal readiness and private state-integrity/count comparisons passed.
- Actual startup warm-up ran exactly once, completed in36.805s and reported both
  configured sources. Bot started after completion; no startup/polling-conflict
  error markers were found. No extra real tracker searches were used to verify
  it. No periodic warm-up or helper retries were added. User acceptance of a
  later real search remains separate; cookie expiry can still cause a cold run.
- Sanitized handoff/plan records capture the completed deployment; runtime source
  is published. Private descriptors, snapshots, logs and rollout helpers remain
  on NAS or under /tmp. GHCR remains deferred until owner acceptance.

## 2026-11-07 — Verified restart-only Jackett tracker warm-up

- Owner selected restart-only warm-up, explicitly rejecting periodic requests;
  complete-source search behavior remains unchanged. Added a native s6 oneshot
  to the derived Jackett image, enabled by bundled Compose and opt-in elsewhere.
- After service readiness it uses the existing local API key privately, lists
  configured indexers and invokes Test once each within a bounded budget. No
  helper retries, periodic polling or bot-startup trigger. Health gates on this
  boot's completion, including failures, then probes only the local Dashboard.
  Internal process restarts do not rerun the container hook. Test can itself
  involve several tracker HTTP requests; expiry can still cause a cold search.
- Eight regressions first failed for missing implementation; nine offline helper
  tests now pass, including failures, malformed IDs, secret suppression, stale
  completion and total budget. Full make check645 passed. Context exclusion,
  actionlint, redacted Gitleaks and full disposable public-stack API/EN-RU/
  outage/restart/rollback/backup acceptance passed. Jackett scan found0 records.
- Synthetic native-s6 integration used real curl/jq with network-disabled HTTP;
  verified health waits, one Test each including500, no idle/retry traffic and
  exactly one additional run after container restart. Added this check to CI.
  Independent review found no blockers after documenting host jq prerequisite.
- NAS deployment and hosted checks remain pending for this source change. No
  real tracker query was used to validate the helper. Private deployment evidence
  stays outside Git; GHCR remains deferred until acceptance.

## 2026-11-07 — Corrected silent health-card reopening during NAS acceptance

- Owner reports health appears ignored and a roughly30s search. Runtime logs
  had no handler/startup errors; persisted HealthManager.open edited the saved
  old message and returned without a current acknowledgement. Added localized
  EN/RU reply pointing to the same card without replacing its token/pin/hourly
  subscription. Unauthorized users still receive no response or edit.
- Three regression failures became green. Review found the initial legacy reply
  arguments fail real PTB21.11.1 validation despite passing the simple fake.
  Added a real Bot/Message/BaseRequest offline regression, observed the exact
  ValueError RED, switched to explicit ReplyParameters and verified GREEN.
- Final make check636 passed (25 health tests;53 focused health/locale tests),
  with lint/format/compile/dependency checks. Independent review found no remaining
  blockers. Source handler CRLF and runtime dependency pins are untouched.
- Private persisted history confirms the reported upstream search took30.334s;
  an older run was493ms. Repeat cache result took50ms HTTP; a fresh variation
  took564ms, with individual sources232/533ms and complete coverage. Same manual
  search endpoint existed before client extraction. Root cause of the individual
  slow upstream run remains unknown; no search-speed fix is claimed.
- Owner explicitly selected waiting for complete source coverage. No indexer,
  timeout, source-completeness policy or search request code changed. Real query
  history/results/credentials remain under private /tmp evidence, never fixtures.
- Published16599fc; all4 hosted workflows passed. Rebuilt/scanned/transferred
  only the bot, verified its archive/config/layer and installed-source/catalog
  hashes, and deployed it with a fresh verified offline backup and retained
  durable card identities. Three service containers were not restarted/replaced.
- Post-update native Telegram/menu checks, SQLite integrity, service readiness
  and startup/polling-conflict log checks passed. Owner must retry `/health` in
  Telegram; GHCR implementation remains deferred. Private artifacts remain
  outside the public checkout.

## 2026-11-07 — Deployed verified candidate to QNAP for acceptance

- Owner explicitly authorized latest-version NAS rollout/testing before GHCR.
  Deployed public9307ad8 to Linux amd64 using4 exact candidate images with
  revision labels. No source/runtime code change or registry publication.
- Scan gate passed for all4; transferred archive checksum, exported config/layer
  digests and installed Python/catalog hashes verified. Preserved existing
  private descriptors except image tags, all storage/network/project identity,
  credentials, resource/security settings and retained previous images.
- Offline bot SQLite snapshots and service-configuration backups verified before
  switching. Candidate read identical schemas/row counts; all existing torrent
  identities remained present. No test torrent was added/paused/deleted.
- Automated NAS checks passed: authenticated qBit/Jackett/state readiness, service
  health, all3 DB integrity checks, Telegram identity and EN/RU command menus,
  no webhook, controlled bot restart and no startup/polling-conflict log errors.
- Two preliminary attempts safely resumed original images before replacement:
  a post-stop container-list lag tripped the strict backup guard; then a helper
  snapshot-copy path typo was corrected with an explicit path-equality assertion.
  Final attempt used a fresh backup destination and completed successfully.
- Private scripts/configuration/snapshots/logs/reports stay on NAS and under
  /tmp/qbitbot-qnap-20261107; none are imported into the public checkout. Only
  sanitized agent handoff notes changed locally and remain uncommitted.
- Next: owner tests real Telegram search/download/completion behavior and confirms
  acceptance before GHCR implementation. Automated checks are not full live
  acceptance; hourly delivery and real completion observation remain pending.

## 2026-11-07 — Validated and merged Dependabot action updates

- Owner authorized enabling required security settings, refreshing/testing and
  merging PRs2/3/4, then deleting their merged branches. Enabled vulnerability
  alerts/Dependency graph; SBOM returned11 packages and PR dependency review passed.
- Verified official tag/commit correspondence for dependency-review5.0.0,
  setup-python7.1.0 and checkout7.0.1. Preserved full pins, read-only defaults,
  disabled persisted checkout credentials and the existing Python/image gates.
  Corrected PR2's stale version comment through CLI because the connector lacks
  workflow write/merge/rerun permission; no additional permissions were granted.
- Refreshed each PR with current main, required every current check to pass and
  merged sequentially with exact-head checks: PR2 eebcdd7, PR3 aac6085, PR4 656b3e4.
  All3 merged branches are removed. Main passed all4 workflows after PR2 and PR3.
- PR2's push smoke run exited when Chrome could not be reached, while the same
  head's independent PR smoke/scan passed. Preserved diagnostics, reran only that
  failed job once and confirmed success. Root cause remains unproven; no fixture
  readiness, TLS, scanner or severity rule was relaxed.
- Final main656b3e4 passed check, CodeQL, security and containers workflows
  (security42397641144, containers42397641172). Local actionlint passed. The local
  release-polish commit was rebased onto main as cd53dde and remains unpushed;
  no Docker publication or production operation occurred. This maintenance record
  remains local with the polish; publishing those docs and GHCR work are separate.

## 2026-11-07 — Polished release documentation

- Owner requested repository release polish before GHCR work. Added four main
  workflow badges and a source-build quick start; setup-check failure prevents
  the quick-start bot launch. Updated security coverage and current image links.
- Added matching EN/RU upgrade commands for bundled and bot-only installations,
  preserving Compose project/volume identity, backups, ownership migration and
  retained-state recovery. Registry images remain explicitly unavailable.
- Updated Unreleased notes for CI/image security repairs and corrected current
  source-layout/Jackett wording. Release checklist keeps version selection, package
  metadata/tag alignment and registry validation as deliberate release steps.
- Prior repair92e0e79 was pushed to main and all4 hosted workflows passed;
  security run42391488811 and containers42391488813 confirmed the repair.
- Documentation validation:51 local Markdown targets and21 shell examples passed;
  all4 badge workflow files exist and git diff --check passed. No runtime changes,
  version bump, tag, registry publication or deployment. Owner authorized committing
  this polish; pushing it and implementing/testing the GHCR workflow remain next.

## 2026-11-07 — Repaired image vulnerability failures

- The owner requested repair of security run42314915135 on0515b13. CodeQL,
  check, containers, secrets and Python dependency audit passed; the image gate
  correctly found16 qBit Expat/Python records and2 Jackett .NET records. Solver
  startup/browser smoke passed; no timeout/scanner relaxation was appropriate.
- Preserved qBittorrent5.3.0; image-build patches pin Expat2.10.0-r0,
  Python3/pyc family3.14.10-r1 and zlib1.4-r0. Alpine removed Python r0 from its
  index, so the first candidate build established the available fixed r1 revision.
- Resolved/pulled immutable upstream Jackett f235901dce0b… (0.24.3025-ls29),
  confirmed patched.NET9.0.22 in server/updater manifests. Updating Alpine Brotli
  alone cannot patch the old self-contained.NET runtime. Exact pin in images.md.
- Fresh baseline scan reproduced17 qBit findings with an additional zlib record.
  New DB/cached-build scans also found bot zlib and solver Expat/zlib, repaired
  through explicit pins in both bot stages and the solver build layer.
- Final verification: all4 rebuilt image scans0 with Trivy0.76.1 DB updated
  2026-11-07T12:52Z; make check633 passed; actual API/controls/restart/rollback,
  fresh EN/RU/bot-only/outage/backup/recovery and solver JS/invalid-TLS passed.
  Independent review found no remaining code blockers. Staged secret scan clean.
- Runtime Python locks, UID/capabilities/TLS/state constraints and all-severity
  security gate unchanged. No existing services, private state or NAS rollout.
- Commit/push is authorized under the ongoing CI repair; next verify hosted
  workflows on the exact repair commit. Docker publishing remains a later phase.
  Private diagnostic/build/scan output stays under /tmp/qbitbot-security-fix-20261107.

## 2026-11-06 — Added CI security checks before Docker publication

- Owner selected security improvements first and clarified that later packaging
  means a Docker image. Added independent Gitleaks/dependency-review jobs without
  changing the existing complete-lock audit or image build/smoke/scan gate.
- Gitleaks8.30.1 uses the existing reviewed checksum/config, full public history
  and tracked-source export, fully redacted output and no finding artifacts.
  The export scan runs after history findings; either failure fails the job.
- Added commit-pinned CodeQL4 Python/security-extended and dependency-review4
  (low+ vulnerabilities/all scopes, no license policy or PR comments), plus weekly
  Actions-only Dependabot. Existing runtime/build/development pins unchanged.
- Independent review found the Dependabot push-token/SARIF failure: verified
  against official GitHub docs and excluded dependabot/** push branches while
  retaining PR coverage. No other review blockers reported.
- Verification: make check633 passed, Ruff/format/compile/pip check passed;
  checksum-verified actionlint1.7.12 passed; Gitleaks scanned all28 public commits
  and the candidate tracked-source export with no findings. Synthetic current-file
  and deleted-history secrets each failed with exit1 and redacted output; the
  clean synthetic export passed. Fixtures/tools stayed under /tmp.
- Local changes only; no commit/push, hosted CodeQL/dependency review, repository
  settings changes, Docker publication or production operations. Next: publish
  reviewed workflows, confirm actual hosted runs/graph/advanced CodeQL settings,
  then configure merge protection. Docker registry/release work follows separately.

## 2026-10-26 — Exposed a separate solver CI startup failure

- curl remediation b7e0c7a was published; code/containers passed, but security
  run40335400018 timed out waiting for Chromium initialization before scanning.
  Original harness suppressed startup logs and removed fixtures on failure.
- Added fixture readiness, exited-process detection and URL-scrubbed startup/
  cgroup/OOM diagnostics before scoped cleanup. Two offline regressions verify
  redaction, original-error preservation and cleanup even when diagnostics time out.
- Scanner loop now runs after smoke failure, while either smoke/scan failure
  still fails the job. Synthetic four-way gate checks and local browser JS/TLS
  passed; full633 tests/checks passed. No readiness deadline/security relaxation.
- Confirmed shipped3.5.2 startup reads browser user-agent without navigation;
  README TEST_URL is stale and unused. No ineffective URL override was committed.
  Exact CI startup cause needs diagnostic rerun; do not claim it was network access.
- Public CI follow-up only; no images/dependencies/NAS services changed here.

## 2026-10-26 — Fixed scheduled curl image security findings

- User reported failed security CI. Run40329899239 failed in qBit image scanning,
  while Python audit passed; unchanged e66c5b8 had passed2026-10-24. Updated feed
  reported48 curl/libcurl records (two high), installed8.22.0-r0/fixed8.23.0-r0.
- Added exact curl/libcurl8.23.0-r0 build patches to both service Dockerfiles;
  retained application/upstream digest pins. No scanner ignores or relaxed gates.
  CI now labels/scans all4 images and aggregates failures instead of stopping at
  the first finding. Synthetic all-pass/failure shell checks verify both outcomes.
- Verification:631 tests/checks; updated DB/all4 images0 findings; actual qBit API/
  thread/control/restart/rollback and fresh solver JS/selfsigned-TLS checks passed.
  Fresh EN/RU/bot-only/history/outage/backup/recovery passed. Exact-commit GitHub
  CI is checked after publishing the fix.
- Private reports/build logs under /tmp/qbitbot-security-20261026. Public docs
  record dated evidence. Commit/push fixes the public CI; no NAS/production poller,
  existing torrents/state, credentials or application version changes authorized.

## 2026-10-24 — Published checkpoints; extracted clients and explicit startup

- User authorized all proposed next steps. Pushed e9413e9/071c192; check, security
  and containers workflows all passed on071c192. No release tags/NAS changes.
- Added independently configured qBit/Jackett clients and shared SearchResults;
  moved env loading/application wiring/polling to startup. Handler import is inert
  and default access denies until explicit validated configuration. Existing module
  commands, callback order/sequential control/background jobs and state preserved.
- Six RED boundary tests became GREEN. Targeted protocols moved their mocks to
  clients, without weakening assertions. Preserved TTL/relogin, 200/204 handling,
  Host/auth/redirect/HTTP/body/privacy protections, hash controls and coverage data.
- Package/source/context manifests include client code and reject private files.
  Runtime locks unchanged and app.py remains CRLF; handler length1220→929 lines.
- Verification:631 full tests/checks, wheel/sdist/installed resources, actual Compose
  and context canaries, API/thread/search/add/control/restart/rollback, fresh EN/RU/
  bot-only/history/outage/backup/restore, scoped cleanup. Runtime Trivy0 findings.
- Real fixtures exposed old global URL test seams. Updated both client search URL
  and matching trusted metadata origin; protections were retained. Independent
  review found no code blockers. Secret/source checks before publication required.
- Task authorization covers committing/pushing this verified refactor and checking
  all3 workflows on its exact commit; Git/Actions remain publication truth. No
  production token/poller, existing torrent/state mutation or NAS operation.

## 2026-10-24 — Committed phase1 and verified installable src package

- User requested the phase1 checkpoint and packaging next. Committed reviewed
  layout as e9413e9 (not pushed), then moved runtime into src/qbitbot and added
  standard metadata/explicit package+locale selection with build-only setuptools.
- pyproject owns unchanged version0.3.0 and reviewed direct requirements; removed
  duplicate VERSION. Runtime closure unchanged; backend pin matches build/dev locks.
  Module commands remain; local development now installs editable source.
- Artifact tests first failed on missing metadata, then verified wheel/sdist
  rebuild/runtime payload, metadata/license/catalog inclusion, private canary
  exclusion and regular installed import outside checkout. Dependency-name check
  normalizes equivalent underscore/hyphen forms. Full625 checks passed.
- Docker now builds a wheel in a separate stage and installs it with runtime pins;
  installed-image probes prove catalogs/version, absent pip/backend and unchanged
  UID1000/read-only/caps/NNP/resource restrictions. Probes use installed imports;
  historical reader/source-rollback fixtures keep their intentional overrides.
- Verified actual filtered context, real API/thread/search/add/controls/restart/
  rollback, fresh EN/RU/bot-only/outage/backup/restore and scoped cleanup. Fresh
  runtime Trivy and updated dev/build pip-audit:zero records/no ignores. Independent
  code review found no blockers. Docs and source/lock integrity checks passed.
- Packaging changes staged only for source-export checks, uncommitted/unpushed.
  No NAS/production operation, Telegram token/poller or existing torrent changes.
  Next separate task: client extraction; no implicit runtime architecture rewrite.

## 2026-10-24 — Applied deployment/documentation layout consolidation

- Owner approved the first structure-review phase. Reduced visible root files15→8:
  all image inputs now deploy/docker/, optional Compose variants deploy/, public
  template config/, unchanged locks requirements/, notices docs/licenses/; agent
  notes under development/agent and historical evidence under docs/archive/.
- Updated Compose, image COPY/context allowlist, CI, integration exporters/tests,
  EN/RU setup, docs index/archive navigation and current release instructions.
  Bot-only commands explicitly use --project-directory .; no project-name override
  was added. All3 full resolved Compose configs match their old runtime semantics
  except intended Dockerfile paths; default and custom project/volume names match.
- Application Python and lock bytes unchanged; only two localized diagnostics now
  point to config/bot.env.example. No package-manager/src/client refactor here.
- Verification:621 tests plus lint/format/compile/dependency checks, merged Compose,
  real API/thread/search/add/control/restart/rollback and state-permission checks,
  fresh EN/RU/bot-only/outage/backup/restore, solver JS and invalid-TLS rejection.
  Disposable resources cleaned; only synthetic fixtures and owned Docker volumes.
- Independent review caught a generated rollback Dockerfile path regression;
  failure reproduced, fixed and full suite rerun passed. Windows-path normalization
  in a new Compose assertion also fixed. Follow-up review found no blockers.
- Actual directory-context canaries exposed parent-directory exceptions admitting
  private descendants. Added explicit child exclusions and a permanent generated
  canary to compose-check (stdin tar contexts bypass client ignore processing).
  Corrected real directory proof passed; fresh public stacks reverified the filter.
- Current documentation links and Docker-context canary checks verified. Runtime
  dependencies did not change; dated security audit remains the prior scan evidence.
  Staged for source-export verification only; no commit/push or NAS operation.
- Next independent phase, if requested: installed-package/src and client boundaries.

## 2026-10-24 — Reviewed complete public repository structure

- Reviewed tracked root/application/tests/integration/deployment/CI/docs and current
  PyPA/Docker guidance. Report: docs/archive/reviews/structure-2026-10-24.md. Current flat
  Docker-first structure is valid, but deployment ownership is inconsistent and
  checkout-based tests do not verify an installed distribution. app.py combines
  clients/parsing/handlers with import-time configuration; release guidance is stale.
- Recommended deployment/docs consolidation first (15 visible root files toward8),
  then separately approved src/package/client refactoring. Preserve Compose paths,
  project/volume identities, build allowlists and historical rollback fixtures.
- Report is advisory; no runtime/layout/deployment change implemented. Confirmed
  earlier security commit2cfd466 and README4fab35c were pushed in this session;
  GitHub CI results remain unverified here. Only documentation checks required.

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
  explicit in docs/archive/security/security-2026-10-24.md, without ignore rules.
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
