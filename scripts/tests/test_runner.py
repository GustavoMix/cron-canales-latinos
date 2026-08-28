from dataclasses import replace

import pytest

from channelwatch.models import (
    ChannelCandidate,
    CheckResult,
    CountryConfig,
    CountrySourceLoad,
    Settings,
    SourceHealth,
)
from channelwatch.runner import ChannelWatchRunner
from channelwatch.store import HealthStore


class FakeSourceLoader:
    def __init__(self):
        self.calls = 0

    async def load_country(self, country, specs):
        self.calls += 1
        return CountrySourceLoad(
            country_code=country.code,
            candidates=[
                ChannelCandidate(
                    name="Canal Bueno",
                    url="https://good.test/live.m3u8",
                    source_ids={"iptv_org"},
                    country_code=country.code,
                    tvg_id="Good.test",
                    source_priority=10,
                ),
                ChannelCandidate(
                    name="Canal Malo",
                    url="https://bad.test/live.m3u8",
                    source_ids={"free_tv"},
                    country_code=country.code,
                    tvg_id="Bad.test",
                    source_priority=20,
                ),
            ],
            sources=[SourceHealth("iptv_org", "https://repo.test", True, "")],
        )


class FakeChecker:
    def __init__(self):
        self.calls = 0
        self.probe_calls = 0
        self.deep_calls = 0

    async def _result(self, url):
        self.calls += 1
        success = "good.test" in url
        return CheckResult(
            url=url,
            success=success,
            checked_at=f"2026-08-28T10:00:{self.calls:02d}Z",
            latency_ms=100,
            error="" if success else "timeout",
            https=True,
            android_playable=success,
        )

    async def probe_url(self, url):
        self.probe_calls += 1
        return await self._result(url)

    async def check_url(self, url):
        self.deep_calls += 1
        return await self._result(url)


@pytest.mark.asyncio
async def test_fresh_country_runs_bootstrap_rounds_and_returns_only_stable_channels(tmp_path):
    settings = replace(Settings(), bootstrap_rounds=2, bootstrap_pause_seconds=0)
    country = CountryConfig("BO", "Bolivia")
    loader = FakeSourceLoader()
    checker = FakeChecker()
    store = HealthStore(tmp_path / "health.db", 20)
    runner = ChannelWatchRunner(settings, {"BO": country}, loader, checker, store)

    first = await runner.run_country(country)

    assert checker.calls == 3  # two quick probes + one deep confirmation
    assert checker.probe_calls == 2
    assert checker.deep_calls == 1
    assert [channel.name for channel in first.channels] == ["Canal Bueno"]
    assert first.bootstrap_rounds == 2

    second = await runner.run_country(country)
    assert checker.calls == 5  # existing country history -> one deep round for two URLs
    assert checker.deep_calls == 3
    assert second.bootstrap_rounds == 1
    store.close()


@pytest.mark.asyncio
async def test_partial_history_from_cancelled_run_still_uses_bootstrap(tmp_path):
    settings = replace(Settings(), bootstrap_rounds=2, bootstrap_pause_seconds=0)
    country = CountryConfig("BO", "Bolivia")
    loader = FakeSourceLoader()
    checker = FakeChecker()
    store = HealthStore(tmp_path / "health.db", 20)
    store.record(
        "https://good.test/live.m3u8",
        "BO",
        "good",
        CheckResult(
            url="https://good.test/live.m3u8",
            success=False,
            checked_at="2026-08-28T09:00:00Z",
            error="timeout",
        ),
    )
    runner = ChannelWatchRunner(settings, {"BO": country}, loader, checker, store)

    result = await runner.run_country(country)

    assert result.bootstrap_rounds == 2
    assert checker.probe_calls == 2
    assert [channel.name for channel in result.channels] == ["Canal Bueno"]
    assert store.has_completed_country_run("BO") is True
    store.close()

@pytest.mark.asyncio
async def test_multiple_countries_run_in_parallel_with_configured_limit():
    import asyncio

    settings = replace(Settings(), country_concurrency=3)
    countries = {
        code: CountryConfig(code, code)
        for code in ["BO", "AR", "PE", "CL", "BR"]
    }
    runner = ChannelWatchRunner(settings, countries, None, None, None)
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def fake_run_country(country):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.02)
        async with lock:
            active -= 1
        return country.code

    runner.run_country = fake_run_country
    result = await runner.run()

    assert result == ["BO", "AR", "PE", "CL", "BR"]
    assert peak == 3

@pytest.mark.asyncio
async def test_failed_source_run_does_not_mark_country_bootstrap_complete(tmp_path):
    class FailingLoader:
        async def load_country(self, country, specs):
            return CountrySourceLoad(
                country_code=country.code,
                candidates=[],
                sources=[SourceHealth("iptv_org", "https://repo.test", False, "timeout")],
            )

    settings = replace(Settings(), bootstrap_rounds=2, bootstrap_pause_seconds=0)
    country = CountryConfig("BO", "Bolivia")
    store = HealthStore(tmp_path / "health.db", 20)
    runner = ChannelWatchRunner(settings, {"BO": country}, FailingLoader(), FakeChecker(), store)

    result = await runner.run_country(country)

    assert result.successful_sources == 0
    assert store.has_completed_country_run("BO") is False
    store.close()
