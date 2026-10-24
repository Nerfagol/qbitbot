# Public deployment layout implementation plan

> Execution: superpowers:executing-plans, inline in the existing public checkout.

**Goal:** apply the approved first phase of structure-review.md, reducing visible
root files while preserving application and deployment behavior.
**Architecture:** retain qbitbot/ and root compose.yaml; group deployment inputs,
config templates, dependency locks and historical docs by ownership.
**Tech stack:** Python3.12, existing pip locks, Docker/Compose, Markdown.
**Spec:** docs/archive/reviews/structure-2026-10-24.md, phase1 recommendation approved by owner.

## Rulings

- Work in the existing checkout: preserve reviewed uncommitted documentation and
  the user's established in-place workflow. No branch/worktree/commit/push required.
- No src/package-manager/client refactor in this phase; no runtime module edits.
- Root-relative bot.env/.env/downloads and Compose project/volume names must remain.
- Historical archive prose keeps original command paths; rewrite its links to
  retained evidence and add an archive notice. Current docs use new commands.

## Tasks

- [x] Capture old resolved Compose configs with synthetic credentials for all3 modes.
- [x] Move Dockerfiles/solver inputs to deploy/docker/, variants to deploy/;
  template to config/, locks to requirements/, notices to docs/licenses/;
  agent notes to docs/development/agent/, historical plans/audits to docs/archive/.
- [x] Update root Compose/build flags, Docker COPY and .dockerignore allowlist,
  CI, tests, integration archive exporters and both-language current instructions.
- [x] Fix current release guidance; add docs index, archive context and migration
  instructions. Keep historical fixture Dockerfiles and baseline Git refs unchanged.
- [x] Verify semantic equality of old/new Compose configs except intended build
  paths, including same project/volume names; full make check and compose-check.
- [x] Run disposable API/restart/rollback and fresh EN/RU/bot-only/state recovery;
  rebuild/smoke optional solver and rescan runtime images if dependency changes arise.
- [x] Final independent read-only review, address findings, update handoff and
  report remaining work. Stage moved/new files only for tracked-source Docker
  export; no commit or push without a request.

## Verification outcome

All listed checks passed. Review identified generated rollback Dockerfile selection
and stale diagnostic paths; reproduced/fixed and reverified. Docker Desktop returns
Windows/UNC contexts, so the new context check normalizes separators. Python runtime
logic and both lock closures remain byte-identical; locale path guidance updated.
Current work is staged only for tracked-source export, with no commit/push/deployment.

Real-directory canary also exposed broad parent exceptions. Re-denied private
descendants, added permanent compose-check verification, and reran fresh-stack
builds. Raw stdin archives remain restricted by their explicit source manifest.
