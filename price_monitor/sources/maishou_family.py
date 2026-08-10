from __future__ import annotations

import requests

from ..matching import shop_matches, title_matches
from ..models import PriceConfidence, Quote
from .maishou import MaishouSource as _BaseMaishouSource
from .maishou import _float, _pick


MAX_FAMILY_DETAIL_LIMIT = 8


class MaishouSource(_BaseMaishouSource):
    """Maishou adapter with an opt-in validated product-family selection mode.

    Normal products keep the original strict mapping behavior. A product can
    explicitly opt in with source.selection.mode=lowest_price when the user has
    declared several variants equivalent (for example, any accepted color of
    the same memory tier). Only candidates that pass the normal title, shop and
    JD self-operated validation are eligible.
    """

    @staticmethod
    def _family_selection(source_cfg: dict) -> bool:
        selection = source_cfg.get("selection") or {}
        return selection.get("mode") == "lowest_price"

    @staticmethod
    def _family_detail_limit(source_cfg: dict) -> int:
        value = source_cfg.get("discovery_detail_limit", 4)
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = 4
        return max(1, min(value, MAX_FAMILY_DETAIL_LIMIT))

    def _family_quote(self, product: dict, source_cfg: dict) -> Quote:
        keyword = self._discovery_keyword(source_cfg)
        if not keyword:
            return self._quote(
                product,
                "NO_MATCH",
                detail={"reason": "No discovery keyword configured for variant family."},
            )

        try:
            raw = self._search(keyword)
        except requests.RequestException as exc:
            return self._quote(
                product,
                "SOURCE_ERROR",
                confidence=PriceConfidence.UNVERIFIED.value,
                detail={"stage": "family_search", "error": f"{type(exc).__name__}: {exc}"},
            )
        except Exception as exc:
            return self._quote(
                product,
                "SOURCE_ERROR",
                confidence=PriceConfidence.UNVERIFIED.value,
                detail={"stage": "family_search", "error": f"{type(exc).__name__}: {exc}"},
            )

        raw_candidates: list[dict] = []
        for item in raw:
            title = _pick(item, "title", "goodsName")
            shop = _pick(item, "shopName")
            if not title_matches(title, product):
                continue
            # Some Maishou search responses omit shopName. Detail validation is
            # authoritative, so only reject here when a conflicting shop is known.
            if shop and not shop_matches(shop, product):
                continue
            raw_candidates.append(item)

        if not raw_candidates:
            return self._quote(
                product,
                "NO_MATCH",
                confidence=PriceConfidence.UNVERIFIED.value,
                detail={"stage": "family_search", "matched_search_candidates": 0},
            )

        valid: dict[str, dict] = {}
        errors: list[str] = []
        limit = self._family_detail_limit(source_cfg)
        for item in raw_candidates[:limit]:
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

            if not self._valid_detail(product, detail):
                continue
            stable_id = self._stable_id(detail)
            if stable_id:
                valid[stable_id] = detail

        priced: list[tuple[float, str, dict]] = []
        for stable_id, detail in valid.items():
            price = _float(_pick(detail, "actualPrice", "price"))
            if price is not None and price > 0:
                priced.append((price, stable_id, detail))

        if not priced:
            status = "SOURCE_ERROR" if errors else "VALIDATION_FAILED"
            return self._quote(
                product,
                status,
                confidence=PriceConfidence.UNVERIFIED.value,
                detail={
                    "stage": "family_detail",
                    "matched_search_candidates": len(raw_candidates),
                    "validated_candidates": len(valid),
                    "detail_errors": errors[:5],
                },
            )

        _, selected_stable_id, selected_detail = min(priced, key=lambda row: row[0])
        quote = self._detail_to_quote(product, selected_detail, exact_mapping=False)
        if quote.status != "OK":
            return quote

        # This is a user-approved variant family, not a pinned canonical SKU.
        # PRODUCT_PAGE_PRICE accurately conveys that the selected page/variant
        # title is validated while no single JD SKU mapping is being asserted.
        quote.confidence = PriceConfidence.PRODUCT_PAGE_PRICE.value
        quote.detail.update(
            {
                "selection_mode": "lowest_price",
                "selection_scope": (source_cfg.get("selection") or {}).get("scope"),
                "selected_goods_id_b": selected_stable_id,
                "validated_candidate_count": len(valid),
                "matched_search_candidate_count": len(raw_candidates),
                "detail_limit": limit,
                "partial_detail_errors": errors[:5],
            }
        )
        return quote

    def fetch(self, product: dict) -> Quote:
        source_cfg = product.get("source") or {}
        mapping = source_cfg.get("mapping") or {}

        # Explicit verified mappings always retain the original exact-SKU path.
        if mapping.get("verified"):
            return super().fetch(product)

        if self._family_selection(source_cfg):
            return self._family_quote(product, source_cfg)

        return super().fetch(product)
