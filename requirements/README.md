# Reviewed dependency locks

- runtime.lock is the full pinned application dependency closure.
- dev.lock adds test/development tools and the build backend to those runtime pins.
- build.lock pins the backend used only during wheel construction. Its pin matches
  pyproject.toml and dev.lock; the final runtime image excludes it.

Use Python3.12, create .venv, then run `make install-dev`. This installs the reviewed
lock and a local editable package without resolving new runtime versions. Refresh
that installation after metadata changes. The bot image installs runtime.lock plus
a built wheel; its module commands remain unchanged.

pyproject.toml declares the direct application pins, supported Python and version.
Runtime pins are unchanged by this packaging migration. For intentional dependency
updates, resolve a clean Python3.12 runtime closure, then development tools with
those same pins. Review diffs and run pip check, pip-audit, make check and Docker/
API/recovery checks. Packaging tests enforce shared pin consistency. No package
manager migration is required.
