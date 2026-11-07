"""Copy the released 0.4.0 images into one package; cleanup is separately opt-in."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from integration.registry_release import COMPONENTS, api, component_tags, wait_for_checks

ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"sha256:[a-f0-9]{64}")


def migration_plan(lock, repository, tag_revision):
    if (
        lock.get("version") != "0.4.0"
        or lock.get("revision") != tag_revision
        or not re.fullmatch(r"[a-f0-9]{40}", tag_revision)
        or lock.get("platform") != "linux/amd64"
        or set(lock.get("images", {})) != set(COMPONENTS)
        or not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", repository)
    ):
        raise ValueError("Invalid released image lock")
    prefix = "ghcr.io/" + repository.lower()
    result = []
    for component in COMPONENTS:
        image = lock["images"][component]
        legacy = prefix + ("-" + component if component != "bot" else "")
        digest = image.get("digest", "")
        if (
            not DIGEST.fullmatch(digest)
            or not DIGEST.fullmatch(image.get("config_digest", ""))
            or image.get("ref") != legacy + "@" + digest
            or image.get("tag") != legacy + ":0.4.0"
        ):
            raise ValueError("Image lock references an unexpected source")
        result.append(
            {
                "component": component,
                "source": image["ref"],
                "digest": digest,
                "targets": [
                    prefix + ":" + tag for tag in component_tags(component, "0.4.0", tag_revision)
                ],
                "legacy_tags": {"0.4.0", "sha-" + tag_revision},
            }
        )
    return result


def verify_targets(plan, registry):
    for item in plan:
        for target in item["targets"]:
            if registry.digest(target) != item["digest"]:
                raise ValueError("Canonical target digest differs from the released image")


def copy_images(plan, registry):
    prefix = plan[0]["targets"][0].rsplit(":", 1)[0]
    known = registry.tags(prefix)
    pending = []
    # Check every collision/source before performing any registry writes.
    for item in plan:
        for target in item["targets"]:
            if target.rsplit(":", 1)[1] in known:
                if registry.digest(target) != item["digest"]:
                    raise ValueError("Refusing to overwrite a different published image")
            else:
                pending.append((item, target))
    for item, _ in pending:
        if registry.digest(item["source"]) != item["digest"]:
            raise ValueError("Released source digest mismatch")
    for item, target in pending:
        registry.copy(item["source"], target)
        if registry.digest(target) != item["digest"]:
            raise ValueError("Registry copy did not preserve the released digest")
    verify_targets(plan, registry)


def cleanup_legacy(plan, registry, versions_for, delete):
    verify_targets(plan, registry)
    pending = []
    for item in plan:
        component = item["component"]
        if component == "bot":
            continue
        versions = versions_for(component)
        if versions is None:  # Already removed during an earlier approved attempt.
            continue
        graph = registry.graph(item["targets"][0])
        if item["digest"] not in graph:
            raise ValueError("Canonical manifest graph changed")
        for version in versions:
            tags = set(version.get("metadata", {}).get("container", {}).get("tags", []))
            if version.get("name") not in graph or not tags <= item["legacy_tags"]:
                raise ValueError(
                    "Legacy package contains an unknown version or tag; cleanup stopped"
                )
        pending.append(component)
    # No package is deleted until every target and legacy package is verified.
    for component in pending:
        delete(component)


class Registry:
    def run(self, *parts):
        result = subprocess.run(["regctl", *parts], capture_output=True, timeout=300)
        if result.returncode:
            raise RuntimeError("Registry operation failed; no unsafe fallback attempted")
        return result.stdout

    def tags(self, prefix):
        return set(json.loads(self.run("tag", "ls", prefix, "--format", "{{json .Tags}}")))

    def digest(self, ref):
        value = self.run("manifest", "digest", ref).decode().strip()
        if not DIGEST.fullmatch(value):
            raise ValueError("Registry returned an invalid digest")
        return value

    def copy(self, source, target):
        self.run("image", "copy", source, target)

    def graph(self, ref):
        prefix = ref.rsplit(":", 1)[0]
        pending = [self.digest(ref)]
        seen = set()
        while pending:
            digest = pending.pop()
            if digest in seen:
                continue
            if not DIGEST.fullmatch(digest) or len(seen) >= 100:
                raise ValueError("Unexpected manifest graph")
            body = self.run("manifest", "get", prefix + "@" + digest, "--format", "raw-body")
            if "sha256:" + hashlib.sha256(body).hexdigest() != digest:
                raise ValueError("Manifest body digest mismatch")
            pending.extend(x["digest"] for x in json.loads(body).get("manifests", []))
            seen.add(digest)
        return seen


def validate_context(repository, ref, revision, operation, actor):
    if (
        repository != "Nerfagol/qbitbot"
        or ref != "refs/heads/main"
        or not re.fullmatch(r"[a-f0-9]{40}", revision)
        or operation == "cleanup"
        and actor.lower() != repository.split("/")[0].lower()
    ):
        raise ValueError("Use owning main branch; legacy cleanup additionally requires its owner")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("copy", "cleanup"))
    args = parser.parse_args()
    repository = os.environ["GITHUB_REPOSITORY"]
    revision = os.environ["GITHUB_SHA"]
    validate_context(
        repository, os.environ["GITHUB_REF"], revision, args.operation, os.environ["GITHUB_ACTOR"]
    )
    wait_for_checks(repository, revision)
    tag_revision = subprocess.check_output(
        ["git", "rev-parse", "v0.4.0^{commit}"],
        cwd=ROOT,
        text=True,
    ).strip()
    lock = json.loads((ROOT / "deploy/registry-0.4.0-legacy.json").read_text())
    plan = migration_plan(lock, repository, tag_revision)
    registry = Registry()
    if args.operation == "copy":
        copy_images(plan, registry)
        for item in plan:
            print("Verified " + item["targets"][0] + " " + item["digest"])
        return
    owner, name = repository.lower().split("/")

    def versions_for(component):
        path = f"users/{owner}/packages/container/{name}-{component}"
        info = api(path, missing_ok=True)
        if info == []:
            return None
        if info.get("repository", {}).get("full_name") != repository:
            raise ValueError("Legacy package is not linked to the expected repository")
        return [v for page in api(path + "/versions?per_page=100", paginate=True) for v in page]

    def delete(component):
        path = f"users/{owner}/packages/container/{name}-{component}"
        result = subprocess.run(
            ["gh", "api", "--method", "DELETE", path],
            capture_output=True,
            timeout=60,
        )
        if result.returncode:
            raise RuntimeError("Verified legacy package deletion failed")
        print("Deleted legacy package " + name + "-" + component)

    cleanup_legacy(plan, registry, versions_for, delete)


if __name__ == "__main__":
    main()
