from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Iterable
from urllib.parse import urljoin, urlparse

import httpx

from .models import CheckResult, Settings, utc_now_iso

_URI_ATTR_RE = re.compile(r'(?:^|,)URI="([^"]+)"')
_BANDWIDTH_RE = re.compile(r'(?:^|,)BANDWIDTH=(\d+)')


class HlsChecker:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            follow_redirects=True,
            headers={"user-agent": settings.user_agent},
        )
        self._global_sem = asyncio.Semaphore(max(1, settings.global_concurrency))
        self._host_sems: dict[str, asyncio.Semaphore] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    def _host_sem(self, url: str) -> asyncio.Semaphore:
        host = (urlparse(url).hostname or "").lower()
        if host not in self._host_sems:
            self._host_sems[host] = asyncio.Semaphore(max(1, self.settings.per_host_concurrency))
        return self._host_sems[host]

    async def _get(self, url: str, *, byte_range: bool = False) -> httpx.Response:
        headers = {"user-agent": self.settings.user_agent}
        if self.settings.web_origin:
            headers["origin"] = self.settings.web_origin
        if byte_range:
            headers["range"] = "bytes=0-2047"
        host_sem = self._host_sem(url)
        async with host_sem:
            async with self._global_sem:
                return await self.client.get(
                    url,
                    headers=headers,
                    timeout=self.settings.stream_timeout_seconds,
                    follow_redirects=True,
                )

    @staticmethod
    def _is_html(response: httpx.Response) -> bool:
        content_type = response.headers.get("content-type", "").lower()
        prefix = response.content[:256].lstrip().lower()
        return "text/html" in content_type or prefix.startswith(b"<html") or prefix.startswith(b"<!doctype html")

    @staticmethod
    def _is_hls(text: str) -> bool:
        for line in text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped.startswith("#EXTM3U")
        return False

    @staticmethod
    def _master_variants(text: str, base_url: str) -> list[tuple[int, str]]:
        lines = [line.strip() for line in text.splitlines()]
        variants: list[tuple[int, str]] = []
        for index, line in enumerate(lines):
            if not line.startswith("#EXT-X-STREAM-INF"):
                continue
            match = _BANDWIDTH_RE.search(line.split(":", 1)[1] if ":" in line else "")
            bandwidth = int(match.group(1)) if match else 0
            for next_line in lines[index + 1 :]:
                if not next_line:
                    continue
                if next_line.startswith("#"):
                    continue
                variants.append((bandwidth, urljoin(base_url, next_line)))
                break
        return variants

    @staticmethod
    def _first_media_uri(text: str, base_url: str) -> str:
        lines = [line.strip() for line in text.splitlines()]
        expect_segment = False
        for line in lines:
            if line.startswith("#EXT-X-PART:"):
                match = _URI_ATTR_RE.search(line.split(":", 1)[1])
                if match:
                    return urljoin(base_url, match.group(1))
            if line.startswith("#EXTINF"):
                expect_segment = True
                continue
            if expect_segment and line and not line.startswith("#"):
                return urljoin(base_url, line)
        return ""

    @staticmethod
    def _key_uri(text: str, base_url: str) -> str:
        for raw in text.splitlines():
            line = raw.strip()
            if not line.startswith("#EXT-X-KEY:"):
                continue
            attrs = line.split(":", 1)[1]
            if "METHOD=NONE" in attrs.upper():
                continue
            match = _URI_ATTR_RE.search(attrs)
            if match:
                return urljoin(base_url, match.group(1))
        return ""

    def _cors_state(self, responses: Iterable[httpx.Response]) -> str:
        if not self.settings.web_origin:
            return "unknown"
        origin = self.settings.web_origin.rstrip("/")
        for response in responses:
            allowed = response.headers.get("access-control-allow-origin", "").rstrip("/")
            if allowed not in {"*", origin}:
                return "blocked"
        return "allowed"

    @staticmethod
    def _all_https(urls: Iterable[str]) -> bool:
        checked = [url for url in urls if url]
        return bool(checked) and all(urlparse(url).scheme.lower() == "https" for url in checked)

    async def check_url(self, url: str) -> CheckResult:
        return await self._run_with_total_timeout(url, deep=True)

    async def probe_url(self, url: str) -> CheckResult:
        return await self._run_with_total_timeout(url, deep=False)

    async def _run_with_total_timeout(self, url: str, *, deep: bool) -> CheckResult:
        try:
            async with asyncio.timeout(max(0.1, self.settings.channel_timeout_seconds)):
                return await self._check_url(url, deep=deep)
        except TimeoutError:
            return CheckResult(
                url=url,
                success=False,
                checked_at=utc_now_iso(),
                latency_ms=int(max(0.1, self.settings.channel_timeout_seconds) * 1000),
                error="channel_timeout",
                cors="unknown",
                https=urlparse(url).scheme.lower() == "https",
                android_playable=False,
                web_playable=False if self.settings.web_origin else None,
            )

    async def _check_url(self, url: str, *, deep: bool) -> CheckResult:
        started = time.perf_counter()
        checked_at = utc_now_iso()
        responses: list[httpx.Response] = []
        checked_urls: list[str] = []
        media_url = ""
        segment_url = ""

        def fail(error: str) -> CheckResult:
            latency = int((time.perf_counter() - started) * 1000)
            cors = self._cors_state(responses)
            https = self._all_https(checked_urls or [url])
            return CheckResult(
                url=url,
                success=False,
                checked_at=checked_at,
                latency_ms=latency,
                error=error,
                media_url=media_url,
                segment_url=segment_url,
                cors=cors,
                https=https,
                android_playable=False,
                web_playable=False if self.settings.web_origin else None,
            )

        try:
            current_url = url
            media_response: httpx.Response | None = None
            for _depth in range(3):
                response = await self._get(current_url)
                responses.append(response)
                checked_urls.append(str(response.url))
                if not 200 <= response.status_code < 300:
                    return fail(f"playlist_http_{response.status_code}")
                if self._is_html(response):
                    return fail("html_response")
                text = response.text
                if not self._is_hls(text):
                    return fail("not_hls")

                variants = self._master_variants(text, str(response.url))
                if variants:
                    variants.sort(key=lambda item: item[0] if item[0] > 0 else 2**63)
                    current_url = variants[0][1]
                    continue

                media_response = response
                media_url = str(response.url)
                break

            if media_response is None:
                return fail("master_depth_exceeded")

            media_text = media_response.text
            if "#EXT-X-ENDLIST" in media_text.upper():
                return fail("vod_endlist")

            if not deep:
                latency = int((time.perf_counter() - started) * 1000)
                cors = self._cors_state(responses)
                https = self._all_https(checked_urls)
                return CheckResult(
                    url=url,
                    success=True,
                    checked_at=checked_at,
                    latency_ms=latency,
                    error="",
                    media_url=media_url,
                    segment_url="",
                    cors=cors,
                    https=https,
                    android_playable=False,
                    web_playable=None,
                )

            key_url = self._key_uri(media_text, media_url)
            if key_url:
                key_response = await self._get(key_url, byte_range=True)
                responses.append(key_response)
                checked_urls.append(str(key_response.url))
                if not 200 <= key_response.status_code < 300:
                    return fail(f"key_http_{key_response.status_code}")
                if self._is_html(key_response):
                    return fail("key_html_response")

            segment_url = self._first_media_uri(media_text, media_url)
            if not segment_url:
                return fail("no_media_segments")

            segment_response = await self._get(segment_url, byte_range=True)
            responses.append(segment_response)
            checked_urls.append(str(segment_response.url))
            if segment_response.status_code not in {200, 206}:
                return fail(f"segment_http_{segment_response.status_code}")
            if self._is_html(segment_response):
                return fail("segment_html_response")
            if not segment_response.content:
                return fail("empty_segment")

            latency = int((time.perf_counter() - started) * 1000)
            cors = self._cors_state(responses)
            https = self._all_https(checked_urls)
            web_playable = None
            if self.settings.web_origin:
                web_playable = bool(https and cors == "allowed")
            return CheckResult(
                url=url,
                success=True,
                checked_at=checked_at,
                latency_ms=latency,
                error="",
                media_url=media_url,
                segment_url=segment_url,
                cors=cors,
                https=https,
                android_playable=True,
                web_playable=web_playable,
            )
        except httpx.TimeoutException:
            return fail("timeout")
        except httpx.HTTPError as exc:
            return fail(f"http_error:{exc.__class__.__name__}")
        except Exception as exc:  # keep a single bad stream from crashing a country run
            return fail(f"unexpected:{exc.__class__.__name__}")
