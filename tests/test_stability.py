from dataclasses import replace

from channelwatch.models import HealthRecord, Settings
from channelwatch.stability import classify_health


def row(success, minute, latency=100):
    return HealthRecord(
        checked_at=f"2026-08-28T10:{minute:02d}:00Z",
        success=success,
        latency_ms=latency,
        error="" if success else "timeout",
    )


SETTINGS = replace(
    Settings(),
    history_window=5,
    min_consecutive_successes=2,
    min_success_rate=0.8,
)


def test_one_success_is_warming():
    health = classify_health([row(True, 1)], SETTINGS)
    assert health.status == "warming"
    assert health.consecutive_successes == 1
    assert health.success_rate == 1.0


def test_two_consecutive_successes_are_stable():
    health = classify_health([row(True, 2), row(True, 1)], SETTINGS)
    assert health.status == "stable"
    assert health.consecutive_successes == 2


def test_success_rate_gate_requires_eighty_percent_of_recent_window():
    stable = classify_health(
        [row(True, 5), row(True, 4), row(True, 3), row(True, 2), row(False, 1)],
        SETTINGS,
    )
    warming = classify_health(
        [row(True, 5), row(True, 4), row(True, 3), row(False, 2), row(False, 1)],
        SETTINGS,
    )
    assert stable.status == "stable"
    assert stable.success_rate == 0.8
    assert warming.status == "warming"
    assert warming.success_rate == 0.6


def test_one_current_failure_is_degraded():
    health = classify_health([row(False, 3), row(True, 2), row(True, 1)], SETTINGS)
    assert health.status == "degraded"
    assert health.consecutive_failures == 1


def test_two_current_failures_are_offline():
    health = classify_health([row(False, 4), row(False, 3), row(True, 2), row(True, 1)], SETTINGS)
    assert health.status == "offline"
    assert health.consecutive_failures == 2
