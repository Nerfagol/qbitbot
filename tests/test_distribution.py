"""Build and install real distributions from synthetic, allowlisted project inputs."""

from email.parser import BytesParser
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tomllib
import zipfile

import pytest
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def test_project_metadata_and_lock_pins_are_consistent():
    config = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = config["project"]
    assert project["name"] == "qbitbot"
    assert project["requires-python"] == "~=3.12.0"
    runtime = dict(
        (canonicalize_name(line.split("==")[0]), line.split("==")[1])
        for line in (ROOT / "requirements/runtime.lock").read_text().splitlines()
        if line and not line.startswith("#")
    )
    dev = dict(
        (canonicalize_name(line.split("==")[0]), line.split("==")[1])
        for line in (ROOT / "requirements/dev.lock").read_text().splitlines()
        if line and not line.startswith("#")
    )
    for item in project["dependencies"]:
        requirement = Requirement(item)
        assert str(requirement.specifier) == "==" + runtime[canonicalize_name(requirement.name)]
    assert runtime.items() <= dev.items()
    assert set(config["build-system"]["requires"]) == set(
        (ROOT / "requirements/build.lock").read_text().splitlines()
    )
    assert all(
        dev[canonicalize_name(Requirement(item).name)] in Requirement(item).specifier
        for item in config["build-system"]["requires"]
    )


def invoke(*args, cwd):
    result = subprocess.run(
        [sys.executable, *args], cwd=cwd, capture_output=True, text=True, timeout=90
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result


@pytest.fixture(scope="module")
def distribution(tmp_path_factory):
    root = tmp_path_factory.mktemp("distribution")
    project = root / "project"
    project.mkdir()
    for name in ("pyproject.toml", "README.md", "LICENSE", "docs/licenses/THIRD_PARTY_NOTICES.md"):
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    shutil.copytree(
        ROOT / "src/qbitbot",
        project / "src/qbitbot",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in (
        ".env",
        "bot.env",
        "private.sqlite3",
        "docs/development/agent/private.txt",
        "src/qbitbot/private.env",
        "src/qbitbot/locales/private.env",
    ):
        target = project / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("synthetic private artifact canary\n")
    output = root / "artifacts"
    output.mkdir()
    invoke(
        "-m",
        "pip",
        "wheel",
        "--no-index",
        "--no-deps",
        "--no-build-isolation",
        "--wheel-dir",
        str(output),
        ".",
        cwd=project,
    )
    wheel = next(output.glob("*.whl"))
    invoke(
        "-c",
        "from setuptools.build_meta import build_sdist; build_sdist(" + repr(str(output)) + ")",
        cwd=project,
    )
    sdist = next(output.glob("*.tar.gz"))
    return root, wheel, sdist


def test_wheel_has_metadata_locales_and_no_private_or_development_files(distribution):
    _, wheel, _ = distribution
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        assert "qbitbot/locales/en.json" in names
        assert "qbitbot/locales/ru.json" in names
        assert "qbitbot/cli/state_permissions.py" in names
        assert not any(
            "private" in n or n.endswith(".env") or n.startswith(("tests/", "integration/", "src/"))
            for n in names
        )
        metadata = BytesParser().parsebytes(
            archive.read(next(n for n in names if n.endswith(".dist-info/METADATA")))
        )
        config = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        assert metadata["Name"] == "qbitbot"
        assert metadata["Version"] == config["version"]
        assert metadata["License-Expression"] == "MIT"
        assert set(metadata.get_all("Requires-Dist")) == {
            str(Requirement(n)) for n in config["dependencies"]
        }
        assert any(n.endswith("/licenses/LICENSE") for n in names)
        assert any(n.endswith("THIRD_PARTY_NOTICES.md") for n in names)


def test_sdist_rebuilds_the_same_runtime_payload_without_private_inputs(distribution):
    root, wheel, sdist = distribution
    extracted = root / "sdist"
    with tarfile.open(sdist) as archive:
        names = archive.getnames()
        assert not any("private" in n or n.endswith(".env") for n in names)
        archive.extractall(extracted, filter="data")
    output = root / "rebuilt"
    output.mkdir()
    invoke(
        "-m",
        "pip",
        "wheel",
        "--no-index",
        "--no-deps",
        "--no-build-isolation",
        "--wheel-dir",
        str(output),
        ".",
        cwd=next(extracted.iterdir()),
    )
    with zipfile.ZipFile(wheel) as original, zipfile.ZipFile(next(output.glob("*.whl"))) as rebuilt:
        runtime = {n: original.read(n) for n in original.namelist() if n.startswith("qbitbot/")}
        assert runtime == {
            n: rebuilt.read(n) for n in rebuilt.namelist() if n.startswith("qbitbot/")
        }


def test_regular_install_runs_outside_checkout_with_both_locales_and_inert_import(distribution):
    root, wheel, _ = distribution
    target = root / "installed"
    invoke(
        "-m",
        "pip",
        "install",
        "--no-index",
        "--no-deps",
        "--target",
        str(target),
        str(wheel),
        cwd=root,
    )
    code = (
        "import sys; sys.path.insert(0," + repr(str(target)) + "); "
        "import qbitbot,importlib.metadata; from pathlib import Path; from qbitbot.i18n import tr; "
        "assert Path(qbitbot.__file__).is_relative_to(" + repr(str(target)) + "); "
        "assert qbitbot.__version__==importlib.metadata.version('qbitbot'); "
        "assert 'qbitbot.app' not in sys.modules; "
        "assert tr('nav.search','en') != tr('nav.search','ru'); print('installed package verified')"
    )
    result = invoke("-I", "-c", code, cwd=root)
    assert "installed package verified" in result.stdout
