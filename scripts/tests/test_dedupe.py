from channelwatch.dedupe import merge_candidates
from channelwatch.models import ChannelCandidate


def item(name, url, source, tvg_id="", logo="", group=""):
    return ChannelCandidate(
        name=name,
        url=url,
        source_ids={source},
        country_code="AR",
        tvg_id=tvg_id,
        logo=logo,
        group=group,
    )


def test_tvg_id_groups_multiple_urls_as_alternates():
    groups = merge_candidates(
        [
            item("Canal 26", "https://a.test/26.m3u8", "iptv_org", tvg_id="Canal26.ar"),
            item("Canal 26 HD", "https://b.test/26.m3u8", "free_tv", tvg_id="Canal26.ar"),
        ]
    )

    assert len(groups) == 1
    assert groups[0].key == "canal26.ar"
    assert {s.url for s in groups[0].streams} == {
        "https://a.test/26.m3u8",
        "https://b.test/26.m3u8",
    }


def test_same_url_merges_source_ids_instead_of_duplicate_streams():
    groups = merge_candidates(
        [
            item("Canal 26", "https://a.test/26.m3u8", "iptv_org", tvg_id="Canal26.ar"),
            item("Canal 26", "https://a.test/26.m3u8", "free_tv", tvg_id="Canal26.ar"),
        ]
    )
    assert len(groups[0].streams) == 1
    assert groups[0].streams[0].source_ids == {"iptv_org", "free_tv"}


def test_normalized_name_fallback_merges_hd_suffix_when_tvg_id_missing():
    groups = merge_candidates(
        [
            item("Canal 26 HD", "https://a.test/live.m3u8", "one"),
            item("Canal 26", "https://b.test/live.m3u8", "two"),
        ]
    )
    assert len(groups) == 1
    assert groups[0].key == "ar:canal26"


def test_group_metadata_uses_non_empty_logo_and_group():
    groups = merge_candidates(
        [
            item("Canal X", "https://a.test/live.m3u8", "one", tvg_id="X.ar"),
            item(
                "Canal X",
                "https://b.test/live.m3u8",
                "two",
                tvg_id="X.ar",
                logo="https://img.test/x.png",
                group="News",
            ),
        ]
    )
    assert groups[0].logo == "https://img.test/x.png"
    assert groups[0].group == "News"
