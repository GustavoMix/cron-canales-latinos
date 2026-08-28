from __future__ import annotations

import os
import tomllib
from pathlib import Path

from .models import CountryConfig, Settings, SourceSpec, SourceTemplate


def _read_toml(path: str | Path) -> dict:
    with Path(path).open("rb") as fh:
        return tomllib.load(fh)


def load_settings(path: str | Path) -> Settings:
    data = _read_toml(path)
    checker = data.get("checker", {})
    publishing = data.get("publishing", {})
    filters = data.get("filters", {})
    templates = []
    for raw in data.get("builtin_sources", []):
        templates.append(
            SourceTemplate(
                id=str(raw["id"]),
                mode=str(raw["mode"]),
                priority=int(raw.get("priority", 0)),
                url=str(raw.get("url", "")),
                url_template=str(raw.get("url_template", "")),
            )
        )

    web_origin = os.getenv("CHANNELWATCH_WEB_ORIGIN", str(checker.get("web_origin", "")))
    output_dir = os.getenv("CHANNELWATCH_OUTPUT_DIR", str(publishing.get("output_dir", "public/data")))
    state_dir = os.getenv("CHANNELWATCH_STATE_DIR", str(publishing.get("state_dir", "state")))

    return Settings(
        source_timeout_seconds=float(checker.get("source_timeout_seconds", 8.0)),
        stream_timeout_seconds=float(checker.get("stream_timeout_seconds", 4.0)),
        channel_timeout_seconds=float(checker.get("channel_timeout_seconds", 8.0)),
        global_concurrency=int(checker.get("global_concurrency", 80)),
        per_host_concurrency=int(checker.get("per_host_concurrency", 6)),
        country_concurrency=int(checker.get("country_concurrency", 4)),
        history_window=int(checker.get("history_window", 5)),
        min_consecutive_successes=int(checker.get("min_consecutive_successes", 2)),
        min_success_rate=float(checker.get("min_success_rate", 0.8)),
        bootstrap_rounds=int(checker.get("bootstrap_rounds", 2)),
        bootstrap_pause_seconds=float(checker.get("bootstrap_pause_seconds", 1.0)),
        max_history_rows_per_stream=int(checker.get("max_history_rows_per_stream", 20)),
        allow_http=bool(checker.get("allow_http", True)),
        block_temporary_urls=bool(checker.get("block_temporary_urls", True)),
        web_origin=web_origin,
        user_agent=str(checker.get("user_agent", "ChannelWatch/0.3")),
        output_dir=output_dir,
        state_dir=state_dir,
        drop_guard_ratio=float(publishing.get("drop_guard_ratio", 0.3)),
        drop_guard_min_previous=int(publishing.get("drop_guard_min_previous", 10)),
        blocked_name_patterns=tuple(str(x).lower() for x in filters.get("blocked_name_patterns", [])),
        builtin_sources=tuple(templates),
    )


def load_countries(path: str | Path) -> dict[str, CountryConfig]:
    data = _read_toml(path)
    result: dict[str, CountryConfig] = {}
    for code, raw in data.get("countries", {}).items():
        normalized = code.upper()
        result[normalized] = CountryConfig(
            code=normalized,
            name=str(raw["name"]),
            custom_urls=tuple(str(url).strip() for url in raw.get("custom_urls", []) if str(url).strip()),
        )
    return result


def build_source_specs(settings: Settings, country: CountryConfig) -> list[SourceSpec]:
    specs: list[SourceSpec] = []
    for template in settings.builtin_sources:
        url = template.url or template.url_template.format(
            country=country.code,
            country_lower=country.code.lower(),
        )
        specs.append(
            SourceSpec(
                id=template.id,
                url=url,
                mode=template.mode,
                country_code=country.code,
                priority=template.priority,
            )
        )

    for index, url in enumerate(country.custom_urls, start=1):
        specs.append(
            SourceSpec(
                id=f"custom_{index}",
                url=url,
                mode="fixed",
                country_code=country.code,
                priority=30,
            )
        )
    return specs
