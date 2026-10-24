"""Resolve public Compose entry points and the optional solver overlay with synthetic settings; print no secrets."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def check(docker="docker", context=None):
    command = [docker] + (["--context", context] if context else [])
    env = {k: v for k, v in os.environ.items() if not k.startswith("COMPOSE_")}
    for key in (
        "PUID",
        "PGID",
        "TZ",
        "DOWNLOADS_DIR",
        "WEB_BIND_ADDRESS",
        "QBIT_WEBUI_PORT",
        "JACKETT_WEBUI_PORT",
        "TORRENT_PORT",
    ):
        env.pop(key, None)
    with tempfile.TemporaryDirectory(prefix="qbitbot-config-") as directory:
        root = Path(directory)
        for name in (
            "compose.yaml",
            "deploy/compose.bot-only.yaml",
            "deploy/compose.flaresolverr.yaml",
        ):
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, root / name)
        (root / ".env").write_text("QBIT_WEBUI_PORT=18080\nDOWNLOADS_DIR=./downloads with spaces\n")
        for blank in (True, False):
            values = (
                ""
                if blank
                else "BOT_TOKEN=123456:SYNTHETIC\nALLOWED_USERS=101\nQBIT_PASS='a $literal #value \\'quote\\''\nQBIT_URL=http://external.invalid:8080\nJACKETT_TORZNAB_URL=http://external.invalid:9117/api\n"
            )
            (root / "bot.env").write_text(values)
            for name in (
                "compose.yaml",
                "deploy/compose.bot-only.yaml",
                "deploy/compose.flaresolverr.yaml",
            ):
                result = subprocess.run(
                    command
                    + [
                        "compose",
                        "--project-directory",
                        str(root),
                        "-f",
                        str(
                            root
                            / (
                                "compose.yaml"
                                if name == "deploy/compose.flaresolverr.yaml"
                                else name
                            )
                        ),
                    ]
                    + (
                        ["-f", str(root / name)]
                        if name == "deploy/compose.flaresolverr.yaml"
                        else []
                    )
                    + [
                        "config",
                        "--format",
                        "json",
                    ],
                    env=env,
                    capture_output=True,
                    timeout=30,
                )
                if result.returncode:
                    raise RuntimeError("Compose configuration validation failed; output withheld")
                cfg = json.loads(result.stdout)
                project = root.name.lower()
                assert cfg["name"] == project
                assert cfg["volumes"]["bot-state"]["name"] == project + "_bot-state"
                bot = cfg["services"]["bot"]
                assert (
                    bot["build"]["context"].replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
                    == root.name
                )
                assert bot["build"]["dockerfile"] == "deploy/docker/bot.Dockerfile"
                assert bot["user"] == "1000:1000"
                assert bot["read_only"] is True
                assert bot["cap_drop"] == ["ALL"]
                assert "no-new-privileges:true" in bot["security_opt"]
                assert bot["mem_limit"] == "268435456"
                assert bot["pids_limit"] == 128
                assert bot["tmpfs"] == ["/tmp:rw,noexec,nosuid,size=32m,mode=1777"]
                if not blank:
                    assert bot["environment"]["QBIT_PASS"] in (
                        "a $literal #value 'quote'",
                        "a $$literal #value 'quote'",
                    )
                if name != "deploy/compose.bot-only.yaml":
                    expected = {"bot", "qbittorrent", "jackett"}
                    if name == "deploy/compose.flaresolverr.yaml":
                        expected.add("flaresolverr")
                        solver = cfg["services"]["flaresolverr"]
                        assert not solver.get("ports")
                        assert not solver.get("volumes")
                        assert solver["user"] == "1000:1000"
                        assert solver["read_only"] is True
                        assert solver["cap_drop"] == ["ALL"]
                        assert "no-new-privileges:true" in solver["security_opt"]
                        assert solver["mem_limit"] == "1073741824"
                        assert solver["pids_limit"] == 256
                        assert set(solver["networks"]) == {"solver"}
                        assert "solver" in cfg["services"]["jackett"]["networks"]
                        assert "solver" not in bot["networks"]
                        assert "solver" not in cfg["services"]["qbittorrent"]["networks"]
                        assert cfg["networks"]["solver"]["enable_ipv6"] is False
                    assert set(cfg["services"]) == expected
                    qbit = cfg["services"]["qbittorrent"]
                    assert qbit["ports"][0]["host_ip"] == "127.0.0.1"
                    assert qbit["ports"][0]["target"] == 18080
                    assert qbit["environment"]["WEBUI_PORT"] == "18080"
                    assert bot["environment"]["QBIT_URL"] == "http://qbittorrent:18080"
                    assert qbit["volumes"][1]["source"].endswith("downloads with spaces")
                    assert "QBIT_PASS" not in qbit["environment"]
                else:
                    assert set(cfg["services"]) == {"bot"}
                    assert not bot.get("depends_on")
                    if not blank:
                        assert bot["environment"]["QBIT_URL"] == "http://external.invalid:8080"
        # Exercise Docker's real directory-context filtering, not just a hand-picked
        # tar archive (stdin archives bypass the CLI's .dockerignore processing).
        allowed = [
            "src/qbitbot/__init__.py",
            "src/qbitbot/cli/__init__.py",
            "src/qbitbot/clients/qbittorrent.py",
            "src/qbitbot/clients/jackett.py",
            "src/qbitbot/locales/en.json",
            "requirements/runtime.lock",
            "requirements/build.lock",
            "pyproject.toml",
            "README.md",
            "docs/licenses/THIRD_PARTY_NOTICES.md",
            "deploy/docker/flaresolverr/LICENSE",
            "deploy/docker/flaresolverr/strict_tls.py",
        ]
        forbidden = [
            "bot.env",
            ".env",
            "config/bot.env.example",
            "requirements/dev.lock",
            "src/qbitbot/private.env",
            "src/qbitbot/cli/private.env",
            "src/qbitbot/clients/private.env",
            "src/qbitbot/locales/private.env",
            "docs/development/agent/memory.md",
            "docs/archive/private-canary.txt",
            "deploy/private.env",
            "deploy/docker/flaresolverr/private.env",
            ".git/private-canary",
            "state/private-canary",
            "backups/private-canary",
        ]
        (root / ".dockerignore").write_bytes((ROOT / ".dockerignore").read_bytes())
        for path in allowed + forbidden:
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            # Preserve the existing synthetic env files for the delivery check below.
            if not target.exists():
                target.write_text("synthetic context canary\n")
        proof = (
            "from pathlib import Path; root=Path('/context'); "
            f"assert all((root/p).is_file() for p in {allowed!r}); "
            f"assert all(not (root/p).exists() for p in {forbidden!r})"
        )
        canary = "qbitbot-context-" + uuid.uuid4().hex[:12]
        recipe = root / "deploy/docker/context-check.Dockerfile"
        recipe.parent.mkdir(parents=True, exist_ok=True)
        recipe.write_text(
            "FROM python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d\n"
            + "COPY . /context\nRUN "
            + json.dumps(["python", "-c", proof])
            + "\n"
        )
        try:
            result = subprocess.run(
                command
                + [
                    "build",
                    "--network",
                    "none",
                    "--label",
                    "qbitbot.verification=" + canary,
                    "-t",
                    canary,
                    "-f",
                    "deploy/docker/context-check.Dockerfile",
                    ".",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                timeout=120,
            )
            if result.returncode:
                raise RuntimeError("Docker directory-context allowlist verification failed")
        finally:
            subprocess.run(command + ["image", "rm", canary], capture_output=True, timeout=30)

        # Compose JSON can escape dollar signs. Verify the delivered bytes as well.
        name = "qbitbot-env-" + uuid.uuid4().hex[:12]
        probe = {
            "services": {
                "probe": {
                    "image": "python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d",
                    "network_mode": "none",
                    "env_file": ["bot.env"],
                    "command": [
                        "python",
                        "-c",
                        "import os; assert os.environ['QBIT_PASS'] == \"a $literal #value 'quote'\"",
                    ],
                }
            }
        }
        # Escape the inline command for Compose; the env_file remains single-quoted.
        probe["services"]["probe"]["command"][-1] = probe["services"]["probe"]["command"][
            -1
        ].replace("$", "$$")
        (root / "probe.json").write_text(json.dumps(probe))
        try:
            result = subprocess.run(
                command
                + [
                    "compose",
                    "-p",
                    name,
                    "--project-directory",
                    str(root),
                    "-f",
                    str(root / "probe.json"),
                    "run",
                    "--rm",
                    "--no-deps",
                    "--name",
                    name,
                    "probe",
                ],
                env=env,
                capture_output=True,
                timeout=60,
            )
            if result.returncode:
                raise RuntimeError("Synthetic environment delivery check failed")
        finally:
            subprocess.run(command + ["rm", "-f", name], capture_output=True, timeout=30)
    print(
        "PASS bundled/bot-only/solver Compose: synthetic config, bindings, solver isolation and Docker context exclusions"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--context")
    args = parser.parse_args()
    check(args.docker, args.context)
