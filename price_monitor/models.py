from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class PriceConfidence(str, Enum):
    EXACT_SKU_PRICE = "EXACT_SKU_PRICE"
    PRODUCT_PAGE_PRICE = "PRODUCT_PAGE_PRICE"
    UNVERIFIED = "UNVERIFIED"


class QuoteStatus(str, Enum):
    OK = "OK"
    CONFIG_REQUIRED = "CONFIG_REQUIRED"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS_SOURCE_MAPPING = "AMBIGUOUS_SOURCE_MAPPING"
    SOURCE_ERROR = "SOURCE_ERROR"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    MAPPED_ENTITY_NOT_FOUND = "MAPPED_ENTITY_NOT_FOUND"
    ANOMALY = "ANOMALY"


@dataclass
class Quote:
    product_id: str
    platform: str
    status: str
    source: str
    checked_at: str
    title: str | None = None
    shop: str | None = None
    price: float | None = None
    effective_price: float | None = None
    original_price: float | None = None
    coupon: float | None = None
    confidence: str = PriceConfidence.UNVERIFIED.value
    source_product_id: str | None = None
    canonical_sku: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def monitoring_price(self) -> float | None:
        if self.effective_price is not None:
            return self.effective_price
        return self.price

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AlertEvent:
    product_id: str
    event_type: str
    price: float
    created_at: str
    confidence: str
    formal: bool
    reference_price: float | None = None
    target_price: float | None = None
    drop_pct: float | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
