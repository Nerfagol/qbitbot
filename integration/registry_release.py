"""Validate immutable registry releases and exact-commit CI before publication."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
COMPONENTS = ("bot", "qbittorrent", "jackett", "flaresolverr")
WORKFLOWS = {
    ".github/workflows/" + n + ".yml" for n in ("check", "containers", "security", "codeql")
}


def metadata(root, tag, revision, repository, *, ref_type="tag"):
    if ref_type != "tag":
        raise ValueError("Publication requires a tag, never a branch")
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag):
        raise ValueError("Run publication from a stable version tag")
    if not re.fullmatch(r"[a-f0-9]{40}", revision):
        raise ValueError("Expected a full source commit SHA")
    if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Invalid source repository")
    version = tag[1:]
    if tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"] != version:
        raise ValueError("Tag and package version differ")
    changelog = (root / "CHANGELOG.md").read_text()
    if not re.search(r"^## " + re.escape(version) + r" — \d{4}-\d{2}-\d{2}$", changelog, re.M):
        raise ValueError("Release needs a dated changelog entry")
    return {"version": version, "prefix": "ghcr.io/" + repository.lower(), "revision": revision}


def checks_passed(records, revision):
    latest = {}
    for record in records:
        path = record.get("path")
        if (
            path in WORKFLOWS
            and record.get("head_sha") == revision
            and record.get("head_branch") == "main"
            and record.get("event") == "push"
            and record.get("id", 0) > latest.get(path, {}).get("id", -1)
        ):
            latest[path] = record
    for record in latest.values():
        if record["status"] == "completed" and record["conclusion"] != "success":
            raise ValueError("A required workflow failed on this source commit")
    return latest.keys() == WORKFLOWS and all(
        r["status"] == "completed" and r["conclusion"] == "success" for r in latest.values()
    )


def check_available(versions, version):
    if any(version in v.get("metadata", {}).get("container", {}).get("tags", []) for v in versions):
        raise ValueError("Version image already exists; never overwrite a released version")


def api(path, *, missing_ok=False, paginate=False):
    command = ["gh", "api"] + (["--paginate", "--slurp"] if paginate else []) + [path]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    if result.returncode:
        if missing_ok and "(HTTP 404)" in result.stderr:
            return []
        raise RuntimeError("GitHub API check failed; publication stopped")
    return json.loads(result.stdout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("gate", "available"))
    args = parser.parse_args()
    repository = os.environ["GITHUB_REPOSITORY"]
    revision = os.environ["GITHUB_SHA"]
    values = metadata(
        ROOT,
        os.environ["GITHUB_REF_NAME"],
        revision,
        repository,
        ref_type=os.environ["GITHUB_REF_TYPE"],
    )
    if args.mode == "gate":
        deadline = time.monotonic() + 1200
        while True:
            data = api(
                f"repos/{repository}/actions/runs?head_sha={revision}&event=push&per_page=100"
            )
            if checks_passed(data["workflow_runs"], revision):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("Required exact-commit workflows did not finish in time")
            print("Waiting for required checks on the exact main source commit", flush=True)
            time.sleep(15)
        with open(os.environ["GITHUB_OUTPUT"], "a") as output:
            for key, value in values.items():
                output.write(f"{key}={value}\n")
        print("Release metadata and all four exact-commit workflows verified")
    else:
        owner, name = repository.lower().split("/")
        for component in COMPONENTS:
            package = name + ("-" + component if component != "bot" else "")
            pages = api(
                f"users/{owner}/packages/container/{package}/versions?per_page=100",
                missing_ok=True,
                paginate=True,
            )
            check_available([v for page in pages for v in page], values["version"])
        print("All version image tags are available")


if __name__ == "__main__":
    main()
