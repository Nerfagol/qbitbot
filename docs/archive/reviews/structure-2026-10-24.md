# Public repository structure review — 2026-10-24

> Historical record: paths and commands describe their original revision. Use the
> [current guides](../../README.md) for the current source layout.

Scope: tracked source at `4fab35c`, including root entry points, application modules,
tests, Docker verification, deployment inputs, CI and documentation. This is a
structural review and proposed direction, not an implemented migration. No services
or production data were accessed. Existing test results are not new verification
of a proposed layout.

## Assessment

The project is a valid Docker-first Python application with a flat import layout.
There is no universal modern standard that limits the number of root files or
requires `src/`. The current layout is functional, but the earlier three-file
cleanup did not establish a consistent policy for deployment assets or packaging.

There are 127 tracked files:20 at root (15 visible and5 hidden),19 under qbitbot/,
42 tests,9 integration files,29 docs,5 docker files and3 GitHub workflows.
The application root package, separate state, inert package entry point, adjacent
locales, isolated test fixtures and pinned/read-only CI are useful foundations.

## Findings, ordered by practical importance

### 1. Deployment assets have inconsistent ownership

The bot Dockerfile and three Compose files are at root, service Dockerfiles are
under docker/, one environment example is hidden at root and another is visible.
CI and integration runners repeat their paths and build-context construction.
Examples: Dockerfile, compose*.yaml, docker/, integration/run.py:254 and
.github/workflows/security.yml. Moving files without changing every consumer
would break builds or the source allowlist.

Recommendation: collect image recipes and optional deployment variants under
`deploy/`, retain root compose.yaml as the default entry point, and put the bot
credential template under `config/`. Keep the default `.env.example` discoverable
at root. Use repository-root build contexts and document root-relative invocation.

### 2. Packaging is intentionally source-only and checkout-dependent

pyproject.toml configures Ruff/pytest but has no build backend or project metadata.
Docker copies qbitbot/ directly rather than installing a built distribution.
tests/test_package.py:18 injects the repository through PYTHONPATH, while
integration probes prepend /app to sys.path. This verifies source-tree execution,
not whether an installable package includes all runtime resources.

This is valid for the present Docker-only distribution, not a broken package
release. If adopting src/qbitbot/, first add package metadata, a chosen build
backend and explicit locale/license inclusion. Then test a wheel installed in a
clean environment from outside the checkout. Preserve `python -m qbitbot` and
maintenance module commands. Moving into src/ alone does not achieve this.

### 3. app.py mixes boundaries and initializes configuration during import

qbitbot/app.py has1,220 lines and65 top-level functions. It combines qBittorrent
sessions/control, torrent parsing/fetching, Torznab parsing/search, Telegram
handlers and startup. At lines42–43, import reads bot.env and validates environment.
The test fixture must change working directory, clear the environment and load
this file under an alternate module name. The package __init__ itself is inert.

Recommendation: extract concrete service clients and torrent parsing behind
explicit settings, then leave startup/composition in app.py. Do this separately
from path moves. Preserve sequential controls, per-user background jobs, access
checks, target identity, HTTP safety and CRLF until an explicit formatting change.
Avoid creating empty layers or splitting already cohesive feature modules.

### 4. Dependency/version ownership needs a documented source of truth

The two lockfiles repeat the runtime closure. VERSION contains0.3.0, but the
Python package exposes no installed project version and pyproject.toml contains
no version metadata. The release checklist still instructs creating v0.3.0 and
waiting for two workflows, although there are now three workflows and that tag
already exists. That is a concrete outdated instruction.

Recommendation: retain reviewed lockfiles as requirements/runtime.lock and
requirements/dev.lock; document how to regenerate and check their shared pins.
When packaging is introduced, declare direct dependencies, supported Python and
version ownership in pyproject.toml. Retire VERSION only after its release
consumers use that source. No package-manager migration is needed for cleanup.
Update current release instructions while preserving historical audit evidence.

### 5. Verification code has repeated orchestration responsibilities

