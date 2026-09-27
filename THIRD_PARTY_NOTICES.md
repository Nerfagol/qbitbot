# Third-party notices

Original qbitbot code uses the [MIT license](LICENSE). Upstream packages and images
retain their own copyrights/licenses. This source release references service images;
it does not redistribute or relicense their binaries. Package license files remain
in installed distributions. Runtime/development versions are fixed in the lock files.

## Python distributions

License identifiers below were checked against installed metadata for those versions.
The version-specific upstream metadata and project links are available from PyPI.

| Distribution | Version | License | Source/metadata |
| --- | --- | --- | --- |
| anyio | 4.12.1 | MIT | [PyPI](https://pypi.org/project/anyio/4.12.1/) |
| certifi | 2026.1.4 | MPL-2.0 | [PyPI](https://pypi.org/project/certifi/2026.1.4/) |
| charset-normalizer | 3.4.4 | MIT | [PyPI](https://pypi.org/project/charset-normalizer/3.4.4/) |
| h11 | 0.16.0 | MIT | [PyPI](https://pypi.org/project/h11/0.16.0/) |
| httpcore | 1.0.9 | BSD-3-Clause | [PyPI](https://pypi.org/project/httpcore/1.0.9/) |
| httpx | 0.28.1 | BSD-3-Clause | [PyPI](https://pypi.org/project/httpx/0.28.1/) |
| idna | 3.11 | BSD-3-Clause | [PyPI](https://pypi.org/project/idna/3.11/) |
| python-telegram-bot | 21.11.1 | LGPL-3.0-only | [PyPI](https://pypi.org/project/python-telegram-bot/21.11.1/) |
| requests | 2.32.5 | Apache-2.0 | [PyPI](https://pypi.org/project/requests/2.32.5/) |
| typing_extensions | 4.15.0 | PSF-2.0 | [PyPI](https://pypi.org/project/typing-extensions/4.15.0/) |
| urllib3 | 2.6.3 | MIT | [PyPI](https://pypi.org/project/urllib3/2.6.3/) |
| iniconfig | 2.3.0 | MIT | [PyPI](https://pypi.org/project/iniconfig/2.3.0/) |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | [PyPI](https://pypi.org/project/packaging/26.3/) |
| pluggy | 1.6.0 | MIT | [PyPI](https://pypi.org/project/pluggy/1.6.0/) |
| pytest | 8.3.5 | MIT | [PyPI](https://pypi.org/project/pytest/8.3.5/) |
| PyYAML | 6.0.2 | MIT | [PyPI](https://pypi.org/project/PyYAML/6.0.2/) |
| ruff | 0.11.13 | MIT | [PyPI](https://pypi.org/project/ruff/0.11.13/) |

## Container components

Image digests are recorded in [the image inventory](docs/deployment/images.md).

- [qBittorrent licensing](https://github.com/qbittorrent/qBittorrent/blob/master/COPYING):
  source GPL-2.0-or-later; binary distribution GPL-3.0-or-later, with its stated OpenSSL exception.
- [Jackett](https://github.com/Jackett/Jackett/blob/master/LICENSE): GPL-2.0.
- LinuxServer [qBittorrent image build](https://github.com/linuxserver/docker-qbittorrent/blob/master/LICENSE)
  and [Jackett image build](https://github.com/linuxserver/docker-jackett/blob/master/LICENSE): GPL-3.0.
- [CPython](https://docs.python.org/3.12/license.html) and the
  [official Python image](https://github.com/docker-library/python) include their
  upstream license notices and operating-system package licenses.

## Verification tooling

GitHub `actions/checkout` and `actions/setup-python` use MIT; their exact source
commits are pinned in the workflows. [Gitleaks](https://github.com/gitleaks/gitleaks)
uses MIT and is pinned with an archive checksum in the release checklist. Generated
preview images contain only synthetic fixture text and no third-party screenshots.
