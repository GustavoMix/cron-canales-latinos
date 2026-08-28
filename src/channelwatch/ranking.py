from __future__ import annotations

from .models import ChannelGroup, CheckResult, EvaluatedStream, RankedChannel, StreamHealth


def _stream_score(item: EvaluatedStream) -> float:
    latency = item.health.latency_ms if item.health.latency_ms is not None else 10_000
    return (
        item.health.success_rate * 1000.0
        + min(item.health.consecutive_successes, 10) * 10.0
        + (100.0 if item.check.https else 0.0)
        + len(item.candidate.source_ids) * 25.0
        + item.candidate.source_priority
        - min(latency, 10_000) / 100.0
    )


def rank_channel_streams(
    group: ChannelGroup,
    evaluations: dict[str, tuple[CheckResult, StreamHealth]],
) -> RankedChannel | None:
    stable: list[EvaluatedStream] = []
    for candidate in group.streams:
        evaluation = evaluations.get(candidate.url)
        if evaluation is None:
            continue
        check, health = evaluation
        if not check.success or health.status != "stable":
            continue
        item = EvaluatedStream(candidate, check, health)
        item.score = _stream_score(item)
        stable.append(item)

    if not stable:
        return None

    stable.sort(key=lambda item: (-item.score, item.candidate.url))
    return RankedChannel(
        key=group.key,
        name=group.name,
        country_code=group.country_code,
        tvg_id=group.tvg_id,
        logo=group.logo,
        category=group.group or "General",
        primary=stable[0],
        alternates=stable[1:],
    )
