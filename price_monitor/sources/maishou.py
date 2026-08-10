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
# Public third-party referral/invite code used as a reproducible default.
# Users can override it with MAISHOU_INVITE_CODE. See README disclosure.
DEFAULT_PUBLIC_INVITE_CODE = "6110440"

# Maishou reachability from GitHub-hosted runners is not stable. Keep each
# request short so a transient regional routing problem cannot consume most
# of the workflow's hard timeout.
TIMEOUT = (2.5, 5)
DISCOVERY_DETAIL_LIMIT = 3

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
        configured_code = (
            invite_code if invite_code is not None else os.getenv("MAISHOU_INVITE_CODE", "")
        )
        self.invite_code = (configured_code or DEFAULT_PUBLIC_INVITE_CODE).strip()
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

    def _valid_detail(self, product: dict, detail: dict) -> bool:
        return (
            title_matches(_pick(detail, "title", "goodsName"), product)
            and shop_matches(_pick(detail, "shopName"), product)
            and jd_self_operated(detail)
        )

    def _stable_id(self, detail: dict) -> str:
        # jdGoodsIdB is treated as a Maishou-side stable-ish identity only.
        # It is NOT presented as a native public JD SKU.
        return str(_pick(detail, "jdGoodsIdB", "goodsIdB", "goodsId") or "")

    def _candidate_summary(self, key: str, detail: dict) -> dict:
        return {
            "goods_id_b": key,
            "goods_id": _pick(detail, "goodsId"),
            "title": _pick(detail, "title"),
            "shop": _pick(detail, "shopName"),
            "price": _float(_pick(detail, "actualPrice")),
        }

    def _ambiguous_quote(
        self,
        product: dict,
        candidates: dict[str, dict],
        *,
        errors: list[str] | None = None,
        candidate_source: str,
    ) -> Quote:
        return self._quote(
            product,
            "AMBIGUOUS_SOURCE_MAPPING",
            confidence=PriceConfidence.UNVERIFIED.value,
            detail={
                "canonical_sku": (product.get("identifiers") or {}).get("sku_id"),
                "candidate_count": len(candidates),
                "candidate_source": candidate_source,
                "candidates": [
                    self._candidate_summary(key, value)
                    for key, value in candidates.items()
                ],
                "reason": (
                    "Multiple Maishou provider entities match; exact canonical "
                    "JD SKU mapping has not been verified."
                ),
                "errors": (errors or [])[:5],
            },
        )

    def _detail_to_quote(
        self,
        product: dict,
        detail: dict,
        *,
        exact_mapping: bool,
    ) -> Quote:
        title = _pick(detail, "title", "goodsName")
        shop = _pick(detail, "shopName")
        if not self._valid_detail(product, detail):
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

    def _probe_known_candidates(
        self,
        product: dict,
        known_candidates: list[dict],
    ) -> tuple[dict[str, dict], list[str], list[str]]:
        """Return (valid_details, transport_errors, stale_or_invalid_errors)."""
        valid: dict[str, dict] = {}
        transport_errors: list[str] = []
        other_errors: list[str] = []

        for candidate in known_candidates:
            goods_id = str(candidate.get("goods_id") or "")
            expected_stable_id = str(candidate.get("goods_id_b") or "")
            if not goods_id:
                continue
            try:
                detail = self._detail(goods_id)
            except requests.RequestException as exc:
                transport_errors.append(
                    f"{goods_id}: {type(exc).__name__}: {exc}"
                )
                continue
            except Exception as exc:
                other_errors.append(
                    f"{goods_id}: {type(exc).__name__}: {exc}"
                )
                continue

            if not self._valid_detail(product, detail):
                other_errors.append(f"{goods_id}: detail validation failed")
                continue

            stable_id = self._stable_id(detail)
            if expected_stable_id and stable_id != expected_stable_id:
                other_errors.append(
                    f"{goods_id}: stable id changed from "
                    f"{expected_stable_id} to {stable_id or '<empty>'}"
                )
                continue
            if stable_id:
                valid[stable_id] = detail

        return valid, transport_errors, other_errors

    def _discover_candidates(
        self,
        product: dict,
        keyword: str,
    ) -> tuple[dict[str, dict], list[str], bool]:
        """Return (valid_details, errors, transport_failed)."""
        errors: list[str] = []
        try:
            raw = self._search(keyword)
        except requests.RequestException as exc:
            return {}, [f"{type(exc).__name__}: {exc}"], True
        except Exception as exc:
            return {}, [f"{type(exc).__name__}: {exc}"], False

        raw_candidates: list[dict] = []
        for item in raw:
            title = _pick(item, "title", "goodsName")
            shop = _pick(item, "shopName")
            if title_matches(title, product) and shop_matches(shop, product):
                raw_candidates.append(item)

        details: dict[str, dict] = {}
        for item in raw_candidates[:DISCOVERY_DETAIL_LIMIT]:
            goods_id = str(_pick(item, "goodsId", "id", "goods_id") or "")
            if not goods_id:
                continue
            try:
                detail = self._detail(goods_id)
            except requests.RequestException as exc:
                errors.append(f"{goods_id}: {type(exc).__name__}: {exc}")
                continue
            except Exception as exc:
                errors.append(f"{goods_id}: {type(exc).__name__}: {exc}")
                continue
            if self._valid_detail(product, detail):
                stable_id = self._stable_id(detail)
                if stable_id:
                    details[stable_id] = detail

        return details, errors, False

    def _discovery_keyword(self, source_cfg: dict) -> str:
        discovery_keyword = source_cfg.get("discovery_keyword")
        if not discovery_keyword:
            keywords = source_cfg.get("search_keywords") or []
            discovery_keyword = keywords[-1] if keywords else ""
        return str(discovery_keyword or "")

    def _fetch_verified_stable_mapping(
        self,
        product: dict,
        source_cfg: dict,
        mapped_stable_id: str,
    ) -> Quote:
        """Fetch a mapping pinned to jdGoodsIdB rather than volatile goodsId.

        Full Maishou goodsId strings have changed prefixes between live runs while
        jdGoodsIdB remained stable. A matching known candidate is therefore only
        a request handle; the returned detail must still report mapped_stable_id.
        """
        known_candidates = source_cfg.get("known_candidates") or []
        candidate = None
        if isinstance(known_candidates, list):
            candidate = next(
                (
                    item
                    for item in known_candidates
                    if str(item.get("goods_id_b") or "") == mapped_stable_id
                ),
                None,
            )

        recovery_errors: list[str] = []
        if candidate:
            goods_id = str(candidate.get("goods_id") or "")
            if goods_id:
                try:
                    detail = self._detail(goods_id)
                except requests.RequestException as exc:
                    # Do not convert transport uncertainty into identity recovery:
                    # fail fast and let the next scheduled run retry.
                    return self._quote(
                        product,
                        "SOURCE_ERROR",
                        confidence=PriceConfidence.UNVERIFIED.value,
                        detail={
                            "stage": "verified_mapping_detail",
                            "mapped_goods_id_b": mapped_stable_id,
                            "error": f"{type(exc).__name__}: {exc}",
                        },
                    )
                except Exception as exc:
                    recovery_errors.append(
                        f"{goods_id}: {type(exc).__name__}: {exc}"
                    )
                else:
                    if (
                        self._valid_detail(product, detail)
                        and self._stable_id(detail) == mapped_stable_id
                    ):
                        return self._detail_to_quote(
                            product, detail, exact_mapping=True
                        )
                    recovery_errors.append(
                        f"{goods_id}: mapped stable identity validation failed"
                    )

        # If the cached request handle became stale for a non-network reason,
        # perform exactly one bounded discovery query and recover only the same
        # previously verified stable identity.
        keyword = self._discovery_keyword(source_cfg)
        if keyword:
            discovered, errors, transport_failed = self._discover_candidates(
                product, keyword
            )
            recovery_errors.extend(errors)
            if transport_failed:
                return self._quote(
                    product,
                    "SOURCE_ERROR",
                    confidence=PriceConfidence.UNVERIFIED.value,
                    detail={
                        "stage": "verified_mapping_discovery",
                        "mapped_goods_id_b": mapped_stable_id,
                        "errors": recovery_errors[:5],
                    },
                )
            detail = discovered.get(mapped_stable_id)
            if detail is not None:
                return self._detail_to_quote(
                    product, detail, exact_mapping=True
                )
            observed = [
                self._candidate_summary(key, value)
                for key, value in discovered.items()
            ]
        else:
            observed = []

        return self._quote(
            product,
            "MAPPED_ENTITY_NOT_FOUND",
            confidence=PriceConfidence.UNVERIFIED.value,
            detail={
                "mapped_goods_id_b": mapped_stable_id,
                "reason": (
                    "The verified Maishou stable identity could not be recovered. "
                    "No other candidate was substituted."
                ),
                "observed_candidates": observed,
                "errors": recovery_errors[:5],
            },
        )

    def fetch(self, product: dict) -> Quote:
        source_cfg = product.get("source") or {}
        mapping = source_cfg.get("mapping") or {}
        mapped_goods_id = mapping.get("provider_goods_id")
        mapped_stable_id = str(mapping.get("provider_goods_id_b") or "")
        mapping_verified = bool(mapping.get("verified"))

        if mapping_verified and mapped_stable_id:
            return self._fetch_verified_stable_mapping(
                product, source_cfg, mapped_stable_id
            )

        # Legacy/full-ID mapping support for forks that already pinned a Maishou
        # goodsId. New mappings should prefer provider_goods_id_b because the
        # full goodsId has proven volatile between live runs.
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

        # First probe provider IDs previously observed for this exact human-facing
        # product. They are cache/discovery hints only, never proof of canonical
        # JD SKU identity.
        known_candidates = source_cfg.get("known_candidates") or []
        known_valid: dict[str, dict] = {}
        known_other_errors: list[str] = []
        if isinstance(known_candidates, list) and known_candidates:
            known_valid, transport_errors, known_other_errors = (
                self._probe_known_candidates(product, known_candidates)
            )
            # Any transport uncertainty means we could not check the complete
            # candidate set. Do not treat the one reachable candidate as unique.
            if transport_errors:
                return self._quote(
                    product,
                    "SOURCE_ERROR",
                    confidence=PriceConfidence.UNVERIFIED.value,
                    detail={
                        "stage": "known_candidate_detail",
                        "errors": (transport_errors + known_other_errors)[:5],
                        "known_candidate_count": len(known_candidates),
                    },
                )
            if len(known_valid) > 1:
                return self._ambiguous_quote(
                    product,
                    known_valid,
                    errors=known_other_errors,
                    candidate_source="known_candidates",
                )

        # Only one discovery query is used. Earlier smoke tests showed the more
        # specific AD653C/SKU queries returning no JD goods, while this query
        # returned the target family. This avoids four serial network waits.
        discovery_keyword = self._discovery_keyword(source_cfg)

        if not discovery_keyword:
            if len(known_valid) == 1:
                detail = next(iter(known_valid.values()))
                return self._detail_to_quote(product, detail, exact_mapping=False)
            return self._quote(
                product,
                "NO_MATCH",
                detail={"reason": "No known candidate or discovery keyword configured."},
            )

        discovered, discovery_errors, transport_failed = self._discover_candidates(
            product, discovery_keyword
        )
        if transport_failed:
            return self._quote(
                product,
                "SOURCE_ERROR",
                confidence=PriceConfidence.UNVERIFIED.value,
                detail={
                    "stage": "discovery_search",
                    "errors": (known_other_errors + discovery_errors)[:5],
                },
            )

        merged = dict(known_valid)
        merged.update(discovered)

        if not merged:
            return self._quote(
                product,
                "VALIDATION_FAILED" if discovery_errors else "NO_MATCH",
                detail={"errors": (known_other_errors + discovery_errors)[:5]},
            )

        if len(merged) != 1:
            return self._ambiguous_quote(
                product,
                merged,
                errors=known_other_errors + discovery_errors,
                candidate_source="known_plus_discovery",
            )

        detail = next(iter(merged.values()))
        # A unique currently reachable provider entity is still not promoted to
        # exact-SKU confidence until its Maishou → canonical JD SKU mapping is
        # explicitly verified and pinned in config.
        return self._detail_to_quote(product, detail, exact_mapping=False)
