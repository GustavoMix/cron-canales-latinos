from __future__ import annotations

import re

from .models import ChannelCandidate

_ATTR_RE = re.compile(r'([A-Za-z0-9_-]+)=(?:"([^"]*)"|([^\s]+))')
_MARKERS_RE = re.compile(r"[ⓈⒼⓎⓉⓗⓒⓘ]+")


def _split_extinf(line: str) -> tuple[str, str]:
    in_quotes = False
    for idx, char in enumerate(line):
        if char == '"':
            in_quotes = not in_quotes
        elif char == "," and not in_quotes:
            return line[:idx], line[idx + 1 :]
    return line, ""


def _clean_name(name: str) -> str:
    cleaned = _MARKERS_RE.sub("", name)
    return " ".join(cleaned.split()).strip()


def parse_extinf_attributes(meta: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for match in _ATTR_RE.finditer(meta):
        attributes[match.group(1).lower()] = match.group(2) if match.group(2) is not None else match.group(3)
    return attributes


def parse_m3u(text: str, source_id: str, default_country: str) -> list[ChannelCandidate]:
    channels: list[ChannelCandidate] = []
    pending: tuple[str, dict[str, str]] | None = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            meta, display_name = _split_extinf(line)
            attributes = parse_extinf_attributes(meta)
            pending = (_clean_name(display_name), attributes)
            continue
        if line.startswith("#"):
            continue
        if pending is None:
            continue

        name, attributes = pending
        pending = None
        tvg_country = attributes.get("tvg-country", "").upper()
        country = tvg_country or default_country.upper()
        channels.append(
            ChannelCandidate(
                name=name,
                url=line,
                source_ids={source_id},
                country_code=country,
                tvg_id=attributes.get("tvg-id", ""),
                logo=attributes.get("tvg-logo", ""),
                group=attributes.get("group-title", ""),
                tvg_country=tvg_country,
                attributes=attributes,
            )
        )
    return channels
