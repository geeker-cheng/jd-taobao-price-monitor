from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from ..matching import shop_matches, title_matches
from ..models import PriceConfidence, Quote
from .base import PriceSource


SEARCH_URL = "https://v3.api.haodanku.com/supersearch"
DETAIL_URL = "https://v3.api.haodanku.com/item_detail"
TIMEOUT = (6, 12)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick(item: dict, *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def _float(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _find_goods(obj: Any) -> list[dict]:
    found: list[dict] = []
    if isinstance(obj, dict):
        keys = set(obj)
        if keys & {"itemid", "item_id"} and keys & {"itemtitle", "title"}:
            found.append(obj)
        for value in obj.values():
            found.extend(_find_goods(value))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(_find_goods(value))
    return found


class HaodankuSource(PriceSource):
    name = "haodanku"

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None):
        self.api_key = (api_key if api_key is not None else os.getenv("HAODANKU_API_KEY", "")).strip()
        self.session = session or requests.Session()

    def _quote(self, product: dict, status: str, **kwargs) -> Quote:
        return Quote(
            product_id=product["id"],
            platform=product["platform"],
            status=status,
            source=self.name,
            checked_at=_now(),
            canonical_sku=(product.get("identifiers") or {}).get("sku_id"),
            **kwargs,
        )

    def _search(self, keyword: str) -> list[dict]:
        response = self.session.get(
            SEARCH_URL,
            params={
                "apikey": self.api_key,
                "keyword": keyword,
                "min_id": 1,
                "back": 50,
            },
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or body.get("code") != 1:
            raise RuntimeError(f"Haodanku search failed: {body}")
        return _find_goods(body)

    def _detail(self, item_id: str) -> dict:
        response = self.session.get(
            DETAIL_URL,
            params={"apikey": self.api_key, "itemid": item_id},
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or body.get("code") != 1:
            raise RuntimeError(f"Haodanku detail failed: {body}")
        data = body.get("data")
        if not isinstance(data, dict):
            raise RuntimeError("Haodanku detail returned no data object")
        return data

    def fetch(self, product: dict) -> Quote:
        if not self.api_key:
            return self._quote(
                product,
                "CONFIG_REQUIRED",
                detail={"required_secret": "HAODANKU_API_KEY"},
            )

        keywords = (product.get("source") or {}).get("search_keywords") or []
        candidates: list[dict] = []
        errors: list[str] = []

        for keyword in keywords:
            try:
                for item in self._search(str(keyword)):
                    title = _pick(item, "itemtitle", "title")
                    shop = _pick(item, "shopname", "shop_name")
                    if title_matches(title, product) and shop_matches(shop, product):
                        candidates.append(item)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

        # Deduplicate logical product-page results. Haodanku item IDs can be opaque
        # and have changed across separate searches, so do not use the opaque ID as
        # the only identity signal during discovery.
        logical: dict[tuple, dict] = {}
        for item in candidates:
            key = (
                str(_pick(item, "itemtitle", "title") or "").strip(),
                str(_pick(item, "shopname", "shop_name") or "").strip(),
                str(_pick(item, "itemprice", "price") or ""),
                str(_pick(item, "itemendprice", "end_price") or ""),
            )
            logical.setdefault(key, item)

        if not logical:
            return self._quote(
                product,
                "NO_MATCH" if not errors else "SOURCE_ERROR",
                detail={"errors": errors[:5]},
            )

        if len(logical) > 1:
            return self._quote(
                product,
                "AMBIGUOUS_SOURCE_MAPPING",
                detail={
                    "candidate_count": len(logical),
                    "candidates": [
                        {
                            "title": _pick(x, "itemtitle", "title"),
                            "shop": _pick(x, "shopname", "shop_name"),
                            "price": _pick(x, "itemprice", "price"),
                            "effective_price": _pick(x, "itemendprice", "end_price"),
                        }
                        for x in list(logical.values())[:10]
                    ],
                    "errors": errors[:5],
                },
            )

        item = next(iter(logical.values()))
        item_id = str(_pick(item, "itemid", "item_id") or "")
        try:
            detail = self._detail(item_id)
        except Exception as exc:
            return self._quote(
                product,
                "SOURCE_ERROR",
                detail={"error": f"{type(exc).__name__}: {exc}"},
            )

        title = _pick(detail, "itemtitle", "title")
        shop = _pick(detail, "shopname", "shop_name")
        if not title_matches(title, product) or not shop_matches(shop, product):
            return self._quote(
                product,
                "VALIDATION_FAILED",
                title=title,
                shop=shop,
                source_product_id=item_id,
            )

        return self._quote(
            product,
            "OK",
            title=title,
            shop=shop,
            price=_float(_pick(detail, "itemprice", "price")),
            effective_price=_float(_pick(detail, "itemendprice", "end_price")),
            coupon=_float(_pick(detail, "couponmoney", "coupon_price")),
            confidence=PriceConfidence.PRODUCT_PAGE_PRICE.value,
            source_product_id=item_id,
            detail={
                "price_scope": "product_page",
                "variant_verified": False,
                "note": "Haodanku detail does not expose enough SKU attributes to prove the requested variant.",
            },
        )
