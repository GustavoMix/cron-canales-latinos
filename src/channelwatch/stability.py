from __future__ import annotations

from .models import HealthRecord, Settings, StreamHealth


def classify_health(checks: list[HealthRecord], settings: Settings) -> StreamHealth:
    considered = checks[: max(1, settings.history_window)]
    if not considered:
        return StreamHealth(
            status="warming",
            success_rate=0.0,
            consecutive_successes=0,
            consecutive_failures=0,
            total_considered=0,
            last_checked="",
            latency_ms=None,
        )

    successes = sum(1 for item in considered if item.success)
    success_rate = successes / len(considered)

    consecutive_successes = 0
    consecutive_failures = 0
    current_success = considered[0].success
    if current_success:
        for item in considered:
            if not item.success:
                break
            consecutive_successes += 1
    else:
        for item in considered:
            if item.success:
                break
            consecutive_failures += 1

    if current_success:
        if (
            consecutive_successes >= settings.min_consecutive_successes
            and success_rate >= settings.min_success_rate
        ):
            status = "stable"
        else:
            status = "warming"
    else:
        status = "offline" if consecutive_failures >= 2 else "degraded"

    latency = considered[0].latency_ms
    if latency is None:
        for item in considered:
            if item.latency_ms is not None:
                latency = item.latency_ms
                break

    return StreamHealth(
        status=status,
        success_rate=round(success_rate, 4),
        consecutive_successes=consecutive_successes,
        consecutive_failures=consecutive_failures,
        total_considered=len(considered),
        last_checked=considered[0].checked_at,
        latency_ms=latency,
    )
