# Public qbitbot release design

Date: 2026-09-27
Status: proposed design; implementation has not started.
Target: version 0.3, after verification; this document does not declare a release.

## Purpose and agreed scope

Make the existing Telegram torrent manager installable by other self-hosters,
with a bot, qBittorrent and Jackett stack and complete English/Russian bot UI.
The user explicitly requires a separate local folder and a new GitHub repository
so public development cannot carry private deployment data or Git history.

Preserve search, filtering, release previews, numbered selection, download
controls, completion notices, restart recovery and hourly health cards.
Direct Telegram torrent-file uploads and media-app links remain out of scope.
Existing private deployments and their accepted version are independent of this work.

## Repository separation and publication

- Start a new independent repository in a sibling folder, provisionally named
  `qbitbot-public`; the GitHub project name is `qbitbot`.
- Do not clone, fork, create a worktree from, add a remote to, or push the private
  repository. The new repository must have its own Git directory and fresh history.
- Export only explicitly reviewed tracked runtime modules, dependency locks,
  build inputs, synthetic tests and generic test helpers. Inventory each exported
  path. Inspect content even when the file is tracked or tests call it synthetic.
- Rewrite public documentation and agent guidance for generic installations.
  Do not copy private README, agent memory, handoff logs, inspection/deployment
  reports, release manifests, environment files, state, archives or verification
  artifacts. Do not copy the private integration launcher's local configuration.
- Exclude tokens, API keys, user/chat IDs, personal bot names, hostnames, addresses,
  personal storage paths, real torrent data and saved Telegram payloads from public
  files, fixtures, screenshots, Git history, CI output and image layers.
- Before the first upload, scan the entire new history and staged export for
  secrets and private identifiers; manually review findings and the file inventory.
  Repeat the checks against release artifacts. Synthetic credentials need explicit,
  narrowly scoped scanner exceptions rather than broad exclusions.
- Create the GitHub repository and upload only after this publication check passes.
  Publication is authorized by the user; no private snapshot is uploaded as staging.
- Resolve original-source provenance and redistribution permissions before choosing
  a project license or publishing code. No license is inferred from possession.
  Preserve required notices and inventory third-party dependencies/images.

## Architecture and packaging

Use one Docker Compose project with three independently persistent services:
`bot`, `qbittorrent` and `jackett`. This is one managed application stack with
separate containers. Bot-only installation against existing services is a second,
documented Compose entry point; avoid starting unused bundled services in that mode.

- Communicate through Compose service DNS names. Support configurable endpoints
  for existing services. Do not use host networking or personal NAS defaults.
- Persist bot state, qBittorrent configuration and Jackett configuration separately.
  Downloads use a user-selected host directory mounted into qBittorrent. The bot
  uses qBittorrent's container path and does not need the downloaded files mounted.
- Use explicit, tested upstream image versions/digests. Establish supported CPU
  architectures by building/testing them; the first verification target is Linux
  amd64. Do not advertise unverified ARM or NAS platform support.
- Make service web interfaces loopback-only by default; document an explicit LAN
  binding option for headless hosts. Configure peer ports separately. Enable outbound
  access needed by Telegram, configured indexers and peers; keep CI tests isolated.
- Use persistent mounts, health/readiness checks and bounded dependency retries.
  Preserve bot recovery behavior across service interruptions. Never enable multiple
  polling instances with the same token.
- Generate example configuration and an allowlisted Docker build context. Keep
  real configuration ignored and private. Avoid echoing resolved Compose secrets.

## First-run experience

Document a short, reproducible setup sequence in both languages:

1. Copy the example configuration; set a bot token, allowed users and download path.
2. Start qBittorrent and Jackett; follow documented upstream authentication setup.
   Set qBittorrent credentials, configure Jackett indexers and obtain its API key.
3. Enter these connection settings locally and run a read-only setup check.
4. Start the bot and verify `/start`, search, Downloads and Health.

