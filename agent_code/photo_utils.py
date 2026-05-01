from __future__ import annotations

import re


def normalize_string_list(values: list[str] | None, limit: int = 10) -> list[str]:
    if not isinstance(values, list):
        return []

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = str(item).strip().lstrip("-").strip()
        if not text:
            continue
        key = re.sub(r"\s+", "", text.lower())
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
        if len(normalized) >= limit:
            break
    return normalized
