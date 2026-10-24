"""Build, integration-test and rehearse rollback on disposable Docker resources.

Usage: python3 integration/run.py --docker docker [--context NAME]
All containers/networks/volumes are newly created and removed in finally.
No host directory or Docker socket is mounted; no ports are published.
"""

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QBIT_DOCKERFILE = "docker/qbittorrent.Dockerfile"


def archive(files):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w") as tar:
        for name, data in files.items():
            header = tarfile.TarInfo(name)
            header.size = len(data)
            # Public source and synthetic probes must be readable by UID 1000.
            header.mode = 0o644
            tar.addfile(header, io.BytesIO(data))
    return stream.getvalue()


def create_tracked(docker, registry, name, *parts, **kwargs):
    # Register intent before a daemon operation can succeed with a lost CLI reply.
    if name not in registry:
        registry.append(name)
    return docker(*parts, **kwargs)


def cleanup_resources(docker, containers, volumes, images, network, *, owner):
    errors = []
    actions = [("container", n, ("rm", "-f", n)) for n in reversed(containers)]
    actions += [("volume", n, ("volume", "rm", n)) for n in reversed(volumes)]
    if network:
        actions.append(("network", network, ("network", "rm", network)))
    actions += [("image", n, ("image", "rm", n)) for n in reversed(images)]
    seen = set()
    for kind, name, command in actions:
        if (kind, name) in seen:
            continue
        seen.add((kind, name))
        label = kind + " " + name
        try:
            template = (
                "{{json .Config.Labels}}" if kind in ("container", "image") else "{{json .Labels}}"
            )
            found = docker("inspect", "--type", kind, "--format", template, name, check=False)
            if found.returncode:
                if b"no such" in found.stderr.lower():
                    continue
                errors.append(label + ": ownership inspection failed")
                continue
            if (json.loads(found.stdout) or {}).get("qbitbot.verification") != owner:
                errors.append(label + ": ownership mismatch")
                continue
            if docker(*command, check=False).returncode:
                errors.append(label + ": nonzero exit")
        except Exception as error:
            errors.append(label + ": " + type(error).__name__)
    return errors


