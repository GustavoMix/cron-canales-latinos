from dataclasses import replace

from channelwatch.filters import filter_candidate
from channelwatch.models import ChannelCandidate, Settings


def candidate(url="https://cdn.example/live.m3u8", name="Canal Uno"):
    return ChannelCandidate(
        name=name,
        url=url,
        source_ids={"test"},
        country_code="BO",
    )


def test_accepts_normal_http_or_https_direct_media_url():
    decision = filter_candidate(candidate(), Settings())
    assert decision.accepted is True
    assert decision.reason == ""


def test_rejects_embedded_credentials():
    decision = filter_candidate(candidate("https://user:pass@cdn.example/live.m3u8"), Settings())
    assert decision.accepted is False
    assert decision.reason == "embedded_credentials"


def test_rejects_obvious_temporary_auth_query_parameters():
    decision = filter_candidate(candidate("https://cdn.example/live.m3u8?token=abc123"), Settings())
    assert decision.accepted is False
    assert decision.reason == "temporary_auth_url"


def test_rejects_known_page_urls_instead_of_direct_hls():
    decision = filter_candidate(candidate("https://www.youtube.com/channel/abc/live"), Settings())
    assert decision.accepted is False
    assert decision.reason == "page_url_not_direct_media"


def test_rejects_blocked_adult_name_patterns():
    settings = replace(Settings(), blocked_name_patterns=("adult", "xxx"))
    decision = filter_candidate(candidate(name="Adult TV"), settings)
    assert decision.accepted is False
    assert decision.reason == "blocked_name"


def test_can_disable_plain_http_sources():
    settings = replace(Settings(), allow_http=False)
    decision = filter_candidate(candidate("http://cdn.example/live.m3u8"), settings)
    assert decision.accepted is False
    assert decision.reason == "http_disabled"
