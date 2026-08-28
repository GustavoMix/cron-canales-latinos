import asyncio
from dataclasses import replace

import httpx
import pytest

from channelwatch.hls import HlsChecker
from channelwatch.models import Settings


CORS = {"access-control-allow-origin": "https://tv.example"}


def make_client(handler):
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


@pytest.mark.asyncio
async def test_master_media_segment_success_and_web_metadata():
    def handler(request: httpx.Request):
        path = request.url.path
        if path == "/master.m3u8":
            return httpx.Response(
                200,
                headers=CORS,
                text="#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=900000\nlow/index.m3u8\n",
            )
        if path == "/low/index.m3u8":
            return httpx.Response(
                200,
                headers=CORS,
                text="#EXTM3U\n#EXT-X-TARGETDURATION:6\n#EXTINF:6.0,\nseg1.ts\n",
            )
        if path == "/low/seg1.ts":
            assert request.headers.get("range") == "bytes=0-2047"
            return httpx.Response(206, headers=CORS, content=b"video-bytes")
        return httpx.Response(404)

    client = make_client(handler)
    settings = replace(Settings(), web_origin="https://tv.example")
    checker = HlsChecker(settings, client=client)

    result = await checker.check_url("https://cdn.example/master.m3u8")

    assert result.success is True
    assert result.media_url == "https://cdn.example/low/index.m3u8"
    assert result.segment_url == "https://cdn.example/low/seg1.ts"
    assert result.cors == "allowed"
    assert result.https is True
    assert result.android_playable is True
    assert result.web_playable is True
    await client.aclose()


@pytest.mark.asyncio
async def test_rejects_vod_endlist_playlist():
    def handler(request):
        return httpx.Response(
            200,
            text="#EXTM3U\n#EXTINF:6,\nseg.ts\n#EXT-X-ENDLIST\n",
        )

    client = make_client(handler)
    result = await HlsChecker(Settings(), client=client).check_url("https://cdn.example/vod.m3u8")
    assert result.success is False
    assert result.error == "vod_endlist"
    await client.aclose()


@pytest.mark.asyncio
async def test_rejects_html_masquerading_as_playlist():
    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html>login</html>")

    client = make_client(handler)
    result = await HlsChecker(Settings(), client=client).check_url("https://cdn.example/live.m3u8")
    assert result.success is False
    assert result.error == "html_response"
    await client.aclose()


@pytest.mark.asyncio
async def test_supports_low_latency_hls_part_when_full_segment_not_present():
    def handler(request):
        if request.url.path.endswith("live.m3u8"):
            return httpx.Response(
                200,
                text='#EXTM3U\n#EXT-X-PART:DURATION=0.333,URI="part001.m4s"\n',
            )
        if request.url.path.endswith("part001.m4s"):
            return httpx.Response(206, content=b"part")
        return httpx.Response(404)

    client = make_client(handler)
    result = await HlsChecker(Settings(), client=client).check_url("https://cdn.example/live.m3u8")
    assert result.success is True
    assert result.segment_url.endswith("part001.m4s")
    await client.aclose()


@pytest.mark.asyncio
async def test_encrypted_playlist_requires_reachable_key():
    def handler(request):
        if request.url.path.endswith("live.m3u8"):
            return httpx.Response(
                200,
                text='#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key.bin"\n#EXTINF:6,\nseg.ts\n',
            )
        if request.url.path.endswith("key.bin"):
            return httpx.Response(403)
        if request.url.path.endswith("seg.ts"):
            return httpx.Response(206, content=b"segment")
        return httpx.Response(404)

    client = make_client(handler)
    result = await HlsChecker(Settings(), client=client).check_url("https://cdn.example/live.m3u8")
    assert result.success is False
    assert result.error == "key_http_403"
    await client.aclose()


@pytest.mark.asyncio
async def test_follows_redirect_before_validating_playlist():
    def handler(request):
        if request.url.path == "/start.m3u8":
            return httpx.Response(302, headers={"location": "/real/live.m3u8"})
        if request.url.path == "/real/live.m3u8":
            return httpx.Response(200, text="#EXTM3U\n#EXTINF:6,\nseg.ts\n")
        if request.url.path == "/real/seg.ts":
            return httpx.Response(206, content=b"segment")
        return httpx.Response(404)

    client = make_client(handler)
    result = await HlsChecker(Settings(), client=client).check_url("https://cdn.example/start.m3u8")
    assert result.success is True
    assert result.media_url == "https://cdn.example/real/live.m3u8"
    await client.aclose()


@pytest.mark.asyncio
async def test_successful_hls_can_be_marked_cors_blocked_for_web():
    def handler(request):
        if request.url.path.endswith("live.m3u8"):
            return httpx.Response(200, text="#EXTM3U\n#EXTINF:6,\nseg.ts\n")
        return httpx.Response(206, content=b"segment")

    client = make_client(handler)
    settings = replace(Settings(), web_origin="https://tv.example")
    result = await HlsChecker(settings, client=client).check_url("https://cdn.example/live.m3u8")
    assert result.success is True
    assert result.cors == "blocked"
    assert result.web_playable is False
    await client.aclose()


@pytest.mark.asyncio
async def test_per_host_concurrency_limit_is_respected():
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def handler(request):
        nonlocal active, peak
        async with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.02)
        async with lock:
            active -= 1
        if request.url.path.endswith(".m3u8"):
            return httpx.Response(200, text="#EXTM3U\n#EXTINF:6,\nseg.ts\n")
        return httpx.Response(206, content=b"segment")

    client = make_client(handler)
    settings = replace(Settings(), global_concurrency=10, per_host_concurrency=1)
    checker = HlsChecker(settings, client=client)

    await asyncio.gather(
        checker.check_url("https://same.example/a.m3u8"),
        checker.check_url("https://same.example/b.m3u8"),
        checker.check_url("https://same.example/c.m3u8"),
    )

    assert peak == 1
    await client.aclose()


@pytest.mark.asyncio
async def test_total_channel_timeout_caps_the_whole_hls_check():
    async def handler(request):
        await asyncio.sleep(1.00)
        return httpx.Response(200, text="#EXTM3U\n#EXTINF:6,\nseg.ts\n")

    client = make_client(handler)
    settings = replace(
        Settings(),
        stream_timeout_seconds=1.0,
        channel_timeout_seconds=0.05,
    )
    checker = HlsChecker(settings, client=client)

    started = asyncio.get_running_loop().time()
    result = await checker.check_url("https://slow.example/live.m3u8")
    elapsed = asyncio.get_running_loop().time() - started

    assert result.success is False
    assert result.error == "channel_timeout"
    # Keep generous scheduler headroom while still proving that the 1 s
    # request is cancelled by the whole-channel timeout.
    assert elapsed < 0.50
    await client.aclose()


@pytest.mark.asyncio
async def test_quick_probe_validates_playlist_without_downloading_segment():
    requested_paths = []

    def handler(request):
        requested_paths.append(request.url.path)
        if request.url.path.endswith("live.m3u8"):
            return httpx.Response(200, text="#EXTM3U\n#EXTINF:6,\nseg.ts\n")
        if request.url.path.endswith("seg.ts"):
            return httpx.Response(206, content=b"segment")
        return httpx.Response(404)

    client = make_client(handler)
    checker = HlsChecker(Settings(), client=client)

    result = await checker.probe_url("https://cdn.example/live.m3u8")

    assert result.success is True
    assert requested_paths == ["/live.m3u8"]
    await client.aclose()
