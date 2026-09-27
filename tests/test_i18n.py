import json
from pathlib import Path
from string import Formatter

import pytest

import i18n
from i18n import normalize_language, plural_form, tr


@pytest.mark.parametrize(
    "code,want", [(None, "en"), ("de", "en"), ("ru", "ru"), ("ru-RU", "ru"), ("EN-us", "en")]
)
def test_language_fallback(code, want):
    assert normalize_language(code) == want


@pytest.mark.parametrize(
    "count,want",
    [
        (0, "many"),
        (1, "one"),
        (2, "few"),
        (5, "many"),
        (11, "many"),
        (12, "many"),
        (14, "many"),
        (21, "one"),
        (22, "few"),
        (25, "many"),
        (101, "one"),
        (111, "many"),
    ],
)
def test_russian_number_forms(count, want):
    assert plural_form("ru", count) == want
    assert plural_form("en", count) == ("one" if count == 1 else "other")


def test_catalogs_match_and_templates_use_same_fields():
    root = Path(__file__).resolve().parents[1] / "locales"
    en = json.loads((root / "en.json").read_text())
    ru = json.loads((root / "ru.json").read_text())
    assert set(en) == set(ru)

    def fields(value):
        strings = value.values() if isinstance(value, dict) else [value]
        sets = [{key for _, key, _, _ in Formatter().parse(s) if key is not None} for s in strings]
        assert all(s == sets[0] for s in sets)
        return sets[0]

    for key in en:
        assert fields(en[key]) == fields(ru[key]), key


def test_untrusted_values_are_never_reinterpreted():
    value = "<b>{private.name}</b> & 😀"
    assert tr("search.query", "en", query=value) == "Search: " + value
    assert tr("search.query", "ru", query=value) == "Поиск: " + value
    with pytest.raises(KeyError):
        tr("missing.key", "en")
    with pytest.raises(KeyError):
        tr("search.query", "en")


def test_missing_russian_key_falls_back_to_english(monkeypatch):
    monkeypatch.setitem(i18n.CATALOGS, "ru", {})
    assert tr("search.query", "ru", query="x") == "Search: x"
    assert tr("units.items", "ru", count=2) == "2 items"
