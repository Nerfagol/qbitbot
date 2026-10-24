from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def config(name="compose.yaml"):
    return yaml.safe_load((ROOT / name).read_text())


def test_stack_separates_services_and_state():
    cfg = config()
    assert set(cfg["services"]) == {"bot", "qbittorrent", "jackett"}
    assert set(cfg["volumes"]) == {"bot-state", "qbit-config", "jackett-config"}
    bot = cfg["services"]["bot"]
    assert bot["volumes"] == ["bot-state:/state"]
    assert all(v["condition"] == "service_healthy" for v in bot["depends_on"].values())
    for name, service in cfg["services"].items():
        assert "container_name" not in service and "network_mode" not in service
        if name != "bot":
            assert "env_file" not in service
            dockerfile = ROOT / service["build"]["dockerfile"]
            assert "@sha256:" in dockerfile.read_text().splitlines()[1]
            assert not service.get("read_only")
            assert not service.get("cap_drop")
            assert not any("PASS" in key or "TOKEN" in key for key in service["environment"])


def test_bot_only_never_starts_bundled_dependencies():
    cfg = config("compose.bot-only.yaml")
    assert set(cfg["services"]) == {"bot"}
    bot = cfg["services"]["bot"]
    assert not bot.get("depends_on")
    assert "QBIT_URL" not in bot["environment"]
    assert bot["env_file"] == ["bot.env"]
    assert bot["volumes"] == ["bot-state:/state"]


def test_web_interfaces_default_to_loopback_and_peer_ports_match():
    cfg = config()
    qbit = cfg["services"]["qbittorrent"]
    assert (
        qbit["ports"][0]
        == "${WEB_BIND_ADDRESS:-127.0.0.1}:${QBIT_WEBUI_PORT:-8080}:${QBIT_WEBUI_PORT:-8080}"
    )
    assert qbit["environment"]["WEBUI_PORT"] == "${QBIT_WEBUI_PORT:-8080}"
    assert qbit["ports"][1:] == [
        "${TORRENT_PORT:-6881}:${TORRENT_PORT:-6881}/tcp",
        "${TORRENT_PORT:-6881}:${TORRENT_PORT:-6881}/udp",
    ]
    assert cfg["services"]["jackett"]["ports"] == [
        "${WEB_BIND_ADDRESS:-127.0.0.1}:${JACKETT_WEBUI_PORT:-9117}:9117"
    ]
    assert cfg["services"]["jackett"]["environment"]["AUTO_UPDATE"] == "false"
    assert qbit["volumes"][1]["target"] == "/downloads"
    assert qbit["volumes"][1]["type"] == "bind"


def test_both_bot_modes_enforce_unprivileged_resource_bounded_runtime():
    for name in ("compose.yaml", "compose.bot-only.yaml"):
        bot = config(name)["services"]["bot"]
        assert bot["user"] == "1000:1000"
        assert bot["read_only"] is True
        assert bot["cap_drop"] == ["ALL"]
        assert bot["security_opt"] == ["no-new-privileges:true"]
        assert bot["mem_limit"] == "256m"
        assert bot["cpus"] == 1.0
        assert bot["pids_limit"] == 128
        assert bot["tmpfs"] == ["/tmp:rw,noexec,nosuid,size=32m,mode=1777"]
