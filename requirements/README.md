# Reviewed dependency locks

- runtime.lock is the complete pinned application dependency closure.
- dev.lock contains the same runtime pins plus test/development tools.

Use Python3.12 and install with `python -m pip install -r requirements/dev.lock`
inside your development virtual environment. The bot image installs runtime.lock.
The lock contents were preserved during the repository layout move.

For an intentional dependency update, resolve the runtime closure in a clean
Python3.12 environment, then resolve the development closure with those runtime
pins and the reviewed development tools. Keep shared packages at identical
versions. Review lock diffs, run pip check and pip-audit, make check, and the
Docker/API/recovery checks before accepting new pins. Dependency sources/package
manager migration are separate work; this layout change introduces neither.
