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
            assert "@sha256:" in service["image"]
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
