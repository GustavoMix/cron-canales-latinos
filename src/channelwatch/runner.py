from __future__ import annotations

import asyncio
import logging

LOG = logging.getLogger("channelwatch.runner")

from .config import build_source_specs
from .dedupe import merge_candidates
from .filters import filter_candidate
from .models import CountryConfig, CountryRunResult, Settings, utc_now_iso
from .ranking import rank_channel_streams
from .stability import classify_health


class ChannelWatchRunner:
    def __init__(self, settings, countries, source_loader, checker, store):
        self.settings: Settings = settings
        self.countries: dict[str, CountryConfig] = countries
        self.source_loader = source_loader
        self.checker = checker
        self.store = store

    async def run_country(self, country: CountryConfig) -> CountryRunResult:
        completed_before = self.store.has_completed_country_run(country.code)
        if not completed_before:
            self.store.clear_country_history(country.code)

        specs = build_source_specs(self.settings, country)
        loaded = await self.source_loader.load_country(country, specs)

        accepted = []
        rejected = 0
        for candidate in loaded.candidates:
            decision = filter_candidate(candidate, self.settings)
            if decision.accepted:
                accepted.append(candidate)
            else:
                rejected += 1

        groups = merge_candidates(accepted)
        url_to_group_key: dict[str, str] = {}
        url_to_name: dict[str, str] = {}
        for group in groups:
            for stream in group.streams:
                url_to_group_key.setdefault(stream.url, group.key)
                url_to_name.setdefault(stream.url, group.name)

        if not completed_before:
            rounds = max(1, self.settings.bootstrap_rounds)
        else:
            rounds = 1

        last_results = {}
        round_urls = list(url_to_group_key)
        for round_index in range(rounds):
            if not round_urls:
                break

            total = len(round_urls)
            completed = 0
            successful_urls: list[str] = []
            use_quick_probe = round_index == 0 and rounds > 1 and hasattr(self.checker, "probe_url")
            phase = "SONDEO RAPIDO" if use_quick_probe else "CONFIRMACION PROFUNDA"
            LOG.info(
                "%s %s %d/%d: comprobando %d streams",
                country.code,
                phase,
                round_index + 1,
                rounds,
                total,
            )


            async def check_one(url: str):
                if use_quick_probe:
                    return url, await self.checker.probe_url(url)
                return url, await self.checker.check_url(url)

            tasks = [asyncio.create_task(check_one(url)) for url in round_urls]
            for task in asyncio.as_completed(tasks):
                url, result = await task
                completed += 1
                last_results[url] = result
                self.store.record(url, country.code, url_to_group_key[url], result)
                if result.success:
                    successful_urls.append(url)
                marker = "OK" if result.success else f"FAIL {result.error}"
                percent = int((completed / total) * 100) if total else 100
                LOG.info(
                    "%s [%d/%d %d%%] %s - %s (%d ms)",
                    country.code,
                    completed,
                    total,
                    percent,
                    url_to_name.get(url, url),
                    marker,
                    result.latency_ms or 0,
                )

            # On a fresh country, only successful first-round candidates can
            # possibly become stable in the bootstrap confirmation round.
            if round_index == 0 and rounds > 1:
                round_urls = successful_urls
                LOG.info(
                    "%s ronda 1: %d/%d candidatos pasan a confirmacion",
                    country.code,
                    len(round_urls),
                    total,
                )

            if round_index + 1 < rounds and round_urls and self.settings.bootstrap_pause_seconds > 0:
                await asyncio.sleep(self.settings.bootstrap_pause_seconds)

        evaluations = {}
        for url, result in last_results.items():
            checks = self.store.recent(url, self.settings.history_window)
            evaluations[url] = (result, classify_health(checks, self.settings))

        ranked = []
        for group in groups:
            channel = rank_channel_streams(group, evaluations)
            if channel is not None:
                if channel.category.casefold() == country.name.casefold():
                    channel.category = "General"
                ranked.append(channel)
        ranked.sort(key=lambda item: item.name.casefold())
        if any(source.success for source in loaded.sources):
            self.store.mark_country_run_complete(country.code, utc_now_iso())

        return CountryRunResult(
            country=country,
            channels=ranked,
            sources=loaded.sources,
            discovered_candidates=len(loaded.candidates),
            rejected_candidates=rejected,
            bootstrap_rounds=rounds,
        )

    async def run(self, country_codes: list[str] | None = None) -> list[CountryRunResult]:
        codes = [code.upper() for code in country_codes] if country_codes else list(self.countries)
        semaphore = asyncio.Semaphore(max(1, self.settings.country_concurrency))

        async def run_one(code: str):
            async with semaphore:
                return await self.run_country(self.countries[code])

        return list(await asyncio.gather(*(run_one(code) for code in codes)))
