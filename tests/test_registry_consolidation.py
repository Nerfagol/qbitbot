"""Consolidation must preserve released content and refuse unsafe cleanup."""

import importlib

import pytest

SHA = "a" * 40
REPOSITORY = "example/bot"
PREFIX = "ghcr.io/example/bot"
COMPONENTS = ("bot", "qbittorrent", "jackett", "flaresolverr")


def migration():
    return importlib.import_module("integration.consolidate_registry")


def lock():
    images = {}
    for i, component in enumerate(COMPONENTS, 1):
        digest = "sha256:" + str(i) * 64
        name = PREFIX + ("-" + component if component != "bot" else "")
        images[component] = {
            "ref": name + "@" + digest,
            "digest": digest,
            "tag": name + ":0.4.0",
            "config_digest": "sha256:" + "9" * 64,
        }
    return {"version": "0.4.0", "revision": SHA, "platform": "linux/amd64", "images": images}


class Registry:
    def __init__(self, plan):
        self.refs = {p["source"]: p["digest"] for p in plan}
        self.copies = []

    def tags(self, prefix):
        return {ref.split(":")[-1] for ref in self.refs if ref.startswith(prefix + ":")}

    def digest(self, ref):
        return self.refs[ref]

    def copy(self, source, target):
        self.copies.append((source, target))
        self.refs[target] = self.refs[source]

    def graph(self, source):
        return {self.refs[source]}


def plan():
    return migration().migration_plan(lock(), REPOSITORY, SHA)


def test_version_lock_and_tags_keep_all_components_in_one_repository():
    result = plan()
    assert result[0]["targets"] == [PREFIX + ":0.4.0", PREFIX + ":sha-" + SHA]
    assert result[2]["targets"] == [PREFIX + ":jackett-0.4.0", PREFIX + ":jackett-sha-" + SHA]
    assert all(t.split(":", 1)[0] == PREFIX for p in result for t in p["targets"])


def test_cleanup_context_requires_the_repository_owner():
    with pytest.raises(ValueError):
        migration().validate_context("Nerfagol/qbitbot", "refs/heads/main", SHA, "cleanup", "other")


@pytest.mark.parametrize("change", ["source", "revision", "components"])
def test_invalid_or_foreign_release_lock_is_rejected(change):
    data = lock()
    if change == "source":
        data["images"]["jackett"]["ref"] = "ghcr.io/foreign/image@sha256:" + "3" * 64
    elif change == "revision":
        data["revision"] = "b" * 40
    else:
        data["images"].pop("bot")
    with pytest.raises(ValueError):
        migration().migration_plan(data, REPOSITORY, SHA)


def test_conflicting_target_stops_before_any_copy():
    records = plan()
    registry = Registry(records)
    registry.refs[records[-1]["targets"][0]] = "sha256:" + "0" * 64
    with pytest.raises(ValueError):
        migration().copy_images(records, registry)
    assert registry.copies == []


def test_partial_migration_resumes_without_replacing_existing_equal_tags():
    records = plan()
    registry = Registry(records)
    registry.refs[records[0]["targets"][0]] = records[0]["digest"]
    migration().copy_images(records, registry)
    assert len(registry.copies) == 7
    assert all(registry.refs[t] == p["digest"] for p in records for t in p["targets"])
    migration().copy_images(records, registry)
    assert len(registry.copies) == 7


def test_copy_verifies_the_result_digest():
    records = plan()
    registry = Registry(records)

    def corrupt(source, target):
        registry.refs[target] = "sha256:" + "0" * 64

    registry.copy = corrupt
    with pytest.raises(ValueError):
        migration().copy_images(records, registry)


@pytest.mark.parametrize("bad", ["target", "legacy_tag", "legacy_manifest"])
def test_cleanup_rejects_unknown_data_or_bad_targets_before_any_deletion(bad):
    records = plan()
    registry = Registry(records)
    migration().copy_images(records, registry)
    versions = {
        p["component"]: [
            {"name": p["digest"], "metadata": {"container": {"tags": ["0.4.0", "sha-" + SHA]}}}
        ]
        for p in records[1:]
    }
    if bad == "target":
        registry.refs.pop(records[0]["targets"][0])
    elif bad == "legacy_tag":
        versions["flaresolverr"][0]["metadata"]["container"]["tags"].append("older-release")
    else:
        versions["flaresolverr"][0]["name"] = "sha256:" + "0" * 64
    deleted = []
    with pytest.raises((ValueError, KeyError)):
        migration().cleanup_legacy(records, registry, lambda c: versions[c], deleted.append)
    assert deleted == []


def test_explicit_cleanup_deletes_only_the_three_verified_legacy_packages():
    records = plan()
    registry = Registry(records)
    migration().copy_images(records, registry)
    deleted = []
    migration().cleanup_legacy(
        records,
        registry,
        lambda c: [
            {
                "name": next(p["digest"] for p in records if p["component"] == c),
                "metadata": {"container": {"tags": ["0.4.0", "sha-" + SHA]}},
            }
        ],
        deleted.append,
    )
    assert deleted == ["qbittorrent", "jackett", "flaresolverr"]
