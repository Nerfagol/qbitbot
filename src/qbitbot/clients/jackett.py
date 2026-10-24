"""Jackett JSON/Torznab transport and parsing with bounded trusted-origin reads."""

from dataclasses import dataclass
import json
import re
from typing import Dict, List
from urllib.parse import urlsplit, urlunsplit
import xml.etree.ElementTree as ET

from qbitbot.http_safety import MAX_SEARCH_BYTES, open_response, read_limited
from qbitbot.search_results import SearchResults

RESULTS_LIMIT = 50


@dataclass(frozen=True, repr=False)
class JackettConfig:
    url: str
    key: str
    timeout: int = 20


def torznab_items(xml_text: str) -> List[Dict]:
    """
    Robust Torznab parser:
    - supports namespaced or non-namespaced torznab:attr
    - prefers magneturl attr; falls back to <link>
    """
    root = ET.fromstring(xml_text)
    if (
        root.tag != "rss"
        or root.find("channel") is None
        or any(element.tag.rsplit("}", 1)[-1] == "error" for element in root.iter())
    ):
        raise ValueError("Search response unavailable")
    out: List[Dict] = []

    # channel/item is standard for torznab
    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip() or "Untitled"
        link = (item.findtext("link") or "").strip() or None

        try:
            size = int(item.findtext("size") or "")
        except ValueError:
            size = None
        seeders = None
        magnet = None

        # Match any namespace: {anything}attr
        for attr in item.findall(".//{*}attr"):
            name = attr.attrib.get("name")
            val = attr.attrib.get("value")
            if not name or val is None:
                continue
            if name == "size":
                try:
                    size = int(val)
                except Exception:
                    pass
            elif name == "seeders":
                try:
                    seeders = int(val)
                except Exception:
                    pass
            elif name == "magneturl":
                magnet = val

        url = magnet or link
        if not url:
            continue

        out.append(
            {
                "title": title,
                "url": url,
                "size": size,
                "seeders": seeders,
            }
        )
        source = (item.findtext("jackettindexer") or "").strip()
        if source:
            out[-1]["source"] = source

    return out


def jackett_response(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("Results"), list):
        raise ValueError("Search response unavailable")
    items = []
    for row in payload["Results"]:
        if not isinstance(row, dict):
            raise ValueError("Search response unavailable")
        url = row.get("MagnetUri") or row.get("Link")
        if not isinstance(url, str) or not url.startswith(("magnet:?", "http://", "https://")):
            continue
        items.append(
            {
                "title": str(row.get("Title") or "Untitled"),
                "url": url,
                "size": row.get("Size") if type(row.get("Size")) is int else None,
                "seeders": row.get("Seeders") if type(row.get("Seeders")) is int else None,
                "source": str(row.get("Tracker") or ""),
            }
        )
    if payload["Results"] and not items:
        raise ValueError("Search response unavailable")
    indexers = payload.get("Indexers")
    statuses = (
        [row.get("Status") if isinstance(row, dict) else None for row in indexers]
        if isinstance(indexers, list)
        else None
    )
    return SearchResults(items, statuses=statuses)


class JackettClient:
    def __init__(self, config):
        self.config = config

    def search(self, query: str, limit: int = RESULTS_LIMIT) -> List[Dict]:
        parts = urlsplit(self.config.url)
        # Jackett's manual-search response includes per-query indexer statuses.
        # Custom Torznab URLs retain their existing query semantics, with unknown coverage.
        if not parts.query and re.fullmatch(
            r".*/api/v2\.0/indexers/[^/]+/results/torznab/api/?", parts.path
        ):
            path = parts.path.rstrip("/")[: -len("/torznab/api")]
            url = urlunsplit(parts._replace(path=path, fragment=""))
            with open_response(
                "GET",
                url,
                trusted_url=self.config.url,
                allow_external_redirects=False,
                params={"apikey": self.config.key, "query": query},
                timeout=(5, self.config.timeout),
            ) as r:
                r.raise_for_status()
                return jackett_response(json.loads(read_limited(r, MAX_SEARCH_BYTES)))
        params = {"apikey": self.config.key, "q": query, "limit": str(limit)}
        with open_response(
            "GET",
            self.config.url,
            trusted_url=self.config.url,
            allow_external_redirects=False,
            params=params,
            timeout=(5, self.config.timeout),
        ) as r:
            r.raise_for_status()
            return SearchResults(torznab_items(read_limited(r, MAX_SEARCH_BYTES)))
