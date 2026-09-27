"""Resolve both public Compose entry points with synthetic settings; print no secrets."""

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
        for name in ("compose.yaml", "compose.bot-only.yaml"):
            shutil.copyfile(ROOT / name, root / name)
        (root / ".env").write_text("QBIT_WEBUI_PORT=18080\nDOWNLOADS_DIR=./downloads with spaces\n")
        for blank in (True, False):
            values = (
                ""
                if blank
                else "BOT_TOKEN=123456:SYNTHETIC\nALLOWED_USERS=101\nQBIT_PASS='a $literal #value \\'quote\\''\nQBIT_URL=http://external.invalid:8080\nJACKETT_TORZNAB_URL=http://external.invalid:9117/api\n"
            )
            (root / "bot.env").write_text(values)
            for name in ("compose.yaml", "compose.bot-only.yaml"):
                result = subprocess.run(
                    command
                    + [
                        "compose",
                        "--project-directory",
                        str(root),
                        "-f",
                        str(root / name),
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
                bot = cfg["services"]["bot"]
                if not blank:
                    assert bot["environment"]["QBIT_PASS"] in (
                        "a $literal #value 'quote'",
                        "a $$literal #value 'quote'",
                    )
                if name == "compose.yaml":
                    assert set(cfg["services"]) == {"bot", "qbittorrent", "jackett"}
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
        # Compose JSON can escape dollar signs. Verify the delivered bytes as well.
        name = "qbitbot-env-" + uuid.uuid4().hex[:12]
        probe = {
            "services": {
                "probe": {
                    "image": "python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c",
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
        "PASS bundled/bot-only Compose: blank bootstrap, literal credentials, paths and port bindings"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--context")
    args = parser.parse_args()
    check(args.docker, args.context)
