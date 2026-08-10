from __future__ import annotations

import json
from pathlib import Path


DEFAULT_STATUS = {"version": 1, "updated_at": None, "products": {}}
DEFAULT_HISTORY = {"version": 1, "products": {}}
DEFAULT_ALERT = {"version": 1, "products": {}}


def _deepcopy_json(obj: dict) -> dict:
    return json.loads(json.dumps(obj, ensure_ascii=False))


def load_json(path: str | Path, default: dict) -> dict:
    path = Path(path)
    if not path.exists():
        return _deepcopy_json(default)
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def write_json(path: str | Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=True)
        fh.write("\n")
    tmp.replace(path)


class StateStore:
    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)
        self.status_path = self.data_dir / "price_status.json"
        self.history_path = self.data_dir / "price_history.json"
        self.alert_path = self.data_dir / "alert_state.json"

        self.status = load_json(self.status_path, DEFAULT_STATUS)
        self.history = load_json(self.history_path, DEFAULT_HISTORY)
        self.alert = load_json(self.alert_path, DEFAULT_ALERT)

    def product_alert_state(self, product_id: str) -> dict:
        # Reserved extension point. Alert logic is intentionally inactive in the
        # current phase, so no target/re-arm/reference state is pre-populated.
        products = self.alert.setdefault("products", {})
        return products.setdefault(product_id, {})

    def set_status(self, product_id: str, value: dict) -> None:
        self.status.setdefault("products", {})[product_id] = value

    def append_history(self, product_id: str, sample: dict, limit: int = 365) -> None:
        rows = self.history.setdefault("products", {}).setdefault(product_id, [])
        rows.append(sample)
        if len(rows) > limit:
            del rows[:-limit]

    def save(self, updated_at: str) -> None:
        self.status["updated_at"] = updated_at
        self.history["updated_at"] = updated_at
        self.alert["updated_at"] = updated_at
        write_json(self.status_path, self.status)
        write_json(self.history_path, self.history)
        write_json(self.alert_path, self.alert)
