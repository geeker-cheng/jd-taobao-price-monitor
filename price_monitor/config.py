from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


SUPPORTED_PLATFORMS = {"jd", "taobao"}
MONITORABLE_STATUSES = {"MONITORING"}


class ConfigError(ValueError):
    pass


def _require_dict(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{name} must be an object")
    return value


def load_config(path: str | Path) -> dict:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    _require_dict(data, "root")
    products = data.get("products")
    if not isinstance(products, list):
        raise ConfigError("products must be a list")

    seen = set()
    for index, product in enumerate(products):
        _require_dict(product, f"products[{index}]")
        product_id = product.get("id")
        if not isinstance(product_id, str) or not product_id.strip():
            raise ConfigError(f"products[{index}].id is required")
        if product_id in seen:
            raise ConfigError(f"duplicate product id: {product_id}")
        seen.add(product_id)

        platform = product.get("platform")
        if platform not in SUPPORTED_PLATFORMS:
            raise ConfigError(
                f"{product_id}: platform must be one of {sorted(SUPPORTED_PLATFORMS)}"
            )

        if product.get("status") not in {
            "NEW", "VERIFIED", "MONITORING", "PAUSED", "INVALID"
        }:
            raise ConfigError(f"{product_id}: invalid status")

        source = _require_dict(product.get("source", {}), f"{product_id}.source")
        provider = source.get("provider")
        expected = "maishou" if platform == "jd" else "haodanku"
        if provider != expected:
            raise ConfigError(
                f"{product_id}: {platform} must use provider={expected}"
            )

        match = _require_dict(product.get("match", {}), f"{product_id}.match")
        groups = match.get("required_title_groups")
        if not isinstance(groups, list) or not groups:
            raise ConfigError(f"{product_id}: required_title_groups must be non-empty")
        if not all(isinstance(group, list) and group for group in groups):
            raise ConfigError(f"{product_id}: every title group must be non-empty")

        shops = _require_dict(product.get("shops", {}), f"{product_id}.shops")
        allowed = shops.get("allowed")
        if not isinstance(allowed, list) or not allowed:
            raise ConfigError(f"{product_id}: shops.allowed must be non-empty")

        alert = _require_dict(product.get("alert", {}), f"{product_id}.alert")
        for field in ("target_price", "significant_drop_pct"):
            value = alert.get(field)
            if value is not None and not isinstance(value, (int, float)):
                raise ConfigError(f"{product_id}: alert.{field} must be numeric or null")
        anomaly = alert.get("anomaly_drop_pct", 0.25)
        if not isinstance(anomaly, (int, float)) or not (0 < anomaly < 1):
            raise ConfigError(
                f"{product_id}: alert.anomaly_drop_pct must be between 0 and 1"
            )

    return data


def monitorable_products(config: dict) -> list[dict]:
    return [
        p for p in config.get("products", [])
        if p.get("enabled", True) and p.get("status") in MONITORABLE_STATUSES
    ]
