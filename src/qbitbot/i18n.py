"""Explicit, per-render translation without a process-global active language."""

import json
from pathlib import Path
from typing import Literal

Language = Literal["en", "ru"]
CATALOGS = {
    language: json.loads((Path(__file__).parent / "locales" / f"{language}.json").read_text())
    for language in ("en", "ru")
}


def normalize_language(code: str | None) -> Language:
    return "ru" if isinstance(code, str) and code.lower().split("-")[0] == "ru" else "en"


def plural_form(language: Language, count: int) -> str:
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise ValueError("Count must be a nonnegative integer")
    if language != "ru":
        return "one" if count == 1 else "other"
    if 11 <= count % 100 <= 14:
        return "many"
    if count % 10 == 1:
        return "one"
    if 2 <= count % 10 <= 4:
        return "few"
    return "many"


def tr(key: str, language: Language, *, count: int | None = None, **values: object) -> str:
    language = normalize_language(language)
    if key not in CATALOGS[language]:
        language = "en"
    template = CATALOGS[language][key]
    if isinstance(template, dict):
        if count is None:
            raise ValueError("Plural message requires count")
        template = template[plural_form(language, count)]
    if count is not None:
        values["count"] = count
    return template.format(**values)
