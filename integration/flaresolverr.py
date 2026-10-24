"""Verify optional browser rendering and strict TLS using owned internal fixtures."""

import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--context")
    parser.add_argument("--image", required=True)
    args = parser.parse_args()
    docker = [args.docker]
    if args.context:
        docker.extend(["--context", args.context])
    name = "qbitbot-flare-smoke-" + uuid.uuid4().hex[:12]
    label = "qbitbot.verification=" + name
    created = []

    def run(*command, check=True):
        result = subprocess.run(docker + list(command), capture_output=True, text=True, timeout=120)
        if check and result.returncode:
            raise RuntimeError(result.stderr or result.stdout)
        return result.stdout.strip() if result.returncode == 0 else ""

    def request(url):
        payload = json.dumps({"cmd": "request.get", "url": url, "maxTimeout": 30000})
        code = (
            "import urllib.request,urllib.error\n"
            "r=urllib.request.Request('http://127.0.0.1:8191/v1',data="
            + repr(payload.encode())
            + ",headers={'Content-Type':'application/json'})\n"
            "try:\n response=urllib.request.urlopen(r,timeout=60)\n"
            "except urllib.error.HTTPError as error:\n response=error\n"
            "print(response.read().decode())"
        )
        return json.loads(run("exec", name, "python", "-c", code))

    with tempfile.TemporaryDirectory(prefix="qbitbot-flare-") as directory:
        cert = Path(directory) / "cert.pem"
        key = Path(directory) / "key.pem"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(key),
                "-out",
                str(cert),
                "-days",
                "1",
                "-subj",
                "/CN=fixture",
                "-addext",
                "subjectAltName=DNS:fixture",
            ],
            capture_output=True,
            check=True,
            timeout=30,
        )
        fixture = (
            "from http.server import BaseHTTPRequestHandler,HTTPServer\n"
            "import ssl,threading,pathlib\n"
            "class H(BaseHTTPRequestHandler):\n"
            " def do_GET(self):\n"
            "  self.send_response(200);self.send_header('Content-Type','text/html');"
            "self.end_headers();self.wfile.write(b'<html><body><div id=proof>pending</div>"
            '<script>document.getElementById("proof").textContent="browser-js-executed"'
            "</script></body></html>')\n"
            "pathlib.Path('/tmp/cert.pem').write_text(" + repr(cert.read_text()) + ")\n"
            "pathlib.Path('/tmp/key.pem').write_text(" + repr(key.read_text()) + ")\n"
            "tls=HTTPServer(('0.0.0.0',8443),H);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);"
            "ctx.load_cert_chain('/tmp/cert.pem','/tmp/key.pem');"
            "tls.socket=ctx.wrap_socket(tls.socket,server_side=True);"
            "threading.Thread(target=tls.serve_forever,daemon=True).start()\n"
            "HTTPServer(('0.0.0.0',8080),H).serve_forever()"
        )
        try:
            run("network", "create", "--internal", "--label", label, name)
            created.append(("network", name))
            run(
                "run",
                "-d",
                "--name",
                name + "-fixture",
                "--network",
                name,
                "--network-alias",
                "fixture",
                "--label",
                label,
                "--read-only",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=16m,mode=1777",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--entrypoint",
                "python",
                args.image,
                "-c",
                fixture,
            )
            created.append(("container", name + "-fixture"))
            run(
                "run",
                "-d",
                "--name",
                name,
                "--network",
                name,
                "--label",
                label,
                "--user",
                "1000:1000",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--memory",
                "1g",
                "--cpus",
                "1.5",
                "--pids-limit",
                "256",
                "--shm-size",
                "256m",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=512m,mode=1777",
                "--tmpfs",
                "/app/.config:rw,noexec,nosuid,nodev,size=64m,uid=1000,gid=1000,mode=0700",
                "--tmpfs",
                "/config:rw,noexec,nosuid,nodev,size=16m,uid=1000,gid=1000,mode=0700",
                "-e",
                "LOG_LEVEL=warning",
                "-e",
                "LOG_HTML=false",
                args.image,
            )
            created.append(("container", name))
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                ready = run(
                    "exec",
                    name,
                    "python",
                    "-c",
                    "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8191/',timeout=2).status)",
                    check=False,
                )
                if ready == "200":
                    break
                time.sleep(2)
            else:
                raise RuntimeError("FlareSolverr readiness timed out")
            response = request("http://fixture:8080/")
            assert response["status"] == "ok", response
            assert response["solution"]["status"] == 200, response
            assert '<div id="proof">browser-js-executed</div>' in response["solution"]["response"]
            response = request("https://fixture:8443/")
            assert response["status"] == "error", response
            print("PASS: Chromium rendered JavaScript and rejected selfsigned HTTPS")
        finally:
            failures = []
            for kind, owned in reversed(created):
                command = (
                    ("rm", "-f", "-v", owned) if kind == "container" else ("network", "rm", owned)
                )
                try:
                    run(*command)
                except (RuntimeError, subprocess.TimeoutExpired):
                    failures.append(owned)
            if failures:
                raise RuntimeError("Owned fixture cleanup failed: " + ", ".join(failures))


if __name__ == "__main__":
    main()
