"""Rehearse the actual public Compose files using newly owned, isolated resources."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def cleanup_project(docker, project):
    if not re.fullmatch(r"qbitbot-public-test-[a-f0-9]{12}(?:-only)?", project):
        raise ValueError("Not a disposable project name")
    errors = []
    for kind, listing, removing, template in [
        ("container", ("ps", "-aq"), ("rm", "-f"), "{{json .Config.Labels}}"),
        ("volume", ("volume", "ls", "-q"), ("volume", "rm"), "{{json .Labels}}"),
        ("network", ("network", "ls", "-q"), ("network", "rm"), "{{json .Labels}}"),
    ]:
        try:
            identifiers = (
                docker(*listing, "--filter", "label=com.docker.compose.project=" + project)
                .decode()
                .split()
            )
            for identifier in dict.fromkeys(identifiers):
                try:
                    labels = json.loads(
                        docker("inspect", "--type", kind, "--format", template, identifier)
                    )
                    if labels.get("com.docker.compose.project") != project:
                        raise ValueError("Ownership mismatch")
                    docker(*removing, identifier)
                except Exception:
                    errors.append(kind)
        except Exception:
            errors.append(kind)
    if errors:
        raise RuntimeError("Scoped cleanup failed: " + ", ".join(errors))


def validate_isolation(config, *, owned_network=None):
    for network in config.get("networks", {}).values():
        if network.get("external"):
            if not owned_network or network.get("name") != owned_network:
                raise ValueError("External network is not owned")
        elif not network.get("internal"):
            raise ValueError("Runtime network must be internal")
    for volume in config.get("volumes", {}).values():
        if volume.get("external"):
            raise ValueError("External volume")
    for service in config["services"].values():
        if service.get("ports") or service.get("network_mode") or service.get("privileged"):
            raise ValueError("Host exposure")
        for mount in service.get("volumes", []):
            if mount.get("type") != "volume" or mount.get("source") not in config.get(
                "volumes", {}
            ):
                raise ValueError("Non-owned mount")


def export_checkout(destination):
    names = (
        subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True)
        .stdout.decode()
        .split("\0")
    )
    # New harness files are deliberately included before their first commit.
    names += [
        "integration/compose.test.yaml",
        "integration/public_probe.py",
        "integration/fixtures.py",
        "backup_state.py",
        "integration/recovery_probe.py",
    ]
    for name in dict.fromkeys(filter(None, names)):
        source = ROOT / name
        if source.is_symlink() or Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Unsafe export input")
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def fresh(docker, root, project, image, checks):
    def compose(*args, only=False):
        files = (
            ["compose.bot-only.yaml", "only.test.json"]
            if only
            else ["compose.yaml", "integration/compose.test.yaml"]
        )
        command = [
            "compose",
            "-p",
            project + ("-only" if only else ""),
            "--project-directory",
            str(root),
        ]
        for name in files:
            command.extend(["-f", str(root / name)])
        return docker(*command, *args, timeout=360)

    (root / ".env").write_text("TEST_BOT_IMAGE=" + image + "\n")
    (root / "bot.env").write_text("")
    cfg = json.loads(compose("config", "--format", "json"))
    validate_isolation(cfg)
    compose("build", "bot")
    compose("pull", "qbittorrent", "jackett")
    compose("up", "-d", "--wait", "--wait-timeout", "150", "qbittorrent", "jackett")
    checks.append("dependency bootstrap with blank bot credentials")
    qbit = compose("ps", "-q", "qbittorrent").decode().strip()
    jackett = compose("ps", "-q", "jackett").decode().strip()
    # The generated password and API key never enter logs or result artifacts.
    logs = docker("logs", qbit)
    matches = re.findall(rb"temporary password is provided for this session:\s*(\S+)", logs)
    if not matches:
        raise RuntimeError("Disposable qBittorrent bootstrap credentials unavailable")
    password = matches[-1].decode()
    settings = json.loads(docker("exec", jackett, "cat", "/config/Jackett/ServerConfig.json"))
    key = settings["APIKey"]
    values = {
        "BOT_TOKEN": "123456:SYNTHETIC_PUBLIC_ACCEPTANCE",
        "ALLOWED_USERS": "101,202",
        "QBIT_USER": "admin",
        "QBIT_PASS": password,
        "QBIT_URL": "http://qbittorrent:8080",
        "JACKETT_API_KEY": key,
        "JACKETT_TORZNAB_URL": "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api",
        "PTB_USE_AIOHTTP": "0",
        "WATCH_INTERVAL_SEC": "1",
    }
    (root / "bot.env").write_text(
        "".join(k + "='" + v.replace("'", "\\'") + "'\n" for k, v in values.items())
    )
    (root / "bot.env").chmod(0o600)
    compose("run", "--rm", "--no-deps", "bot", "python", "setup_check.py")
    compose("up", "-d", "--no-deps", "bot")
    bot = compose("ps", "-q", "bot").decode().strip()
    for name in ("public_probe.py", "fixtures.py"):
        docker("cp", str(root / "integration" / name), bot + ":/tmp/" + name)
    result = json.loads(docker("exec", bot, "python", "/tmp/public_probe.py", "fresh", timeout=120))
    checks.extend(result["checks"])
    # A service outage is observed by the same bot container, then recovers.
    docker("stop", "--time", "10", jackett)
    docker("exec", bot, "python", "/tmp/public_probe.py", "outage", timeout=60)
    docker("start", jackett)
    compose("up", "-d", "--wait", "--wait-timeout", "150", "jackett")
    docker("exec", bot, "python", "setup_check.py", "--language", "ru", timeout=60)
    checks.append("dependency outage and recovery without bot rebuild")
    network = cfg["networks"]["default"]["name"]
    only = {
        "services": {
            "bot": {
                "image": image,
                "command": ["python", "-c", "import time; time.sleep(1800)"],
                "restart": "no",
            }
        },
        "networks": {"default": {"external": True, "name": network}},
    }
    (root / "only.test.json").write_text(json.dumps(only))
    only_cfg = json.loads(compose("config", "--format", "json", only=True))
    assert set(only_cfg["services"]) == {"bot"}
    validate_isolation(only_cfg, owned_network=network)
    compose("run", "--rm", "--no-deps", "bot", "python", "setup_check.py", only=True)
    compose("up", "-d", "--no-build", only=True)
    checks.append("bot-only Compose with explicit existing-service endpoints")
    return bot, cfg


def recovery(docker, root, project, image, bot, config, checks):
    probe = root / "integration/recovery_probe.py"
    docker("cp", str(probe), bot + ":/tmp/recovery_probe.py")
    docker("exec", bot, "python", "/tmp/recovery_probe.py", "seed")
    docker(
        "exec",
        bot,
        "python",
        "backup_state.py",
        "--watch-db",
        "/state/watches.sqlite3",
        "--destination",
        "/state/snapshot",
    )
    docker("stop", "--time", "5", bot)
    state = config["volumes"]["bot-state"]["name"]
    # Rebuild the exact original public application code on the same locked runtime.
    baseline = root / "baseline-build"
    baseline.mkdir()
    files = (
        "tg_torrent_bot.py",
        "watch_store.py",
        "monitoring.py",
        "downloads.py",
        "search_ui.py",
        "health.py",
    )
    for name in files:
        data = subprocess.run(
            ["git", "show", "7267bcd:" + name], cwd=ROOT, capture_output=True, check=True
        ).stdout
        (baseline / name).write_bytes(data)
    (baseline / "Dockerfile").write_text("FROM " + image + "\nCOPY " + " ".join(files) + " /app/\n")
    old_image = project + ":original-public"
    docker("build", "-t", old_image, str(baseline), timeout=300)

    def run(name, selected, mode, mounts):
        identifier = project + "-" + name
        docker(
            "create",
            "--name",
            identifier,
            "--label",
            "com.docker.compose.project=" + project,
            "--network",
            "none",
            *mounts,
            selected,
            "python",
            "/tmp/recovery_probe.py",
            mode,
        )
        docker("cp", str(probe), identifier + ":/tmp/recovery_probe.py")
        docker("start", "--attach", identifier)
        assert docker("inspect", "--format", "{{.State.ExitCode}}", identifier).strip() == b"0"

    run("replacement", image, "new", ["-v", state + ":/state"])
    run("rollback", old_image, "old", ["-v", state + ":/state"])
    run("upgrade-again", image, "new", ["-v", state + ":/state"])
    checks.append(
        "replacement and public-baseline rollback retain pending notice, health card, v1 schema and preferences"
    )
    restored = project + "-restored-state"
    docker("volume", "create", "--label", "com.docker.compose.project=" + project, restored)
    run(
        "disaster-restore",
        image,
        "restore",
        ["-v", restored + ":/state", "-v", state + ":/source:ro"],
    )
    run("restored-check", image, "new", ["-v", restored + ":/state"])
    checks.append("online backup integrity and deliberate snapshot restore into a new volume")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--context")
    parser.add_argument("--scenario", choices=("fresh", "recovery", "all"), default="all")
    args = parser.parse_args(argv)
    command = [args.docker] + (["--context", args.context] if args.context else [])
    # Never let a developer's ambient Compose configuration enter the fixture.
    env = {
        k: v
        for k, v in os.environ.items()
        if k in ("PATH", "HOME", "DOCKER_HOST", "DOCKER_CONFIG", "XDG_RUNTIME_DIR", "WSL_INTEROP")
    }

    def docker(*parts, timeout=120):
        result = subprocess.run(
            command + list(parts), capture_output=True, env=env, timeout=timeout
        )
        if result.returncode:
            diagnostic = ROOT / ".verification" / "public-failure.log"
            diagnostic.parent.mkdir(mode=0o700, exist_ok=True)
            with open(diagnostic, "wb") as stream:
                os.chmod(diagnostic, 0o600)
                stream.write(result.stderr)
            raise RuntimeError("Disposable Docker operation failed: " + parts[0])
        return result.stdout + (result.stderr if parts[0] == "logs" else b"")

    project = "qbitbot-public-test-" + uuid.uuid4().hex[:12]
    image = project + ":candidate"
    checks = []
    failure = None
    with tempfile.TemporaryDirectory(prefix="qbitbot-fresh-") as directory:
        root = Path(directory)
        try:
            export_checkout(root)
            bot, config = fresh(docker, root, project, image, checks)
            if args.scenario in ("recovery", "all"):
                recovery(docker, root, project, image, bot, config, checks)
        except Exception as error:
            failure = (
                type(error).__name__ + ": " + str(error)
                if isinstance(error, (RuntimeError, ValueError))
                else type(error).__name__
            )
        finally:
            for owned in (project + "-only", project):
                try:
                    cleanup_project(docker, owned)
                except Exception:
                    failure = "Scoped resource cleanup failed"
            try:
                for owned_image in (project + ":original-public", image):
                    if docker("image", "ls", "-q", owned_image).strip():
                        docker("image", "rm", owned_image)
            except Exception:
                failure = "Scoped image cleanup failed"
    if failure:
        print("FAIL " + failure)
        return 1
    checks.append("scoped cleanup")
    print(json.dumps({"checks": checks, "status": "passed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
