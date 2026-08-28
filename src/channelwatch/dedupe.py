from __future__ import annotations

import re
import unicodedata

from .models import ChannelCandidate, ChannelGroup

_QUALITY_RE = re.compile(r"\b(?:uhd|fhd|hd|sd|4k|1080p|720p|576p|480p)\b", re.IGNORECASE)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_channel_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = _QUALITY_RE.sub(" ", text)
    return _NON_ALNUM_RE.sub("", text.casefold())


def candidate_key(candidate: ChannelCandidate) -> str:
    if candidate.tvg_id.strip():
        return candidate.tvg_id.strip().casefold()
    return f"{candidate.country_code.lower()}:{normalize_channel_name(candidate.name)}"


def merge_candidates(candidates: list[ChannelCandidate]) -> list[ChannelGroup]:
    groups: dict[str, ChannelGroup] = {}
    stream_indexes: dict[str, dict[str, ChannelCandidate]] = {}

    for candidate in candidates:
        key = candidate_key(candidate)
        if key not in groups:
            groups[key] = ChannelGroup(
                key=key,
                name=candidate.name,
                country_code=candidate.country_code,
                tvg_id=candidate.tvg_id,
                logo=candidate.logo,
                group=candidate.group,
                streams=[],
            )
            stream_indexes[key] = {}
        group = groups[key]
        if not group.logo and candidate.logo:
            group.logo = candidate.logo
        if not group.group and candidate.group:
            group.group = candidate.group
        if not group.tvg_id and candidate.tvg_id:
            group.tvg_id = candidate.tvg_id

        existing = stream_indexes[key].get(candidate.url)
        if existing is not None:
            existing.source_ids.update(candidate.source_ids)
            existing.source_priority = max(existing.source_priority, candidate.source_priority)
            if not existing.logo and candidate.logo:
                existing.logo = candidate.logo
            continue

        group.streams.append(candidate)
        stream_indexes[key][candidate.url] = candidate

    return list(groups.values())
