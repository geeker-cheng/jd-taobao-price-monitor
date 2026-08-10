from __future__ import annotations

from datetime import datetime, timezone

from .alerts import evaluate_quote
from .config import monitorable_products
from .models import Quote
from .sources import HaodankuSource, MaishouSource
from .state import StateStore


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MonitorEngine:
    def __init__(self, config: dict, store: StateStore, sources: dict | None = None):
        self.config = config
        self.store = store
        self.sources = sources or {
            "jd": MaishouSource(),
            "taobao": HaodankuSource(),
        }

    def run(self, *, now: str | None = None) -> dict:
        now = now or _now()
        output = {"checked_at": now, "products": {}, "events": []}

        for product in monitorable_products(self.config):
            product_id = product["id"]
            source = self.sources[product["platform"]]
            try:
                quote = source.fetch(product)
            except Exception as exc:
                quote = Quote(
                    product_id=product_id,
                    platform=product["platform"],
                    status="SOURCE_ERROR",
                    source=type(source).__name__,
                    checked_at=now,
                    detail={"error": f"{type(exc).__name__}: {exc}"},
                )

            alert_state = self.store.product_alert_state(product_id)
            quote, events, accepted = evaluate_quote(
                product, quote, alert_state, now=now
            )

            status_record = quote.to_dict()
            status_record["monitoring_price"] = quote.monitoring_price
            status_record["accepted_sample"] = accepted
            status_record["events"] = [event.to_dict() for event in events]
            self.store.set_status(product_id, status_record)

            if accepted:
                self.store.append_history(
                    product_id,
                    {
                        "checked_at": now,
                        "price": quote.price,
                        "effective_price": quote.effective_price,
                        "monitoring_price": quote.monitoring_price,
                        "confidence": quote.confidence,
                        "source": quote.source,
                        "source_product_id": quote.source_product_id,
                    },
                    limit=int(self.config.get("history_limit", 365)),
                )

            output["products"][product_id] = status_record
            output["events"].extend(event.to_dict() for event in events)

        self.store.save(now)
        return output
