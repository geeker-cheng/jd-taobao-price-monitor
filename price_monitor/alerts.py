from __future__ import annotations

from datetime import datetime, timezone

from .models import AlertEvent, PriceConfidence, Quote


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _drop_pct(reference: float, current: float) -> float:
    if reference <= 0:
        return 0.0
    return (reference - current) / reference


def evaluate_quote(
    product: dict,
    quote: Quote,
    alert_state: dict,
    *,
    now: str | None = None,
) -> tuple[Quote, list[AlertEvent], bool]:
    """Evaluate a valid source quote.

    Returns (possibly status-adjusted quote, events, accepted_sample).
    An anomalous sample is not allowed to move alert baselines.
    """
    now = now or _now()
    price = quote.monitoring_price
    if quote.status != "OK" or price is None or price <= 0:
        return quote, [], False

    cfg = product.get("alert", {})
    anomaly_threshold = float(cfg.get("anomaly_drop_pct", 0.25))
    last_valid = alert_state.get("last_valid_price")

    if isinstance(last_valid, (int, float)) and price < last_valid:
        drop = _drop_pct(float(last_valid), float(price))
        if drop >= anomaly_threshold:
            quote.status = "ANOMALY"
            quote.detail = dict(quote.detail)
            quote.detail["anomaly"] = {
                "last_valid_price": last_valid,
                "current_price": price,
                "drop_pct": round(drop, 6),
                "threshold": anomaly_threshold,
            }
            return quote, [], False

    events: list[AlertEvent] = []
    confidence = quote.confidence
    allow_page = bool(cfg.get("allow_product_page_alerts", False))
    formal_eligible = (
        confidence == PriceConfidence.EXACT_SKU_PRICE.value
        or (
            confidence == PriceConfidence.PRODUCT_PAGE_PRICE.value
            and allow_page
        )
    )

    target = cfg.get("target_price")
    armed = bool(alert_state.get("target_armed", True))
    if isinstance(target, (int, float)):
        target = float(target)
        if price <= target and armed:
            events.append(
                AlertEvent(
                    product_id=quote.product_id,
                    event_type=(
                        "TARGET_REACHED"
                        if formal_eligible
                        else "CANDIDATE_TARGET_REACHED"
                    ),
                    price=float(price),
                    created_at=now,
                    confidence=confidence,
                    formal=formal_eligible,
                    target_price=target,
                    message=(
                        "Target price reached."
                        if formal_eligible
                        else "Product-page/unverified price reached target; exact SKU confirmation required."
                    ),
                )
            )
            alert_state["target_armed"] = False
        elif price > target:
            alert_state["target_armed"] = True

    reference = alert_state.get("reference_price")
    if not isinstance(reference, (int, float)):
        reference = float(price)
        alert_state["reference_price"] = reference

    significant = cfg.get("significant_drop_pct")
    if isinstance(significant, (int, float)) and reference > 0 and price < reference:
        significant = float(significant)
        drop = _drop_pct(float(reference), float(price))
        if drop >= significant:
            events.append(
                AlertEvent(
                    product_id=quote.product_id,
                    event_type=(
                        "SIGNIFICANT_DROP"
                        if formal_eligible
                        else "CANDIDATE_SIGNIFICANT_DROP"
                    ),
                    price=float(price),
                    created_at=now,
                    confidence=confidence,
                    formal=formal_eligible,
                    reference_price=float(reference),
                    drop_pct=round(drop, 6),
                    message=(
                        "Significant drop from reference price."
                        if formal_eligible
                        else "Product-page/unverified significant drop; exact SKU confirmation required."
                    ),
                )
            )
            alert_state["reference_price"] = float(price)
        # If the decline is not yet large enough, keep the old high reference.
    elif price > float(reference):
        alert_state["reference_price"] = float(price)

    alert_state["last_valid_price"] = float(price)
    if events:
        alert_state["last_alert_price"] = float(price)
        alert_state["last_alert_at"] = now

    return quote, events, True
