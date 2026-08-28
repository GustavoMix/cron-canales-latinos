import json
from dataclasses import replace

from channelwatch.models import (
    ChannelCandidate,
    CheckResult,
    CountryConfig,
    CountryRunResult,
    EvaluatedStream,
    RankedChannel,
    Settings,
    SourceHealth,
    StreamHealth,
)
from channelwatch.publisher import Publisher


def ranked(name="Bolivia TV", key="boliviatv.bo", suffix="1"):
    candidate = ChannelCandidate(
        name=name,
        url=f"https://cdn.test/{suffix}/live.m3u8",
        source_ids={"iptv_org", "free_tv"},
        country_code="BO",
        tvg_id=key,
        logo="https://img.test/logo.png",
    )
    check = CheckResult(
        url=candidate.url,
        success=True,
        checked_at="2026-08-28T10:00:00Z",
        latency_ms=123,
        cors="allowed",
        https=True,
        android_playable=True,
        web_playable=True,
    )
    health = StreamHealth(
        status="stable",
        success_rate=1.0,
        consecutive_successes=3,
        consecutive_failures=0,
        total_considered=3,
        last_checked="2026-08-28T10:00:00Z",
        latency_ms=123,
    )
    return RankedChannel(
        key=key,
        name=name,
        country_code="BO",
        tvg_id=key,
        logo=candidate.logo,
        category="General",
        primary=EvaluatedStream(candidate, check, health, 1000),
        alternates=[],
    )


def run_result(channels, sources=None):
    return CountryRunResult(
        country=CountryConfig("BO", "Bolivia"),
        channels=channels,
        sources=sources
        if sources is not None
        else [SourceHealth("iptv_org", "https://repo.test/bo.m3u", True, "", 5)],
        discovered_candidates=5,
        rejected_candidates=1,
        bootstrap_rounds=2,
    )


def test_publish_country_writes_expected_schema_atomically(tmp_path):
    settings = replace(Settings(), output_dir=str(tmp_path))
    publisher = Publisher(settings)

    outcome = publisher.publish_country(run_result([ranked()]))

    assert outcome.status == "published"
    payload = json.loads((tmp_path / "bo.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["country"] == {"code": "BO", "name": "Bolivia"}
    assert payload["total_channels"] == 1
    assert payload["channels"][0]["stream"] == "https://cdn.test/1/live.m3u8"
    assert payload["channels"][0]["status"] == "stable"
    assert payload["channels"][0]["sources"] == ["free_tv", "iptv_org"]
    assert payload["channels"][0]["web_playable"] is True
    assert not list(tmp_path.glob("*.tmp"))


def test_all_source_failure_preserves_previous_country_json(tmp_path):
    existing = {"marker": "keep-me", "total_channels": 12}
    path = tmp_path / "bo.json"
    path.write_text(json.dumps(existing), encoding="utf-8")
    settings = replace(Settings(), output_dir=str(tmp_path))
    publisher = Publisher(settings)
    result = run_result([], sources=[SourceHealth("iptv_org", "x", False, "timeout", 0)])

    outcome = publisher.publish_country(result)

    assert outcome.status == "preserved"
    assert json.loads(path.read_text(encoding="utf-8")) == existing


def test_large_drop_is_quarantined_instead_of_replacing_good_feed(tmp_path):
    old = {"schema_version": 1, "total_channels": 20, "channels": []}
    path = tmp_path / "bo.json"
    path.write_text(json.dumps(old), encoding="utf-8")
    settings = replace(
        Settings(),
        output_dir=str(tmp_path),
        drop_guard_ratio=0.30,
        drop_guard_min_previous=10,
    )
    publisher = Publisher(settings)
    new_channels = [ranked("One", "one.bo", "1"), ranked("Two", "two.bo", "2")]

    outcome = publisher.publish_country(run_result(new_channels))

    assert outcome.status == "quarantined"
    assert json.loads(path.read_text(encoding="utf-8")) == old
    candidate = json.loads((tmp_path / "quarantine/bo-candidate.json").read_text(encoding="utf-8"))
    assert candidate["total_channels"] == 2


def test_force_publish_bypasses_large_drop_guard(tmp_path):
    path = tmp_path / "bo.json"
    path.write_text(json.dumps({"total_channels": 20}), encoding="utf-8")
    settings = replace(Settings(), output_dir=str(tmp_path), drop_guard_ratio=0.30, drop_guard_min_previous=10)
    publisher = Publisher(settings)

    outcome = publisher.publish_country(run_result([ranked()]), force=True)

    assert outcome.status == "published"
    assert json.loads(path.read_text(encoding="utf-8"))["total_channels"] == 1


def test_publish_index_reads_existing_country_feeds(tmp_path):
    (tmp_path / "bo.json").write_text(
        json.dumps({"country": {"code": "BO", "name": "Bolivia"}, "total_channels": 7, "generated_at": "x"}),
        encoding="utf-8",
    )
    (tmp_path / "ar.json").write_text(
        json.dumps({"country": {"code": "AR", "name": "Argentina"}, "total_channels": 9, "generated_at": "y"}),
        encoding="utf-8",
    )
    publisher = Publisher(replace(Settings(), output_dir=str(tmp_path)))

    publisher.publish_index({"BO": CountryConfig("BO", "Bolivia"), "AR": CountryConfig("AR", "Argentina")})

    index = json.loads((tmp_path / "countries.json").read_text(encoding="utf-8"))
    assert [(x["code"], x["channels"], x["path"]) for x in index["countries"]] == [
        ("AR", 9, "ar.json"),
        ("BO", 7, "bo.json"),
    ]
