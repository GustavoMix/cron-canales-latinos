from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import CountryConfig, CountryRunResult, PublishOutcome, RankedChannel, Settings, utc_now_iso


class Publisher:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.output_dir = Path(settings.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, indent=2, sort_keys=False)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    @staticmethod
    def _alternate_payload(channel: RankedChannel) -> list[dict]:
        items = []
        for alternate in channel.alternates:
            items.append(
                {
                    "stream": alternate.candidate.url,
                    "sources": sorted(alternate.candidate.source_ids),
                    "latency_ms": alternate.health.latency_ms,
                    "https": alternate.check.https,
                    "cors": alternate.check.cors,
                    "web_playable": alternate.check.web_playable,
                }
            )
        return items

    @classmethod
    def _channel_payload(cls, channel: RankedChannel) -> dict:
        primary = channel.primary
        all_sources = set(primary.candidate.source_ids)
        for alternate in channel.alternates:
            all_sources.update(alternate.candidate.source_ids)
        return {
            "id": channel.tvg_id or channel.key,
            "name": channel.name,
            "logo": channel.logo,
            "category": channel.category,
            "stream": primary.candidate.url,
            "alternates": cls._alternate_payload(channel),
            "status": "stable",
            "stability": {
                "success_rate": primary.health.success_rate,
                "consecutive_successes": primary.health.consecutive_successes,
            },
            "latency_ms": primary.health.latency_ms,
            "sources": sorted(all_sources),
            "android_playable": primary.check.android_playable,
            "https": primary.check.https,
            "cors": primary.check.cors,
            "web_playable": primary.check.web_playable,
            "last_checked": primary.health.last_checked,
        }

    def build_country_payload(self, result: CountryRunResult) -> dict:
        return {
            "schema_version": 1,
            "country": {"code": result.country.code, "name": result.country.name},
            "generated_at": utc_now_iso(),
            "source_health": [
                {
                    "id": source.id,
                    "url": source.url,
                    "success": source.success,
                    "error": source.error,
                    "candidates": source.candidate_count,
                }
                for source in result.sources
            ],
            "stats": {
                "discovered_candidates": result.discovered_candidates,
                "rejected_candidates": result.rejected_candidates,
                "check_rounds": result.bootstrap_rounds,
            },
            "total_channels": len(result.channels),
            "channels": [self._channel_payload(channel) for channel in result.channels],
        }

    def publish_country(self, result: CountryRunResult, force: bool = False) -> PublishOutcome:
        code = result.country.code.lower()
        path = self.output_dir / f"{code}.json"
        payload = self.build_country_payload(result)

        if result.successful_sources == 0:
            return PublishOutcome(result.country.code, "preserved", str(path), len(result.channels))

        if path.exists() and not force:
            try:
                previous = json.loads(path.read_text(encoding="utf-8"))
                previous_count = int(previous.get("total_channels", 0))
            except (ValueError, OSError, json.JSONDecodeError):
                previous_count = 0
            new_count = len(result.channels)
            if (
                previous_count >= self.settings.drop_guard_min_previous
                and new_count < previous_count * self.settings.drop_guard_ratio
            ):
                quarantine = self.output_dir / "quarantine" / f"{code}-candidate.json"
                self._atomic_write_json(quarantine, payload)
                return PublishOutcome(result.country.code, "quarantined", str(quarantine), new_count)

        self._atomic_write_json(path, payload)
        return PublishOutcome(result.country.code, "published", str(path), len(result.channels))

    def publish_index(self, countries: dict[str, CountryConfig]) -> Path:
        entries = []
        for code in sorted(countries):
            path = self.output_dir / f"{code.lower()}.json"
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            country_data = payload.get("country") or {"code": code, "name": countries[code].name}
            entries.append(
                {
                    "code": country_data.get("code", code),
                    "name": country_data.get("name", countries[code].name),
                    "channels": int(payload.get("total_channels", 0)),
                    "generated_at": payload.get("generated_at", ""),
                    "path": f"{code.lower()}.json",
                }
            )
        output = self.output_dir / "countries.json"
        self._atomic_write_json(
            output,
            {
                "schema_version": 1,
                "generated_at": utc_now_iso(),
                "countries": entries,
            },
        )
        return output
