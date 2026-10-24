# Package builds and installation

The runtime lives in src/qbitbot/. Import names and module commands remain
`qbitbot.*`. Python3.12 is the supported series. No PyPI publication or new release
tag is part of this packaging migration.

## Development

```sh
python3.12 -m venv .venv
make install-dev
make check
make wheel
```

install-dev installs requirements/dev.lock and a local editable package without
resolving new runtime versions. Refresh the editable installation after changing
metadata. Importing qbitbot is inert: it exposes installed __version__ without
reading bot.env or starting polling. Handler, startup and client imports are inert with respect to personal settings,
state and networking. Explicit startup loads/validates configuration and composes
service clients before polling. See [service boundaries](services.md).

## Version and dependency ownership

pyproject.toml [project].version is the single version source; the duplicate root
VERSION file was removed. The version remains0.3.0 until a deliberate release bump.
Installed importlib.metadata and qbitbot.__version__ report the built version.

Existing direct runtime pins are declared in project.dependencies; runtime.lock
holds the complete deployment closure. Setuptools84.2.1 is pinned in build-system,
requirements/build.lock and dev.lock. It runs only during wheel construction.
No new runtime dependencies are introduced. Keep all shared pins consistent.

## Artifact verification

make check builds a real wheel and source distribution from a generated copy of
reviewed inputs, includes synthetic private-file canaries and rebuilds the wheel
from its source distribution. It verifies metadata, exact runtime payload,
EN/RU catalogs and license notices, then performs a regular wheel installation
outside the source checkout. These builds use no-index/no-build-isolation and the
already installed backend. No project credentials or live service fixtures enter.

Only qbitbot/qbitbot.cli Python modules and the two declared locale JSON files are
packaged as runtime data. Docker context exclusions are tested separately with
make compose-check. The installed-image verification runs without a checkout,
checks both catalogs/version, rejects missing credentials before polling, and
confirms setuptools/pip are absent under nonroot/read-only restrictions.

## Container and recovery behavior

The image uses a separate package-build stage, then installs the wheel and locked
runtime dependencies in the final stage. Runtime code resides in Python's installed
package directory; /app remains the working directory for optional bot.env and
relative settings. Durable /state and qBittorrent paths/volumes are unchanged.

Probes import the installed package and find its source through module metadata.
Only the explicitly historical reader and synthetic writable-release rollback
fixture use source overrides. Do not reintroduce a root PYTHONPATH dependency to
make missing wheel resources pass. Use each old tag's own guides for old images.

CLI module commands remain available after installation:

```sh
python -m qbitbot
python -m qbitbot.cli.setup_check --help
python -m qbitbot.cli.backup_state --help
python -m qbitbot.cli.state_permissions --help
```

The first starts a real poller and requires private configuration. Automated checks
use only help/missing-config paths or synthetic Telegram transport.
