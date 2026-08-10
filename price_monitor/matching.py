from __future__ import annotations

import re
from typing import Any


def compact(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"[\s\-_—–·/]+", "", text)


def contains_any(text: str, terms: list[str]) -> bool:
    c = compact(text)
    return any(compact(term) in c for term in terms)


def title_matches(title: str | None, product: dict) -> bool:
    if not title:
        return False
    cfg = product.get("match", {})
    value = compact(title)

    for group in cfg.get("required_title_groups", []):
        if not any(compact(term) in value for term in group):
            return False

    for term in cfg.get("excluded_title_terms", []):
        if compact(term) in value:
            return False

    return True


def shop_matches(shop: str | None, product: dict) -> bool:
    if not shop:
        return False
    value = compact(shop)
    allowed = product.get("shops", {}).get("allowed", [])
    return any(compact(item) in value or value in compact(item) for item in allowed)


def jd_self_operated(detail: dict) -> bool:
    shop = compact(detail.get("shopName"))
    tags = detail.get("tagList") or []
    tag_text = compact(" ".join(str(x) for x in tags))
    shop_type = detail.get("shopType")
    return "自营" in shop or "自营" in tag_text or shop_type == 1