def run_ephemeral(docker, containers, name, *parts, check=True, timeout=120, owner=None):
    # Register the unique name before create: the daemon may finish an operation
    # even if its CLI times out. The parent's finally block can still remove it.
    create_tracked(
        docker,
        containers,
        name,
        "create",
        "--name",
        name,
        "--label",
        "qbitbot.verification=" + (owner or name),
        *parts,
    )
    result = docker("start", "--attach", name, check=False, timeout=timeout)
    state = docker("inspect", "--format", "{{json .State}}", name)
    state = json.loads(state.stdout)
    if state["Running"]:
        raise RuntimeError("Helper is still running after attached CLI exited: " + name)
    result.returncode = int(state["ExitCode"])
    docker("rm", name)
    containers.remove(name)
    if check and result.returncode:
        raise RuntimeError(
            "Helper failed: "
            + result.stderr.decode(errors="replace")
            + result.stdout.decode(errors="replace")
        )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--context")
    args = parser.parse_args()
    command = [args.docker] + (["--context", args.context] if args.context else [])

    def docker(*parts, stdin=None, check=True, timeout=120):
        result = subprocess.run(
            command + list(parts), input=stdin, capture_output=True, timeout=timeout
        )
        if check and result.returncode:
            # Docker/API test commands contain only synthetic configuration.
            raise RuntimeError(
                f"Docker {parts[0]} failed:\n"
                + result.stderr.decode(errors="replace")
                + result.stdout.decode(errors="replace")
            )
        return result

    def output(*parts, **kwargs):
        return docker(*parts, **kwargs).stdout.decode().strip()

    engine = output("info", "--format", "{{.OperatingSystem}}")
    prefix = "qbitbot-verify-" + uuid.uuid4().hex[:10]
    image = prefix + ":baseline"
    candidate = prefix + ":candidate"
    qbit_image = prefix + ":qbittorrent"
    network = prefix + "-net"
    containers, volumes, images = [], [], []
    network_created = False
    summary = {"engine": engine, "context": args.context, "resource_prefix": prefix, "checks": []}

    def ephemeral(*parts, **kwargs):
        name = prefix + "-helper-" + uuid.uuid4().hex[:8]
        return run_ephemeral(docker, containers, name, *parts, owner=prefix, **kwargs)

    def ephemeral_output(*parts, **kwargs):
        return ephemeral(*parts, **kwargs).stdout.decode().strip()

    def passed(label):
        print("PASS " + label, flush=True)
        summary["checks"].append(label)

    def volume(suffix):
        name = prefix + "-" + suffix
        create_tracked(
            docker,
            volumes,
            name,
            "volume",
            "create",
            "--label",
            "qbitbot.verification=" + prefix,
            name,
        )
        return name

    def run_container(name, *parts):
        create_tracked(
            docker,
            containers,
            name,
            "create",
            "--name",
            name,
            "--label",
            "qbitbot.verification=" + prefix,
            *parts,
        )
        docker("start", name)
        return name

    def wait_password(cid):
        started = output("inspect", "--format", "{{.State.StartedAt}}", cid)
        for _ in range(60):
            logs = docker("logs", "--since", started, "--tail", "100", cid)
            matches = re.findall(
                r"temporary password is provided for this session:\s*(\S+)",
                (logs.stdout + logs.stderr).decode(errors="replace"),
            )
            if matches:
                return matches[-1]
            time.sleep(0.5)
        raise RuntimeError("Disposable qBittorrent did not publish its temporary password")

    def probe(mode, password, data_volume):
        name = prefix + "-probe-" + mode
        cfg = {
            "BOT_TOKEN": "123456:SYNTHETIC_INTEGRATION_ONLY",
            "QBIT_URL": "http://qbittorrent:8080",
            "QBIT_USER": "admin",
            "QBIT_PASS": password,
            "QBIT_SAVEPATH": "/downloads",
            "PTB_USE_AIOHTTP": "0",
            "ALLOWED_USERS": "101",
            "WATCH_DB_PATH": "/state/watches.sqlite3",
            "JACKETT_TORZNAB_URL": "http://fixtures:8765/torznab",
            "JACKETT_API_KEY": "synthetic",
        }
        cid = name
        create_tracked(
            docker,
            containers,
            name,
            "create",
            "--name",
            name,
            "--label",
            "qbitbot.verification=" + prefix,
            "--network",
            network,
            "--network-alias",
            "fixtures",
            "--memory",
            "256m",
            "-v",
            data_volume + ":/downloads",
            "-v",
            state + ":/state",
            image,
            "python",
            "/tmp/probe.py",
            mode,
        )
        docker(
            "cp",
            "-",
            cid + ":/tmp",
            stdin=archive(
                {
                    "probe.py": (ROOT / "integration/probe.py").read_bytes(),
                    "verification-config.json": json.dumps(cfg).encode(),
                }
            ),
        )
        result = docker("start", "--attach", cid, timeout=90)
        code = output("inspect", "--format", "{{.State.ExitCode}}", cid)
        text = result.stdout.decode(errors="replace")
        print(text, end="", flush=True)
        assert code == "0", result.stderr.decode(errors="replace")
        summary["checks"].extend(line[5:] for line in text.splitlines() if line.startswith("PASS "))
        # Remove the network alias before the next probe.
        docker("rm", cid)
        containers.remove(cid)

    try:
        build = {
            n: (ROOT / n).read_bytes()
            for n in [
                "Dockerfile",
                "LICENSE",
                "THIRD_PARTY_NOTICES.md",
                ".dockerignore",
                "requirements.lock",
                *(
                    path.relative_to(ROOT).as_posix()
                    for pattern in ("*.py", "cli/*.py", "locales/*.json")
                    for path in sorted((ROOT / "qbitbot").glob(pattern))
                ),
            ]
        }
        create_tracked(
            docker,
            images,
            image,
            "build",
            "--label",
            "qbitbot.verification=" + prefix,
            "-t",
            image,
            "-",
            stdin=archive(build),
            timeout=300,
        )
        summary["bot_image_id"] = output("image", "inspect", "--format", "{{.Id}}", image)
        passed("bot container build with pinned runtime dependencies")
        smoke = ephemeral("--network", "none", image, check=False)
        assert smoke.returncode != 0 and b"ALLOWED_USERS:" in smoke.stderr
        passed("default entry point imports successfully and rejects missing credentials")
        hardened = [
            "--network",
            "none",
            "--read-only",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=32m,mode=1777",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--memory",
            "256m",
            "--cpus",
            "1",
            "--pids-limit",
            "128",
        ]
        private_state = volume("permissions")
        verify_runtime = """import os, sqlite3, ssl
from pathlib import Path
assert os.getuid()==os.getgid()==1000
assert Path('/state').stat().st_uid==1000
with sqlite3.connect('/state/smoke.sqlite3') as conn:
    conn.execute('CREATE TABLE smoke(n)')
Path('/tmp/smoke').write_text('temporary')
try:
    Path('/app/forbidden').write_text('fail')
except OSError:
    pass
else:
    raise AssertionError('root filesystem is writable')
status=Path('/proc/self/status').read_text()
assert 'CapEff:\\t0000000000000000' in status and 'NoNewPrivs:\\t1' in status
"""
        ephemeral(*hardened, "-v", private_state + ":/state", image, "python", "-c", verify_runtime)
        passed(
            "nonroot musl/SSL/SQLite runtime, read-only root, tmpfs, no capabilities and no privilege escalation"
        )
        old_state = volume("old-permissions")
        seed_permissions = """from pathlib import Path
p=Path('/legacy'); p.chmod(0o700)
(p/'watches.sqlite3').write_bytes(b'unchanged synthetic state')
(p/'snapshot').mkdir(mode=0o700)
(p/'snapshot'/'backup').write_bytes(b'unchanged synthetic backup')
"""
        ephemeral(
            "--network",
            "none",
            "--user",
            "0:0",
            "-v",
            old_state + ":/legacy",
            image,
            "python",
            "-c",
            seed_permissions,
        )
        ephemeral(
            *hardened,
            "--user",
            "0:0",
            "--cap-add",
            "CHOWN",
            "--cap-add",
            "DAC_OVERRIDE",
            "--cap-add",
            "FOWNER",
            "-v",
            old_state + ":/state",
            image,
            "python",
            "-m",
            "qbitbot.cli.state_permissions",
            "--offline",
        )
        check_permissions = """from pathlib import Path
p=Path('/state')
assert (p/'watches.sqlite3').read_bytes()==b'unchanged synthetic state'
assert (p/'snapshot'/'backup').read_bytes()==b'unchanged synthetic backup'
for path in [p,*p.rglob('*')]:
    assert path.stat().st_uid==path.stat().st_gid==1000
    assert path.stat().st_mode & 0o777 == (0o700 if path.is_dir() else 0o600)
(p/'postmigration').write_text('writable')
"""
        ephemeral(*hardened, "-v", old_state + ":/state", image, "python", "-c", check_permissions)
        passed(
            "explicit offline ownership migration preserves existing state/backup bytes and private permissions"
        )
        digest = ephemeral_output(
            "--network",
            "none",
            image,
            "python",
            "-c",
            "import hashlib; print(hashlib.sha256(open('/app/qbitbot/app.py','rb').read()).hexdigest())",
        )
        assert digest == hashlib.sha256((ROOT / "qbitbot/app.py").read_bytes()).hexdigest()
        passed("built source checksum matches current local source")
        create_tracked(
            docker,
            images,
            qbit_image,
            "build",
            "--label",
            "qbitbot.verification=" + prefix,
            "-t",
            qbit_image,
            "-f",
            QBIT_DOCKERFILE,
            "-",
            stdin=archive({QBIT_DOCKERFILE: (ROOT / QBIT_DOCKERFILE).read_bytes()}),
            timeout=300,
        )
        summary["qbit_image"] = qbit_image
        network_created = True
        output(
            "network", "create", "--internal", "--label", "qbitbot.verification=" + prefix, network
        )
        config, data, state = volume("config"), volume("data"), volume("state")
        qbit = run_container(
            prefix + "-qbit",
            "--network",
            network,
            "--network-alias",
            "qbittorrent",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "-e",
            "PUID=1000",
            "-e",
            "PGID=1000",
            "-e",
            "TZ=Etc/UTC",
            "-v",
            config + ":/config",
            "-v",
            data + ":/downloads",
            qbit_image,
        )
        password = wait_password(qbit)
        time.sleep(1)
        probe("suite", password, data)
        probe("watch-seed", password, data)
        probe("watch-restore", password, data)
        probe("watch-again", password, data)
        docker("stop", "--time", "10", qbit)
        probe("outage", password, data)
        docker("start", qbit)
        password = wait_password(qbit)
        time.sleep(1)
        probe("reconnect", password, data)

        # Isolated equivalent of the deployment writable application mount and protected backup.
        app, backup = volume("app"), volume("backup")
        init = """from pathlib import Path
import shutil, tarfile
p=Path('/release')
shutil.copytree('/app/qbitbot', p/'qbitbot')
(p/'bot.env').write_text('BOT_TOKEN=rollback-fixture\\nPTB_USE_AIOHTTP=0\\nALLOWED_USERS=101\\nQBIT_URL=http://qbit.invalid\\nQBIT_USER=test\\nQBIT_PASS=synthetic\\nJACKETT_TORZNAB_URL=http://jackett.invalid/api\\nJACKETT_API_KEY=synthetic\\n')
(p/'compose.yaml').write_text('services: {bot: {image: retained-baseline}}\\n')
with tarfile.open('/backup/app.tar','w') as t: t.add('/release',arcname='app')
Path('/backup/app.tar').chmod(0o600)
for base in ('/release', '/backup'):
    for path in [Path(base), *Path(base).rglob('*')]:
        shutil.chown(path, user=1000, group=1000)
"""
        ephemeral(
            "--network",
            "none",
            "-v",
            app + ":/release",
            "-v",
            backup + ":/backup",
            "--user",
            "0:0",
            image,
            "python",
            "-c",
            init,
        )
        check = """import hashlib
from qbitbot import app as b
assert b.BOT_TOKEN=='rollback-fixture'
print(hashlib.sha256(open('/app/qbitbot/app.py','rb').read()).hexdigest())
"""
        original = ephemeral_output(
            "--network", "none", "-v", app + ":/app", image, "python", "-c", check
        )
        assert original == digest
        create_tracked(
            docker,
            images,
            candidate,
            "build",
            "--label",
            "qbitbot.verification=" + prefix,
            "-t",
            candidate,
            "-",
            stdin=archive(
                {
                    "Dockerfile": f"FROM {image}\nUSER 0:0\nRUN echo candidate > /candidate-marker\nUSER 1000:1000\n".encode()
                }
            ),
        )
        assert (
            output("image", "inspect", "--format", "{{.Id}}", candidate) != summary["bot_image_id"]
        )
        ephemeral(
            "--network",
            "none",
            "-v",
            app + ":/app",
            candidate,
            "python",
            "-c",
            "from pathlib import Path; Path('/app/qbitbot/app.py').write_text('INVALID PYTHON !'); Path('/app/compose.yaml').write_text('broken candidate')",
        )
        broken = ephemeral(
            "--network",
            "none",
            "-v",
            app + ":/app",
            candidate,
            "python",
            "-c",
            check,
            check=False,
        )
        assert broken.returncode != 0 and b"SyntaxError" in broken.stderr
        passed("rollback rehearsal detects deliberately broken candidate startup")
        restore = """import tarfile
with tarfile.open('/backup/app.tar') as t: t.extractall('/restore',filter='data')
"""
        ephemeral(
            "--network",
            "none",
            "-v",
            app + ":/restore/app",
            "-v",
            backup + ":/backup:ro",
            image,
            "python",
            "-c",
            restore,
        )
        restored = ephemeral_output(
            "--network",
            "none",
            "-v",
            app + ":/app",
            image,
            "python",
            "-c",
            check
            + "\nassert open('/app/compose.yaml').read()=='services: {bot: {image: retained-baseline}}\\n'\n",
        )
        assert restored == digest
        passed("rollback restores source checksum, synthetic configuration and retained image")
        probe("reconnect", password, data)
        passed("application rollback leaves separate torrent storage intact")
        probe("watch-again", password, data)
        passed("application rollback leaves separate monitoring state intact")
        summary["completed"] = True
    finally:
        cleanup_errors = cleanup_resources(
            docker, containers, volumes, images, network if network_created else None, owner=prefix
        )
        summary["cleanup_errors"] = cleanup_errors
        (ROOT / ".verification").mkdir(exist_ok=True)
        (ROOT / ".verification/latest.json").write_text(json.dumps(summary, indent=2) + "\n")
        if cleanup_errors:
            raise RuntimeError("Cleanup incomplete: " + ", ".join(cleanup_errors))
        print("PASS disposable resources cleaned up", flush=True)


if __name__ == "__main__":
    main()
