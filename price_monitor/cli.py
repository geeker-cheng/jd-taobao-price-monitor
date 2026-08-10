from __future__ import annotations

import argparse
import json
import sys

from .config import ConfigError, load_config
from .engine import MonitorEngine
from .state import StateStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="JD + Taobao/Tmall price monitor")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="Validate product configuration")
    validate.add_argument("--config", default="config/products.yaml")

    run = sub.add_parser("run", help="Run all MONITORING products once")
    run.add_argument("--config", default="config/products.yaml")
    run.add_argument("--data-dir", default="data")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
    except (OSError, ConfigError, ValueError) as exc:
        print(f"CONFIG_ERROR: {exc}", file=sys.stderr)
        return 2

    if args.command == "validate":
        print(
            json.dumps(
                {
                    "ok": True,
                    "products": len(config.get("products", [])),
                    "platforms": sorted(
                        {p["platform"] for p in config.get("products", [])}
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0

    store = StateStore(args.data_dir)
    output = MonitorEngine(config, store).run()
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
