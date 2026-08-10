from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from ..matching import jd_self_operated, shop_matches, title_matches
from ..models import PriceConfidence, Quote
from .base import PriceSource


BASE_URL = "https://appapi.maishou88.com"
SEARCH_PATH = "/api/v1/homepage/searchList"
DETAIL_PATH = "/api/v3/goods/detail"
TIMEOUT = (6, 12)
HEADERS = {
    "Accept": "application/json",
    "Referer": "https://hnbc018.kuaizhan.com/",
    "User-Agent": "Mozilla/5.0 AppleWebKit/537 Chrome/143 Safari/537",
}


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


def _looks_like_goods(item: Any) -> bool:
    return isinstance(item, dict) and bool(
        set(item) & {"goodsId", "title", "goodsName", "actualPrice", "shopName"}
    )


def _find_goods_list(obj: Any) -> list[dict]:
    if isinstance(obj, list):
        if obj and any(_looks_like_goods(x) for x in obj):
            return [x for x in obj if isinstance(x, dict)]
        for value in obj:
            found = _find_goods_list(value)
            if found:
                return found
    elif isinstance(obj, dict):
        for value in obj.values():
            found = _find_goods_list(value)
            if found:
                return found
    return []


class MaishouSource(PriceSource):
    name = "maishou"

    def __init__(
        self,
        invite_code: str | None = None,
        session: requests.Session | None = None,
    ):
        # Intentionally no public/referral fallback in production code.
        self.invite_code = (
            invite_code if invite_code is not None else os.getenv("MAISHOU_INVITE_CODE", "")
        ).strip()
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

    def _detail(self, goods_id: str) -> dict:
        payload = {
            "goodsId": goods_id,
            "sourceType": "2",
            "inviteCode": self.invite_code,
            "supplierCode": "",
            "activityId": "",
            "isShare": "1",
            "token": "",
            "keyword": "",
            "usageScene": 5,
        }
        response = self.session.post(
            BASE_URL + DETAIL_PATH,
            headers=HEADERS,
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        data = body.get("data") if isinstance(body, dict) else None
        if not isinstance(data, dict) or not data:
            raise RuntimeError(f"Maishou detail failed: {body}")
        return data

    def _search(self, keyword: str) -> list[dict]:
        payload = {
            "keyword": keyword,
            "sourceType": "2",
            "page": "1",
            "pageSize": "20",
            "inviteCode": self.invite_code,
        }
        response = self.session.post(
            BASE_URL + SEARCH_PATH,
            headers=HEADERS,
            data=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict) or body.get("status") != "success":
            raise RuntimeError(f"Maishou search failed: {body}")
        return _find_goods_list(body)

    def _detail_to_quote(
        self,
        product: dict,
        detail: dict,
        *,
        exact_mapping: bool,
    ) -> Quote:
        title = _pick(detail, "title", "goodsName")
        shop = _pick(detail, "shopName")
        if (
            not title_matches(title, product)
            or not shop_matches(shop, product)
            or not jd_self_operated(detail)
        ):
            return self._quote(
                product,
                "VALIDATION_FAILED",
                title=title,
                shop=shop,
                source_product_id=_pick(detail, "goodsId"),
            )

        return self._quote(
            product,
            "OK",
            title=title,
            shop=shop,
            price=_float(_pick(detail, "actualPrice", "price")),
            effective_price=_float(_pick(detail, "actualPrice", "price")),
            original_price=_float(_pick(detail, "originalPrice")),
            coupon=_float(_pick(detail, "couponPrice")),
            confidence=(
                PriceConfidence.EXACT_SKU_PRICE.value
                if exact_mapping
                else PriceConfidence.UNVERIFIED.value
            ),
            source_product_id=_pick(detail, "goodsId"),
            detail={
                "goods_id_b": _pick(detail, "jdGoodsIdB", "goodsIdB"),
                "self_operated": jd_self_operated(detail),
                "provider_mapping_verified": exact_mapping,
            },
        )

    def fetch(self, product: dict) -> Quote:
        if not self.invite_code:
            return self._quote(
                product,
                "CONFIG_REQUIRED",
                detail={"required_secret": "MAISHOU_INVITE_CODE"},
            )

        source_cfg = product.get("source") or {}
        mapping = source_cfg.get("mapping") or {}
        mapped_goods_id = mapping.get("provider_goods_id")
        mapping_verified = bool(mapping.get("verified"))

        if mapped_goods_id and mapping_verified:
            try:
                detail = self._detail(str(mapped_goods_id))
            except Exception as exc:
                return self._quote(
                    product,
                    "SOURCE_ERROR",
                    detail={"error": f"{type(exc).__name__}: {exc}"},
                )
            return self._detail_to_quote(product, detail, exact_mapping=True)

        keywords = source_cfg.get("search_keywords") or []
        raw_candidates: list[dict] = []
        errors: list[str] = []
        for keyword in keywords:
            try:
                for item in self._search(str(keyword)):
                    title = _pick(item, "title", "goodsName")
                    shop = _pick(item, "shopName")
                    if title_matches(title, product) and shop_matches(shop, product):
                        raw_candidates.append(item)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")

        if not raw_candidates:
            return self._quote(
                product,
                "NO_MATCH" if not errors else "SOURCE_ERROR",
                detail={"errors": errors[:5]},
            )

        # Maishou may return several provider entities for the same human-facing
        # JD product with different promotional prices. Do not choose the cheapest.
        # Detail each candidate and require a single provider mapping.
        detail_candidates: dict[str, dict] = {}
        for item in raw_candidates[:10]:
            goods_id = str(_pick(item, "goodsId", "id", "goods_id") or "")
            if not goods_id:
                continue
            try:
                detail = self._detail(goods_id)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
                continue
            if (
                title_matches(_pick(detail, "title", "goodsName"), product)
                and shop_matches(_pick(detail, "shopName"), product)
                and jd_self_operated(detail)
            ):
                stable_id = str(_pick(detail, "jdGoodsIdB", "goodsIdB", "goodsId") or "")
                if stable_id:
                    detail_candidates[stable_id] = detail

        if not detail_candidates:
            return self._quote(
                product,
                "VALIDATION_FAILED" if not errors else "SOURCE_ERROR",
                detail={"errors": errors[:5]},
            )

        if len(detail_candidates) != 1:
            return self._quote(
                product,
                "AMBIGUOUS_SOURCE_MAPPING",
                confidence=PriceConfidence.UNVERIFIED.value,
                detail={
                    "canonical_sku": (product.get("identifiers") or {}).get("sku_id"),
                    "candidate_count": len(detail_candidates),
                    "candidates": [
                        {
                            "goods_id_b": key,
                            "goods_id": _pick(value, "goodsId"),
                            "title": _pick(value, "title"),
                            "shop": _pick(value, "shopName"),
                            "price": _float(_pick(value, "actualPrice")),
                        }
                        for key, value in detail_candidates.items()
                    ],
                    "reason": "Multiple Maishou provider entities match; exact canonical JD SKU mapping has not been verified.",
                    "errors": errors[:5],
                },
            )

        detail = next(iter(detail_candidates.values()))
        # A unique search result is still not promoted to exact-SKU confidence
        # until its provider goods ID is explicitly verified and pinned in config.
        return self._detail_to_quote(product, detail, exact_mapping=False)
