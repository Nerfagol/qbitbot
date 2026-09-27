# Public Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an independently maintained public qbitbot project with a three-service installation and complete English/Russian UI.

**Architecture:** A fresh repository receives only audited source and synthetic tests. Compose manages bot, qBittorrent and Jackett with persistent storage; a separate bot-only configuration connects existing services. Explicit per-user language resolution preserves owner-bound controls and durable notifications.

**Tech Stack:** Python 3.12, python-telegram-bot, requests, SQLite, Docker Compose v2, pytest/Ruff, GitHub Actions.

**Spec:** [Public release design](../specs/2026-09-27-public-release-design.md), approved by the user on 2026-09-27, including MIT licensing for original code.

## Global Constraints

- The new repository must have its own Git directory and fresh history.
- Existing private deployments and their accepted version are independent of this work.
- Direct Telegram torrent-file uploads and media-app links remain out of scope.
- English is the fallback for unsupported languages or missing preference information.
- The first verification target is Linux amd64. Do not advertise unverified ARM or NAS platform support.
- Create the GitHub repository and upload only after this publication check passes.
- A pushed repository alone is not a completed release.

## Review Focus

1. Exported tests/docs/history can leak private identifiers: packaging task 1 and release task 3.
2. Bootstrap must work before credentials are known: packaging tasks 2/3.
3. User language must survive restart without changing another user's cards: bilingual tasks 2/5.
4. Language changes must preserve confirmation guards and pending delivery: bilingual tasks 3–5.
5. Fresh install, rollback and cleanup must be proven on disposable resources: release tasks 1/2.

## Starting state

- A separate local repository already exists with fresh history and a design document.
- The user confirmed original authorship and approved the design before requesting this plan.
- Source has not been exported and the new GitHub repository has not been created.
- No implementation, language conversion, container verification or publication is claimed by this plan.
- Existing source uses six runtime modules, Russian rendering, SQLite watch/health state,
  owner-bound controls and a synthetic regression suite. Preserve those boundaries initially.

## Ordered milestone plans

| Order | Plan | Independently reviewable outcome |
| --- | --- | --- |
| 1 | [Public packaging](2026-09-27-public-packaging.md) | Audited source, regression baseline, safe settings and bundled/bot-only installation |
| 2 | [Bilingual interface](2026-09-27-bilingual-interface.md) | Complete EN/RU flows with persisted preferences and compatible delivery |
| 3 | [Verification and publication](2026-09-27-public-release-verification.md) | Fresh-install/recovery evidence, clean public artifacts, passing CI and tagged release |

These are three sequential plans because packaging, localization and publication
have distinct acceptance criteria. Work through each plan's checkboxes and commit
tested units. A failed milestone remains incomplete; do not skip into publication.

## Execution checklist

- [ ] User reviews this plan and selects native or subagent-driven execution.
- [ ] Confirm all execution tools operate in the new public folder. Do not create
  a linked worktree from the private donor; the independent checkout already supplies isolation.
- [ ] Complete packaging tasks 1–3 and record retained test coverage.
- [ ] Complete bilingual tasks 1–5 and record owner/restart compatibility checks.
- [ ] Complete release-verification tasks 1–3 and audit all public history/artifacts.
- [ ] Complete publication task 4; record remote CI, version tag and release links.

## Self-review

The plans map every design section to a task: repository separation/provenance to
packaging 1 and release 3; architecture/first-run to packaging 2/3; language to bilingual
1–5; reliability to regression retention plus bilingual guards/recovery; verification
and release documentation/publication to release 1–4. No private absolute paths,
account identifiers, credentials or deployment records are required in these plans.

Interfaces flow in dependency order: settings/check results before packaging and
diagnostic translations, catalog/preferences before renderers, packaging baseline
before rollback rehearsal, local audit before repository upload, and exact-commit CI
before release tagging. Image/scanner/action pins are resolved and recorded during
their owning tasks, rather than invented here. Review-focus conditions have explicit
tests in the tasks that own them.

## Execution recommendation

Native execution in the separate public folder is recommended: language propagation
touches shared rendering/lifecycle interfaces, so sequential implementation keeps
those changes coherent. Complete an independent review after implementation and
before publication. Subagent-driven execution is also supported if the user prefers
per-task independent implementation/review. Selection awaits user review of this plan.
