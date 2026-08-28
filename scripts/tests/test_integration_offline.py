import json
from dataclasses import replace

import httpx
import pytest

from channelwatch.hls import HlsChecker
from channelwatch.models import CountryConfig, Settings, SourceTemplate
from channelwatch.publisher import Publisher
from channelwatch.runner import ChannelWatchRunner
from channelwatch.source_loader import SourceLoader
from channelwatch.store import HealthStore


@pytest.mark.asyncio
async def test_offline_end_to_end_generates_stable_country_json(tmp_path):
    playlist = """#EXTM3U
#EXTINF:-1 tvg-id="BoliviaTV.bo" tvg-logo="https://img.test/bo.png",Bolivia TV
https://cdn.test/live.m3u8
"""

    def handler(request: httpx.Request):
        if request.url.host == "repo.test":
            return httpx.Response(200, text=playlist)
        if request.url.path == "/live.m3u8":
            return httpx.Response(200, text="#EXTM3U\n#EXTINF:6,\nseg.ts\n")
        if request.url.path == "/seg.ts":
            return httpx.Response(206, content=b"segment")
        return httpx.Response(404)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
    settings = replace(
        Settings(),
        output_dir=str(tmp_path / "out"),
        state_dir=str(tmp_path / "state"),
        bootstrap_rounds=2,
        bootstrap_pause_seconds=0,
        builtin_sources=(
            SourceTemplate(
                id="test_source",
                mode="fixed",
                priority=10,
                url="https://repo.test/bo.m3u",
            ),
        ),
    )
    country = CountryConfig("BO", "Bolivia")
    countries = {"BO": country}
    store = HealthStore(tmp_path / "state/health.db", 20)
    loader = SourceLoader(settings, client=client)
    checker = HlsChecker(settings, client=client)
    runner = ChannelWatchRunner(settings, countries, loader, checker, store)
    publisher = Publisher(settings)

    result = await runner.run_country(country)
    outcome = publisher.publish_country(result)
    publisher.publish_index(countries)

    payload = json.loads((tmp_path / "out/bo.json").read_text(encoding="utf-8"))
    assert outcome.status == "published"
    assert payload["total_channels"] == 1
    assert payload["channels"][0]["name"] == "Bolivia TV"
    assert payload["channels"][0]["status"] == "stable"
    assert (tmp_path / "out/countries.json").exists()

    store.close()
    await client.aclose()
