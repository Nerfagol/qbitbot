"""Verify the real s6 oneshot with synthetic loopback HTTP and no external network."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid

PYTHON_IMAGE = "python:3.12.15-alpine3.24@sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d"
FIXTURE = r"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import json, time
counts = {}
class H(BaseHTTPRequestHandler):
    def log_message(self, *args): pass
    def do_GET(self):
        path = urlparse(self.path)
        if path.path == '/counts':
            body = json.dumps(counts).encode()
        elif path.path == '/api/v2.0/indexers':
            assert parse_qs(path.query) == {'apikey':['synthetic-key'], 'configured':['true']}
            body = b'[{"id":"fixture-a"},{"id":"fixture-b"}]'
        else:
            body = b'healthy'
        self.send_response(200); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        path = urlparse(self.path)
        assert parse_qs(path.query) == {'apikey':['synthetic-key']}
        assert path.path in ('/api/v2.0/indexers/fixture-a/test', '/api/v2.0/indexers/fixture-b/test')
        counts[path.path] = counts.get(path.path, 0) + 1
        time.sleep(3)
        self.send_response(204 if 'fixture-a' in path.path else 500)
        self.end_headers()
ThreadingHTTPServer(('127.0.0.1',9117), H).serve_forever()
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--context")
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    command = [args.docker] + (["--context", args.context] if args.context else [])
    owner = "qbitbot-jackett-startup-" + uuid.uuid4().hex[:12]
    fixture, jackett = owner + "-http", owner + "-s6"
    created = []

    def docker(*parts, check=True):
        result = subprocess.run(command + list(parts), capture_output=True, text=True, timeout=60)
        if check and result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result

    def counts():
        result = docker(
            "exec",
            fixture,
            "python",
            "-c",
            "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9117/counts').read().decode())",
        )
        return json.loads(result.stdout)

    def health():
        return (
            docker(
                "exec",
                jackett,
                "/usr/local/bin/qbitbot-jackett-startup",
                "health",
                check=False,
            ).returncode
            == 0
        )

    def wait_ready(expected):
        deadline = time.monotonic() + 45
        saw_pending = False
        while time.monotonic() < deadline:
            if health():
                assert counts() == expected
                assert saw_pending, "health did not wait for startup warm-up"
                return
            saw_pending = True
            time.sleep(0.3)
        raise RuntimeError("s6 warm-up did not complete")

    try:
        # Both containers share only a network-disabled namespace. No real
        # tracker, production service, host mount or published port is used.
        created.append(fixture)
        docker(
            "run",
            "-d",
            "--name",
            fixture,
            "--network",
            "none",
            "--label",
            "qbitbot.verification=" + owner,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--entrypoint",
            "python",
            PYTHON_IMAGE,
            "-c",
            FIXTURE,
        )
        created.append(jackett)
        docker(
            "create",
            "--name",
            jackett,
            "--network",
            "container:" + fixture,
            "--label",
            "qbitbot.verification=" + owner,
            "-e",
            "AUTO_UPDATE=false",
            "-e",
            "JACKETT_WARMUP_ON_START=1",
            args.image,
        )
        with tempfile.TemporaryDirectory(prefix=owner) as directory:
            path = Path(directory)
            (path / "Jackett").mkdir()
            (path / "Jackett/ServerConfig.json").write_text('{"APIKey":"synthetic-key"}')
            # Replace only the application process; preserve the image's native
            # s6 graph, readiness notification and actual warm-up hook.
            service = path / "run"
            service.write_text(
                "#!/usr/bin/with-contenv sh\n"
                'exec s6-notifyoncheck -d -n 30 -w 100 -c "nc -z localhost 9117" sleep 600\n'
            )
            service.chmod(0o755)
            docker("cp", str(path / "Jackett"), jackett + ":/config/")
            docker("cp", str(service), jackett + ":/etc/s6-overlay/s6-rc.d/svc-jackett/run")
        docker("start", jackett)
        expected = {"/api/v2.0/indexers/fixture-a/test": 1, "/api/v2.0/indexers/fixture-b/test": 1}
        wait_ready(expected)
        # Ordinary health polling and elapsed idle time must never trigger tests.
        for _ in range(3):
            assert health()
            time.sleep(1)
        assert counts() == expected
        docker("restart", "--time", "5", jackett)
        wait_ready({key: 2 for key in expected})
        logs = docker("logs", jackett).stdout
        assert logs.count("Jackett startup warm-up: finished (1/2 tests succeeded)") == 2
        assert "synthetic-key" not in logs
        print(
            "PASS native s6 readiness, failed-test no-retry, idle health and one warm-up per container restart"
        )
    finally:
        for name in reversed(created):
            found = docker("inspect", "--format", "{{json .Config.Labels}}", name, check=False)
            if found.returncode == 0:
                assert json.loads(found.stdout).get("qbitbot.verification") == owner
                docker("rm", "-f", "-v", name)


if __name__ == "__main__":
    main()
