from __future__ import annotations

import asyncio

import httpx

from .m3u import parse_m3u
from .models import CountryConfig, CountrySourceLoad, Settings, SourceHealth, SourceSpec


class SourceLoader:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            follow_redirects=True,
            headers={"user-agent": settings.user_agent},
        )
        self._fetch_tasks: dict[str, asyncio.Task[tuple[bool, str, str]]] = {}

    async def aclose(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _download(self, url: str) -> tuple[bool, str, str]:
        try:
            response = await self.client.get(
                url,
                timeout=self.settings.source_timeout_seconds,
                follow_redirects=True,
                headers={"user-agent": self.settings.user_agent},
            )
            if not 200 <= response.status_code < 300:
                return False, "", f"http_{response.status_code}"
            text = response.text
            if "#EXTM3U" not in text[:4096].upper():
                return False, "", "invalid_m3u"
            return True, text, ""
        except httpx.TimeoutException:
            return False, "", "timeout"
        except httpx.HTTPError as exc:
            return False, "", f"http_error:{exc.__class__.__name__}"
        except Exception as exc:
            return False, "", f"unexpected:{exc.__class__.__name__}"

    async def _fetch_once(self, url: str) -> tuple[bool, str, str]:
        task = self._fetch_tasks.get(url)
        if task is None:
            task = asyncio.create_task(self._download(url))
            self._fetch_tasks[url] = task
        return await asyncio.shield(task)

    async def load_country(self, country: CountryConfig, specs: list[SourceSpec]) -> CountrySourceLoad:
        candidates = []
        sources: list[SourceHealth] = []
        downloads = await asyncio.gather(*(self._fetch_once(spec.url) for spec in specs))

        for spec, (success, text, error) in zip(specs, downloads, strict=True):
            if not success:
                sources.append(SourceHealth(spec.id, spec.url, False, error, 0))
                continue

            parsed = parse_m3u(
                text,
                source_id=spec.id,
                default_country=country.code if spec.mode == "fixed" else "",
            )
            if spec.mode == "attribute":
                parsed = [item for item in parsed if item.country_code.upper() == country.code]
            else:
                for item in parsed:
                    item.country_code = country.code

            for item in parsed:
                item.source_priority = spec.priority
            candidates.extend(parsed)
            sources.append(SourceHealth(spec.id, spec.url, True, "", len(parsed)))

        return CountrySourceLoad(country.code, candidates, sources)
