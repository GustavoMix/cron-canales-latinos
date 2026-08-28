import httpx
import pytest

from channelwatch.models import CountryConfig, Settings, SourceSpec
from channelwatch.source_loader import SourceLoader


@pytest.mark.asyncio
async def test_shared_global_source_is_fetched_once_and_filtered_per_country():
    calls = 0
    playlist = """#EXTM3U
#EXTINF:-1 tvg-id="Bolivia.bo" tvg-country="BO",Bolivia TV
https://bo.test/live.m3u8
#EXTINF:-1 tvg-id="Argentina.ar" tvg-country="AR",Argentina TV
https://ar.test/live.m3u8
"""

    def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, text=playlist)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    loader = SourceLoader(Settings(), client=client)
    global_url = "https://repo.test/global.m3u"

    bo = await loader.load_country(
        CountryConfig("BO", "Bolivia"),
        [SourceSpec("free_tv", global_url, "attribute", "BO", 20)],
    )
    ar = await loader.load_country(
        CountryConfig("AR", "Argentina"),
        [SourceSpec("free_tv", global_url, "attribute", "AR", 20)],
    )

    assert calls == 1
    assert [c.name for c in bo.candidates] == ["Bolivia TV"]
    assert [c.name for c in ar.candidates] == ["Argentina TV"]
    assert bo.sources[0].success is True
    await client.aclose()


@pytest.mark.asyncio
async def test_fixed_country_source_assigns_country_and_priority():
    playlist = """#EXTM3U
#EXTINF:-1 tvg-id="ATB.bo",ATB
https://bo.test/atb.m3u8
"""

    def handler(request):
        return httpx.Response(200, text=playlist)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    loader = SourceLoader(Settings(), client=client)
    result = await loader.load_country(
        CountryConfig("BO", "Bolivia"),
        [SourceSpec("iptv_org", "https://repo.test/bo.m3u", "fixed", "BO", 10)],
    )

    assert result.candidates[0].country_code == "BO"
    assert result.candidates[0].source_priority == 10
    await client.aclose()


@pytest.mark.asyncio
async def test_source_failure_is_reported_without_crashing_country():
    def handler(request):
        return httpx.Response(503, text="down")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    loader = SourceLoader(Settings(), client=client)
    result = await loader.load_country(
        CountryConfig("BO", "Bolivia"),
        [SourceSpec("source", "https://repo.test/bo.m3u", "fixed", "BO", 1)],
    )

    assert result.candidates == []
    assert result.sources[0].success is False
    assert result.sources[0].error == "http_503"
    await client.aclose()

@pytest.mark.asyncio
async def test_country_sources_are_fetched_in_parallel():
    import asyncio

    active = 0
    peak = 0
    lock = asyncio.Lock()
    playlist = "#EXTM3U\n#EXTINF:-1,Canal\nhttps://cdn.test/live.m3u8\n"

    async def handler(request):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.03)
        async with lock:
            active -= 1
        return httpx.Response(200, text=playlist)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    loader = SourceLoader(Settings(), client=client)
    result = await loader.load_country(
        CountryConfig("BO", "Bolivia"),
        [
            SourceSpec("one", "https://repo1.test/bo.m3u", "fixed", "BO", 10),
            SourceSpec("two", "https://repo2.test/bo.m3u", "fixed", "BO", 20),
        ],
    )

    assert peak == 2
    assert len(result.sources) == 2
    await client.aclose()
