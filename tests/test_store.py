from channelwatch.models import CheckResult
from channelwatch.store import HealthStore


def result(success, checked_at, latency=100, error=""):
    return CheckResult(
        url="https://cdn.test/live.m3u8",
        success=success,
        checked_at=checked_at,
        latency_ms=latency,
        error=error,
    )


def test_sqlite_health_persists_between_instances(tmp_path):
    db = tmp_path / "health.db"
    store = HealthStore(db, max_history_rows_per_stream=20)
    store.record("https://cdn.test/live.m3u8", "BO", "canal", result(True, "2026-08-28T10:00:00Z"))
    store.close()

    reopened = HealthStore(db, max_history_rows_per_stream=20)
    rows = reopened.recent("https://cdn.test/live.m3u8", limit=5)
    reopened.close()

    assert len(rows) == 1
    assert rows[0].success is True
    assert rows[0].checked_at == "2026-08-28T10:00:00Z"


def test_store_prunes_old_rows_per_stream(tmp_path):
    db = tmp_path / "health.db"
    store = HealthStore(db, max_history_rows_per_stream=3)
    for i in range(5):
        store.record(
            "https://cdn.test/live.m3u8",
            "BO",
            "canal",
            result(True, f"2026-08-28T10:0{i}:00Z", latency=100 + i),
        )

    rows = store.recent("https://cdn.test/live.m3u8", limit=10)
    store.close()

    assert len(rows) == 3
    assert [row.checked_at for row in rows] == [
        "2026-08-28T10:04:00Z",
        "2026-08-28T10:03:00Z",
        "2026-08-28T10:02:00Z",
    ]


def test_has_history_changes_after_first_record(tmp_path):
    store = HealthStore(tmp_path / "health.db", max_history_rows_per_stream=5)
    assert store.has_history() is False
    store.record("https://cdn.test/live.m3u8", "BO", "canal", result(True, "2026-08-28T10:00:00Z"))
    assert store.has_history() is True
    store.close()


def test_has_country_history_is_scoped_per_country(tmp_path):
    store = HealthStore(tmp_path / "health.db", max_history_rows_per_stream=5)
    store.record("https://cdn.test/bo.m3u8", "BO", "bo", result(True, "2026-08-28T10:00:00Z"))
    assert store.has_country_history("BO") is True
    assert store.has_country_history("AR") is False
    store.close()


def test_country_bootstrap_is_complete_only_after_explicit_completion(tmp_path):
    store = HealthStore(tmp_path / "health.db", max_history_rows_per_stream=5)
    store.record("https://cdn.test/bo.m3u8", "BO", "bo", result(True, "2026-08-28T10:00:00Z"))

    assert store.has_completed_country_run("BO") is False

    store.mark_country_run_complete("BO", "2026-08-28T10:01:00Z")
    assert store.has_completed_country_run("BO") is True
    assert store.has_completed_country_run("AR") is False
    store.close()


def test_clear_country_history_removes_only_that_country(tmp_path):
    store = HealthStore(tmp_path / "health.db", max_history_rows_per_stream=5)
    store.record("https://cdn.test/bo.m3u8", "BO", "bo", result(True, "2026-08-28T10:00:00Z"))
    store.record("https://cdn.test/ar.m3u8", "AR", "ar", result(True, "2026-08-28T10:00:00Z"))

    store.clear_country_history("BO")

    assert store.recent("https://cdn.test/bo.m3u8", 5) == []
    assert len(store.recent("https://cdn.test/ar.m3u8", 5)) == 1
    store.close()
