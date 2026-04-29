from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, config_to_dict, default_config, save_config
from .server import NutCounterRuntime, build_doctor_report
from . import __version__


def main() -> None:
    parser = argparse.ArgumentParser(prog="nut-counter")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("version")
    subcommands.add_parser("doctor")
    subcommands.add_parser("repair")
    subcommands.add_parser("reset-config")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    args = parser.parse_args()

    if args.command == "version":
        print(__version__)
        return

    if args.command == "reset-config":
        config = default_config()
        save_config(config, args.config)
        print(json.dumps(config_to_dict(config), ensure_ascii=False, indent=2))
        return

    if args.command == "doctor":
        runtime = NutCounterRuntime(ui_dir=Path("/opt/nut-counter/ui"), config_path=args.config)
        try:
            print(json.dumps(build_doctor_report(runtime), ensure_ascii=False, indent=2))
        finally:
            runtime.close()
        return

    if args.command == "repair":
        args.config.parent.mkdir(parents=True, exist_ok=True)
        if not args.config.exists():
            save_config(default_config(), args.config)
            print(f"created default config at {args.config}")
            return
        print("no automatic repair needed")


if __name__ == "__main__":
    main()
