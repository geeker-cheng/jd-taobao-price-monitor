from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .security import sanitize_data


STATE_VERSION = 2
HEALTH_VERSION = 1
ALERT_VERSION = 1
DEFAULT_STATUS = {"version": STATE_VERSION, "updated_at": None, "products": {}}
DEFAULT_HISTORY = {"version": STATE_VERSION, "updated_at": None, "products": {}}
DEFAULT_ALERT = {"version": ALERT_VERSION, "updated_at": None, "products": {}}
DEFAULT_HEALTH = {"version": HEALTH_VERSION, "updated_at": None, "sources": {}}
HISTORY_SIGNATURE_FIELDS = (
    "status",
    "price",
    "effective_price",
    "monitoring_price",
    "confidence",
    "source",
    "canonical_sku",
    "provider_stable_id",
)


def _deepcopy_json(obj: dict) -> dict:
    return json.loads(json.dumps(obj, ensure_ascii=False))


def load_json(path: str | Path, default: dict) -> dict:
    path = Path(path)
    if not path.exists():
        return _deepcopy_json(default)
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} contains invalid JSON; refusing to overwrite state") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _render_json(data: dict) -> str:
    safe = sanitize_data(data)
    return json.dumps(safe, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_json_if_changed(path: str | Path, data: dict) -> bool:
    path = Path(path)
    rendered = _render_json(data)
    if path.exists() and path.read_text(encoding="utf-8") == rendered:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(rendered, encoding="utf-8", newline="\n")
    tmp.replace(path)
    return True


def _sample_signature(sample: dict) -> tuple[Any, ...]:
    return tuple(sample.get(field) for field in HISTORY_SIGNATURE_FIELDS)


class StateStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.status_path = self.data_dir / "price_status.json"
        self.history_path = self.data_dir / "price_history.json"
        self.alert_path = self.data_dir / "alert_state.json"
        self.health_path = self.data_dir / "source_health.json"

        self.status = load_json(self.status_path, DEFAULT_STATUS)
        self.history = load_json(self.history_path, DEFAULT_HISTORY)
        self.alert = load_json(self.alert_path, DEFAULT_ALERT)
        self.health = load_json(self.health_path, DEFAULT_HEALTH)
        self._dirty = {"status": False, "history": False, "alert": False, "health": False}

        # Sanitize any legacy state already present in the checkout. This lets the
        # next successful run clean old unsafe material instead of preserving it.
        for key, attr in (
            ("status", "status"),
            ("history", "history"),
            ("alert", "alert"),
            ("health", "health"),
        ):
            current = getattr(self, attr)
            safe = sanitize_data(current)
            if safe != current:
                setattr(self, attr, safe)
                self._dirty[key] = True

        # Small in-place schema migration for repositories created by v1.
        if self.status.get("version") != STATE_VERSION:
            self.status["version"] = STATE_VERSION
            self._dirty["status"] = True
        if self.history.get("version") != STATE_VERSION:
            self.history["version"] = STATE_VERSION
            self._dirty["history"] = True
        if self.health.get("version") != HEALTH_VERSION:
            self.health["version"] = HEALTH_VERSION
            self._dirty["health"] = True

    def product_alert_state(self, product_id: str) -> dict:
        products = self.alert.setdefault("products", {})
        if product_id not in products:
            products[product_id] = {}
            self._dirty["alert"] = True
        return products[product_id]

    def set_status(self, product_id: str, value: dict) -> None:
        safe_value = sanitize_data(value)
        products = self.status.setdefault("products", {})
        if products.get(product_id) != safe_value:
            products[product_id] = safe_value
            self._dirty["status"] = True

    def append_history(self, product_id: str, sample: dict, limit: int = 365) -> bool:
        safe_sample = sanitize_data(sample)
        rows = self.history.setdefault("products", {}).setdefault(product_id, [])
        if rows and _sample_signature(rows[-1]) == _sample_signature(safe_sample):
            return False
        rows.append(safe_sample)
        if len(rows) > limit:
            del rows[:-limit]
        self._dirty["history"] = True
        return True

    def update_source_health(
        self,
        source: str,
        *,
        checked_at: str,
        ok: bool,
        status: str,
        error: str | None = None,
    ) -> None:
        sources = self.health.setdefault("sources", {})
        old = sources.get(source, {})
        current = dict(old)
        current["last_checked_at"] = checked_at
        current["last_status"] = status
        if ok:
            current["last_success_at"] = checked_at
            current["consecutive_failures"] = 0
            current["last_error"] = None
        else:
            current["last_error_at"] = checked_at
            current["last_error"] = sanitize_data(error or status)
            current["consecutive_failures"] = int(old.get("consecutive_failures") or 0) + 1
        current = sanitize_data(current)
        if old != current:
            sources[source] = current
            self._dirty["health"] = True

    def save(self, updated_at: str) -> list[str]:
        changed: list[str] = []
        targets = (
            ("status", self.status_path, self.status),
            ("history", self.history_path, self.history),
            ("health", self.health_path, self.health),
            ("alert", self.alert_path, self.alert),
        )
        for key, path, payload in targets:
            if not self._dirty[key]:
                continue
            safe_payload = sanitize_data(payload)
            if safe_payload != payload:
                payload.clear()
                payload.update(safe_payload)
            payload["updated_at"] = updated_at
            if write_json_if_changed(path, payload):
                changed.append(path.name)
            self._dirty[key] = False
        return changed
