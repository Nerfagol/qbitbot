# Service clients and explicit startup implementation plan

> Execute inline using planning/execution, TDD and final independent review.

**Goal:** remove qBittorrent/Jackett transport and environment/bootstrap effects
from Telegram handlers while preserving behavior, security and module commands.
**Spec:** owner approved all proposed next steps after packaging checkpoint071c192.
**Architecture:** narrow immutable client configs and client-owned protocol/session
logic under clients/; shared search-result metadata outside UI; startup owns env
loading, validated settings injection, handler wiring and polling. Existing handler
boundary functions remain thin adapters for feature modules and test seams.
**Stack:** existing pinned Python3.12/PTB/Requests; no new dependency or schema.

## Constraints and decisions

- Push checkpoints and verify all3 GitHub workflows. No NAS/real torrent/poller.
- Keep app.py CRLF, owner/allowlist checks, sequential controls and per-user jobs.
- Preserve 200/Ok and204-empty auth/add semantics, session TTL/relogin behavior,
  Host override, no environment credentials/redirects, hash validation and add types.
- Preserve Jackett DNS-pinned trusted origin, bounded reads/response closure,
  Torznab/JSON coverage/error semantics and safe last-search health.
- app/startup/client imports read no personal environment/config file or open services/state.
  Immutable packaged locale reads remain allowed, as in the existing UI.
  Explicit configure/load/build controls startup; default unconfigured access denies.
- Existing python -m qbitbot and maintenance commands remain. Historical reader and
  source-rollback fixture keep intentional exceptions; probes configure explicitly.
- Keep source/wheel/context package allowlists precise for clients/*.py; no manager,
  dependency version, state mapping or database changes. Work in existing checkout.

## Tasks

- [x] Write failing tests for inert handler/client/startup imports, independent
  clients with synthetic settings/transports, TTL/relogin and secret-safe configs;
  test JSON/Torznab bounded search and explicit startup/load behavior.
- [x] Extract QBitConfig/Client and JackettConfig/Client/parsers. Move SearchResults
  into a transport-neutral shared module, retaining existing import compatibility.
- [x] Make app imports inert. startup.load_runtime/configure_handlers/build_application
  owns configuration and wiring; __main__ uses startup.main. Preserve thin handler
  I/O adapters, health tracking and existing callbacks; update targeted test seams.
- [x] Update probes, package/context/source manifests, docs and current handoff.
  Prove wheel includes clients and no private descendants; no added dependencies.
- [x] Run full checks, Docker Compose/context, API/thread/add/controls/restart/
  rollback, fresh EN/RU/history/bot-only/backup/recovery and runtime advisory scan.
- [x] Independent read-only final review and fix verified findings. Commit/push
  verified refactor and check CI as continuation of owner-authorized full steps;
  owner requested all steps, including publication and exact-commit CI verification.

## Evidence

631 full checks and all local Docker/context/API/recovery scenarios passed. Both
independent client tests and original HTTP/security assertions retained. Frozen
client configs and startup are explicit; unchanged protocol behavior was reviewed.
Generated fixture URL seams were updated after real failures; security allowlists
were not relaxed. Runtime scan0. Checkpoints were published with all3 CI green;
new refactor publication is recorded by Git/Actions, not assumed from local tests.
