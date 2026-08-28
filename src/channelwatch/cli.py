from __future__ import annotations

import argparse
import asyncio
import json
import logging
from dataclasses import asdict
from pathlib import Path

from .config import load_countries, load_settings
from .hls import HlsChecker
from .publisher import Publisher
from .runner import ChannelWatchRunner
from .source_loader import SourceLoader
from .store import HealthStore

LOG = logging.getLogger("channelwatch")


def _common_settings_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--settings", default="config/settings.toml", help="Path to settings TOML")


def _common_countries_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--countries", default="config/countries.toml", help="Path to countries TOML")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="channelwatch",
        description="Validate public/authorized IPTV HLS streams and publish stable JSON feeds.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run source ingestion, checks and JSON publishing")
    _common_settings_argument(run)
    _common_countries_argument(run)
    run.add_argument("--country", action="append", help="Limit to ISO country code; may be repeated")
    run.add_argument("--force-publish", action="store_true", help="Bypass large-drop quarantine guard")

    check = sub.add_parser("check-url", help="Deep-check a single direct HLS URL")
    _common_settings_argument(check)
    check.add_argument("url")

    validate = sub.add_parser("validate-config", help="Validate TOML configuration without network")
    _common_settings_argument(validate)
    _common_countries_argument(validate)

    countries = sub.add_parser("list-countries", help="List configured countries")
    _common_countries_argument(countries)

    publish_index = sub.add_parser("publish-index", help="Build countries.json from existing country feeds")
    _common_settings_argument(publish_index)
    _common_countries_argument(publish_index)

    return parser


def _validate_config(settings_path: str, countries_path: str) -> int:
    settings = load_settings(settings_path)
    countries = load_countries(countries_path)
    source_ids = [source.id for source in settings.builtin_sources]
    if len(countries) == 0:
        print("Invalid configuration: no countries configured")
        return 2
    if len(source_ids) < 2:
        print("Invalid configuration: expected at least two built-in sources")
        return 2
    if len(set(source_ids)) != len(source_ids):
        print("Invalid configuration: duplicate built-in source IDs")
        return 2
    print(f"OK: {len(countries)} countries; built-in sources: {', '.join(source_ids)}")
    return 0


async def _check_url(settings_path: str, url: str) -> int:
    settings = load_settings(settings_path)
    checker = HlsChecker(settings)
    try:
        result = await checker.check_url(url)
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0 if result.success else 1
    finally:
        await checker.aclose()


async def _run(args: argparse.Namespace) -> int:
    settings = load_settings(args.settings)
    countries = load_countries(args.countries)
    selected = [code.upper() for code in args.country] if args.country else list(countries)
    unknown = [code for code in selected if code not in countries]
    if unknown:
        print(f"Unknown country code(s): {', '.join(unknown)}")
        return 2

    state_dir = Path(settings.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    store = HealthStore(
        state_dir / "health.db",
        max_history_rows_per_stream=settings.max_history_rows_per_stream,
    )
    source_loader = SourceLoader(settings)
    checker = HlsChecker(settings)
    publisher = Publisher(settings)
    runner = ChannelWatchRunner(settings, countries, source_loader, checker, store)

    try:
        results = await runner.run(selected)
        for result in results:
            outcome = publisher.publish_country(result, force=args.force_publish)
            print(
                f"{result.country.code}: {outcome.status} | "
                f"stable={len(result.channels)} discovered={result.discovered_candidates} "
                f"rejected={result.rejected_candidates} sources_ok={result.successful_sources}/{len(result.sources)}"
            )
        publisher.publish_index(countries)
        print(f"Index: {Path(settings.output_dir) / 'countries.json'}")
        return 0
    finally:
        store.close()
        await source_loader.aclose()
        await checker.aclose()


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "validate-config":
        return _validate_config(args.settings, args.countries)
    if args.command == "list-countries":
        countries = load_countries(args.countries)
        for code in sorted(countries):
            print(f"{code}  {countries[code].name}")
        return 0
    if args.command == "publish-index":
        settings = load_settings(args.settings)
        countries = load_countries(args.countries)
        output = Publisher(settings).publish_index(countries)
        print(f"Index: {output}")
        return 0
    if args.command == "check-url":
        return asyncio.run(_check_url(args.settings, args.url))
    if args.command == "run":
        return asyncio.run(_run(args))
    parser.error("unknown command")
    return 2
