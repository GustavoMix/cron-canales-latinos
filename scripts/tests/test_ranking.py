from channelwatch.models import (
    ChannelCandidate,
    ChannelGroup,
    CheckResult,
    StreamHealth,
)
from channelwatch.ranking import rank_channel_streams


def candidate(url, sources, priority=0):
    return ChannelCandidate(
        name="Canal 26",
        url=url,
        source_ids=set(sources),
        country_code="AR",
        tvg_id="Canal26.ar",
        source_priority=priority,
    )


def health(status="stable", success_rate=1.0, consecutive=3, latency=100):
    return StreamHealth(
        status=status,
        success_rate=success_rate,
        consecutive_successes=consecutive,
        consecutive_failures=0,
        total_considered=3,
        last_checked="2026-08-28T10:00:00Z",
        latency_ms=latency,
    )


def check(url, https=True, latency=100):
    return CheckResult(
        url=url,
        success=True,
        checked_at="2026-08-28T10:00:00Z",
        latency_ms=latency,
        https=https,
        android_playable=True,
    )


def test_https_stable_stream_beats_faster_http_stream_and_keeps_alternate():
    https_item = candidate("https://cdn.test/26.m3u8", {"iptv_org"}, 10)
    http_item = candidate("http://fast.test/26.m3u8", {"free_tv"}, 20)
    group = ChannelGroup("canal26.ar", "Canal 26", "AR", "Canal26.ar", "", "News", [https_item, http_item])
    evaluations = {
        https_item.url: (check(https_item.url, True, 500), health(latency=500)),
        http_item.url: (check(http_item.url, False, 50), health(latency=50)),
    }

    ranked = rank_channel_streams(group, evaluations)

    assert ranked is not None
    assert ranked.primary.candidate.url == https_item.url
    assert [alt.candidate.url for alt in ranked.alternates] == [http_item.url]


def test_non_stable_streams_are_not_publishable():
    item = candidate("https://cdn.test/26.m3u8", {"iptv_org"})
    group = ChannelGroup("canal26.ar", "Canal 26", "AR", "Canal26.ar", "", "", [item])
    evaluations = {item.url: (check(item.url), health(status="warming", consecutive=1))}

    assert rank_channel_streams(group, evaluations) is None


def test_same_health_prefers_stream_seen_in_more_sources():
    one = candidate("https://one.test/live.m3u8", {"iptv_org"}, 10)
    two = candidate("https://two.test/live.m3u8", {"iptv_org", "free_tv"}, 10)
    group = ChannelGroup("x.ar", "X", "AR", "X.ar", "", "", [one, two])
    evaluations = {
        one.url: (check(one.url, True, 100), health(latency=100)),
        two.url: (check(two.url, True, 100), health(latency=100)),
    }

    ranked = rank_channel_streams(group, evaluations)
    assert ranked.primary.candidate.url == two.url
