from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Iterable


SENSITIVE_ENV_NAMES = (
    "HAODANKU_API_KEY",
    "MAISHOU_INVITE_CODE",
)

SENSITIVE_KEYS = {
    "apikey",
    "api_key",
    "api-key",
    "access_token",
    "accesstoken",
    "token",
    "authorization",
    "secret",
    "password",
    "passwd",
    "invitecode",
    "invite_code",
}

STATE_FILENAMES = (
    "price_status.json",
    "price_history.json",
    "source_health.json",
    "alert_state.json",
)

_QUERY_SECRET_RE = re.compile(
    r"(?i)([?&](?:apikey|api_key|access_token|token|authorization|secret|password|passwd|invitecode|invite_code)=)([^&#\s]+)"
)
_PATH_SECRET_RE = re.compile(
    r"(?i)(/(?:apikey|api_key|access_token|token|secret|password|passwd|invitecode|invite_code)/)([^/?#\s]+)"
)
_BEARER_RE = re.compile(r"(?i)(\bBearer\s+)([A-Za-z0-9._~+\-/=]+)")


def configured_secret_values(extra: Iterable[str] | None = None) -> tuple[str, ...]:
    values: list[str] = []
    for name in SENSITIVE_ENV_NAMES:
        value = os.getenv(name, "").strip()
        if len(value) >= 4:
            values.append(value)
    if extra:
        for value in extra:
            value = str(value or "").strip()
            if len(value) >= 4:
                values.append(value)
    # Longest first avoids a shorter value partially masking a longer one.
    return tuple(sorted(set(values), key=len, reverse=True))


def redact_text(value: Any, *, extra_secrets: Iterable[str] | None = None) -> str:
    text = str(value)
    for secret in configured_secret_values(extra_secrets):
        text = text.replace(secret, "***")
    text = _QUERY_SECRET_RE.sub(r"\1***", text)
    text = _PATH_SECRET_RE.sub(r"\1***", text)
    text = _BEARER_RE.sub(r"\1***", text)
    return text


def _normalized_key(key: Any) -> str:
    return str(key).strip().lower().replace("-", "_")


def sanitize_data(value: Any, *, extra_secrets: Iterable[str] | None = None) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            normalized = _normalized_key(key)
            if normalized in {x.replace("-", "_") for x in SENSITIVE_KEYS}:
                if item not in (None, "", [], {}):
                    result[key] = "***"
                else:
                    result[key] = item
            else:
                result[key] = sanitize_data(item, extra_secrets=extra_secrets)
        return result
    if isinstance(value, list):
        return [sanitize_data(item, extra_secrets=extra_secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_data(item, extra_secrets=extra_secrets) for item in value)
    if isinstance(value, str):
        return redact_text(value, extra_secrets=extra_secrets)
    return value


def scan_state_directory(data_dir: str | Path) -> list[str]:
    """Return public state files that still contain material requiring redaction.

    The function never returns the sensitive value itself, only file names.
    """
    root = Path(data_dir)
    issues: list[str] = []
    for filename in STATE_FILENAMES:
        path = root / filename
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            issues.append(filename)
            continue
        if sanitize_data(data) != data:
            issues.append(filename)
    return issues