integration/run.py, public_stack.py and flaresolverr.py each manage Docker calls,
readiness and resource cleanup. run.py has565 lines and probe.py746. They cover
different scenarios, so deleting one is not consolidation. The older runners also
have explicit ownership checks and pre-registration of resource intent that must
not be lost when sharing helpers.

Recommendation: retain integration/ as a coherent suite; extract only repeated
Docker/resource-lifecycle logic into an import-safe helper, with cleanup-failure
regressions. This matters more than renaming the folder to tests/integration/.
Forty-two focused offline test files are reasonable and need no cosmetic split.

### 6. Documentation mixes current guidance with accumulated process history

User guides, development guidance and dated audits already have useful homes.
There is no docs index. Workflow-specific plans, agent memory and progress sit
beside general developer documents. Current memory still says security CI is
unpublished, although its workflow was pushed; actual CI status was not checked
by this review. The latest progress does not record the completed pushes.

Recommendation: add docs/README.md; organize navigation around user/development/
operations/audit audiences. Put agent-only notes in docs/development/agent/ and
historical plans/audits in a clearly labelled archive, preserving provenance and
links. Keep README, CHANGELOG, LICENSE and AGENTS at root; move detailed third-party
notices under docs/licenses/ and update image/license-copy inputs. Fix stale current
facts without rewriting dated historical results as fresh verification.

## Proposed end state

This is a recommendation, not a requirement imposed by Python or Docker:

```text
.github/workflows/
src/qbitbot/                    installed runtime package, in a later phase
  cli/
  clients/                      extracted concrete service clients
  locales/
tests/                          offline behavior and regression tests
integration/                    disposable Docker scenarios and shared support
deploy/
  docker/                       bot/service Dockerfiles and solver build inputs
  compose.bot-only.yaml
  compose.flaresolverr.yaml
config/
  bot.env.example
requirements/
  runtime.lock
  dev.lock
docs/
  README.md                     guide index
  deployment/
  development/agent/
  licenses/
  archive/
README.md
CHANGELOG.md
LICENSE
AGENTS.md
Makefile
pyproject.toml
compose.yaml
.env.example                    hidden default configuration template
```

Keep ordinary tool dotfiles at root where their tools discover them. VERSION
remains at root until package/release version ownership is migrated. Moving
non-default files can reduce visible root files from15 to8 initially and7 once
VERSION is retired. Root file count is a consequence of ownership, not the goal.

## Migration choices and recommendation

1. **Focused deployment/documentation consolidation first (recommended).** Move
   Docker/optional Compose/templates/locks/notices into their owners, fix current
   release docs, and update every consumer. Keep the runtime import layout and
   package manager unchanged. This addresses the root concern with limited risk.
2. **Complete packaging and application refactor.** Also add installed-package
   metadata/src layout, wheel checks, explicit startup and client extraction.
   Better long-term boundaries, but a larger change to build/test/startup behavior.

Recommend two separately reviewable phases rather than one filesystem shuffle.
No large runtime reorganization should be bundled into the first phase.

## Required migration checks

- Preserve the existing Compose project identity and named volumes. Moving the
  first Compose file can change default project names and relative path resolution.
  Validate root-relative invocation (including --project-directory for standalone
  variants), env_file, downloads paths, build contexts and merged networks.
- Keep secrets/state outside source and image contexts. Update .dockerignore and
  source-export allowlists rather than broadening the context to make builds pass.
- Update Makefile, workflows, both-language guides, container probes, package tests
  and historical rollback handling; do not alter old release fixtures blindly.
- Run full offline checks and Docker Compose/API/restart/rollback/fresh-stack
  verification. Solver JS/TLS, ownership migration and security scans must remain.
- A later src/package phase also requires clean installed-wheel execution,
  included locale tests, inert imports and unchanged bot/maintenance entry points.
- No NAS deployment, existing volume rename or real torrent operation is needed.

## Primary references

- [PyPA: src versus flat layout](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/)
  explains both layouts and why src needs installation and prevents accidental
  checkout imports. It does not mandate src for every application.
- [PyPA: pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/)
  distinguishes project/build metadata from tool-only configuration.
- [Docker: merging Compose files](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)
  documents evaluation of relative paths against the first/base Compose file.