The setup check explains missing values, incorrect credentials, unreachable APIs
and unwritable state without printing credentials or raw diagnostic URLs. An empty
or invalid allowlist must fail closed. Do not assume upstream container images accept
password environment variables; verify their supported configuration mechanism.
Do not ship tracker accounts, preconfigured private indexers or sample passwords
that can become production defaults. Updates must preserve user settings and volumes.

## English and Russian

Introduce a small translation module with stable message keys and separate English
and Russian catalogs. Keep callback payloads, commands, torrent identities and stored
status codes language-neutral. Pass language explicitly through rendering boundaries
so simultaneous users cannot change each other's text.

- On first interaction, use Telegram's supplied Russian language preference when
  present; otherwise use English. Provide `/language` and a visible Language / Язык
  control, with a persisted per-user override. English is the fallback for unsupported
  languages or missing preference information.
- Translate start/help, command descriptions, search/filter/sort UI, previews,
  confirmations, download states, progress units, errors, health cards and notices.
  Preserve torrent titles, paths and indexer names verbatim and escape them safely.
- Configure Telegram command descriptions per language. An explicit user choice
  also updates that user's private-chat menu; shared groups keep language-neutral
  command names and use Telegram's language-specific descriptions.
- A card uses its owning user's preference. Shared torrent access remains unchanged.
  Group card updates follow that card owner, not whichever user last interacted.
- Store preferences in a separate database beside existing bot state. Keep watch
  schema and existing pending-notice compatibility intact. Include preferences in
  backup instructions without importing private production databases.
- Resolve current language when rendering future progress/health updates and when
  first composing a completion notice. Once a notice is queued durably, its saved
  text remains unchanged during retries, even if the language preference changes.
  Historical sent messages are not bulk-rewritten after switching language.

## Reliability constraints

Retain allowlist checks, owner-bound buttons, target identity rechecks, explicit
download confirmation and delete-torrent-plus-files confirmation. All allowlisted
users continue to administer the connected qBittorrent library. Preserve sequential
control handling, background search jobs and metadata-based addition identity.

State stays separate from application releases. Keep at-least-once delivery semantics
documented and pending notices compatible. Ordinary code rollback retains newer
compatible state; backup/restore examples must never silently erase volumes.

## Verification and release acceptance

- Establish a passing exported regression baseline before packaging or translating.
  Preserve meaningful behavior tests; adapt or omit private-environment harness tests
  explicitly, with a record of what they covered and any generic replacement.
- Unit tests use synthetic settings and block networking. Test both catalogs for
  matching keys and interpolation fields, English fallback, Russian plural forms,
  preference persistence, owner isolation and safe handling of untrusted titles.
- Exercise both languages across search, add confirmation, numbered downloads,
  pause/resume, deletion, outages, health cards and completion/restart delivery.
- Build and test Compose from an empty checkout with fresh disposable volumes.
  Verify dependencies, authentication, storage permissions, readiness, bot-only mode,
  restart persistence and upgrade/rollback. Use generated torrents and fixture search
  responses; automated tests must not use real trackers or personal Telegram tokens.
- Separate optional manual Telegram acceptance uses a dedicated test bot and fresh
  settings. Never copy an existing private acceptance environment into this repository.
- GitHub CI runs offline tests/lint plus supported container checks without production
  secrets. No public CI run depends on private NAS access or developer filesystem paths.
- Release documentation includes English/Russian quick starts, configuration,
  backup/restore, limits, tested platforms, troubleshooting and sanitized screenshots.
- Completion requires a clean public-history audit, passing checks, resolved licensing
  and a reproducible fresh install. A pushed repository alone is not a completed release.

## Delivery order

1. Establish the separate repository, reviewed source export, generic documentation,
   passing regression baseline and three-service/bot-only packaging.
2. Add complete bilingual rendering and durable preferences, then test both languages.
3. Verify clean installation, restart/upgrade recovery and release artifacts; complete
   provenance/license and privacy review; publish the new repository and version 0.3.

## Design decisions awaiting user input

Original bot authorship/provenance has been requested from the user. Public code
publication and final license selection depend on that answer. Local inspection,
design and implementation can proceed without assuming redistribution rights.
