from __future__ import annotations

from .models import AlertEvent, Quote


def evaluate_quote(
    product: dict,
    quote: Quote,
    alert_state: dict,
    *,
    now: str | None = None,
) -> tuple[Quote, list[AlertEvent], bool]:
    """Reserved alert-policy interface.

    The current production phase does not implement target-price alerts,
    significant-drop alerts, alert state machines, or price-change-based
    anomaly rejection. Platform/source adapters are responsible for deciding
    whether the returned quote belongs to the configured product.

    A positive price from an OK quote is accepted into history regardless of
    the size of the price move. The signature is kept so a future alert layer
    can be added without changing the engine/source contract.
    """
    del product, alert_state, now

    price = quote.monitoring_price
    if quote.status != "OK" or price is None or price <= 0:
        return quote, [], False

    return quote, [], True
