# Installable src package implementation plan

> Execute inline using superpowers:executing-plans and test-driven-development.

**Goal:** install qbitbot from a built distribution, preserving module commands,
behavior, locale payloads and container restrictions.
**Spec:** approved next packaging phase of the structural review and owner request.
**Architecture:** src/qbitbot with a standard setuptools backend, explicit package
and locale data, static project metadata as version source; wheel installed into
runtime image. Runtime clients remain unchanged.
**Tech:** Python3.12, setuptools84.2.1 build-only, existing pinned pip dependencies.

## Constraints and decisions

- Phase1 checkpoint is e9413e9. Work in the existing public checkout; no push/NAS.
- Setuptools explicitly includes only Python modules and EN/RU locale data.
- pyproject.toml owns version0.3.0 (unchanged); retire duplicate VERSION file.
- Declare existing direct dependencies with their reviewed exact runtime pins.
- Build backend is pinned in metadata/build.lock/dev.lock; not in runtime image.
- Preserve app.py CRLF and all existing runtime modules except inert version export.
- Historical rollback reader stays on its original Git ref/top-level imports;
  synthetic writable-release fixture copies the installed package explicitly.

## Tasks

- [x] Write package metadata/artifact/locale/privacy/regular-install tests; observe
  metadata tests fail before adding metadata. Tests use synthetic input copies,
  no-index/no-build-isolation builds and no real environment/token/state.
- [x] Add metadata/build pin and move package to src/. Install editable for local
  development; remove checkout PYTHONPATH tricks from current-package tests.
- [x] Prove wheel and sdist rebuild, installed metadata, both catalogs, inert import,
  CLI help and missing-config rejection outside checkout. Preserve direct/lock pins.
- [x] Build/install wheel in a separate Docker build stage; exclude backend/installer
  from runtime. Update deny-by-default source/context manifests and canary tests.
- [x] Update probes to locate the installed package; retain only explicit historical
  reader/source-rollback path behavior. Preserve current module commands and state.
- [x] Update Makefile/CI/dev setup/versions/notices and docs. Run full tests and
  dependency audit, Compose, API/restart/rollback/fresh recovery and runtime scan.
- [x] Perform final independent read-only review, fix verified findings and handoff.
  Packaging work remains uncommitted unless asked; client extraction remains separate.

## Completion evidence

Metadata RED observed before implementation.625 checks passed, including actual
wheel/sdist/private-file/regular-install tests. Compose/context, installed-image
security/metadata/source checks, API/restart/rollback and fresh EN/RU/history/
backup/recovery passed. Runtime Trivy and build/dev audit report zero findings.
Runtime byte moves preserved, backend absent at runtime, reviewed code has no
blockers. Phase1 is committed; packaging remains staged/uncommitted and unpushed.
