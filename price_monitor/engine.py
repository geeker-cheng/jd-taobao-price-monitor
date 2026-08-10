from __future__ import annotations

from datetime import datetime, timezone

from .alerts import evaluate_quote
from .config import monitorable_products
from .models import Quote
from .state import StateStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _age_seconds(now: str, then: str | None) -> int | None:
    if not then:
        return None
    try:
        now_dt = datetime.fromisoformat(now.replace("Z", "+00:00"))
        then_dt = datetime.fromisoformat(then.replace("Z", "+00:00"))
        return max(0, int((now_dt - then_dt).total_seconds()))
    except (TypeError, ValueError):
        return None


def _health_error(quote: Quote) -> str | None:
    for key in ("error", "reason"):
        value = quote.detail.get(key)
        if value:
            return str(value)[:500]
    errors = quote.detail.get("errors")
    if isinstance(errors, list) and errors:
        return str(errors[0])[:500]
    return None


class MonitorEngine:
    def __init__(self, config: dict, store: StateStore, sources: dict | None = None):
        self.config = config
        self.store = store
        if sources is None:
            # Lazy import keeps the state/engine layer independently testable.
            from .sources import HaodankuSource, MaishouSource
            sources = {"jd": MaishouSource(), "taobao": HaodankuSource()}
        self.sources = sources

    def run(self, *, now: str | None = None) -> dict:
        now = now or _now()
        output = {"checked_at": now, "products": {}, "events": []}

        for product in monitorable_products(self.config):
            product_id = product["id"]
            source = self.sources[product["platform"]]
            provider = (product.get("source") or {}).get("provider") or type(source).__name__
            try:
                quote = source.fetch(product)
            except Exception as exc:
                quote = Quote(
                    product_id=product_id,
                    platform=product["platform"],
                    status="SOURCE_ERROR",
                    source=provider,
                    checked_at=now,
                    detail={"error": f"{type(exc).__name__}: {exc}"},
                )

            # Alert policy is a reserved no-op interface in the current phase.
            quote, events, accepted = evaluate_quote(product, quote, {}, now=now)
            previous = self.store.status.get("products", {}).get(product_id, {})
            last_success_at = now if accepted else previous.get("last_success_at")

            status_record = quote.to_dict()
            status_record.update(
                {
                    "monitoring_price": quote.monitoring_price,
                    "accepted_sample": accepted,
                    "events": [event.to_dict() for event in events],
                    "last_checked_at": now,
                    "last_success_at": last_success_at,
                    "source_status": quote.status,
                    "data_age_seconds": 0 if accepted else _age_seconds(now, last_success_at),
                }
            )
            self.store.set_status(product_id, status_record)
            self.store.update_source_health(
                str(provider),
                checked_at=now,
                ok=accepted,
                status=quote.status,
                error=_health_error(quote),
            )

            if accepted:
                self.store.append_history(
                    product_id,
                    {
                        "checked_at": now,
                        "status": quote.status,
                        "price": quote.price,
                        "effective_price": quote.effective_price,
                        "monitoring_price": quote.monitoring_price,
                        "confidence": quote.confidence,
                        "source": quote.source,
                        "source_product_id": quote.source_product_id,
                        "canonical_sku": quote.canonical_sku,
                        "provider_stable_id": quote.detail.get("goods_id_b"),
                    },
                    limit=int(self.config.get("history_limit", 365)),
                )

            output["products"][product_id] = status_record
            output["events"].extend(event.to_dict() for event in events)

        output["state_files_changed"] = self.store.save(now)
        return output
