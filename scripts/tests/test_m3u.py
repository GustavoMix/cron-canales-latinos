from channelwatch.m3u import parse_m3u


def test_parses_extinf_attributes_country_and_url():
    text = """#EXTM3U
#EXTINF:-1 tvg-id="BoliviaTV.bo@SD" tvg-logo="https://img.test/bo.png" tvg-country="BO" group-title="Bolivia",Bolivia TV Ⓢ
https://cdn.test/bolivia/index.m3u8
"""
    channels = parse_m3u(text, source_id="free_tv", default_country="")

    assert len(channels) == 1
    item = channels[0]
    assert item.name == "Bolivia TV"
    assert item.tvg_id == "BoliviaTV.bo@SD"
    assert item.logo == "https://img.test/bo.png"
    assert item.tvg_country == "BO"
    assert item.country_code == "BO"
    assert item.group == "Bolivia"
    assert item.url == "https://cdn.test/bolivia/index.m3u8"
    assert item.source_ids == {"free_tv"}


def test_default_country_is_used_when_playlist_has_no_country_attribute():
    text = """#EXTM3U
#EXTINF:-1 tvg-id="ATBLaPaz.bo",ATB La Paz
https://cdn.test/atb/index.m3u8
"""
    channels = parse_m3u(text, source_id="iptv_org", default_country="BO")
    assert channels[0].country_code == "BO"


def test_comma_inside_quoted_attribute_does_not_break_display_name():
    text = """#EXTM3U
#EXTINF:-1 tvg-name="Noticias, Ahora" tvg-country="AR",Canal Noticias
https://cdn.test/news.m3u8
"""
    channels = parse_m3u(text, source_id="source", default_country="")
    assert channels[0].attributes["tvg-name"] == "Noticias, Ahora"
    assert channels[0].name == "Canal Noticias"


def test_ignores_orphan_urls_without_extinf():
    text = """#EXTM3U
https://cdn.test/orphan.m3u8
#EXTINF:-1,Valid
https://cdn.test/valid.m3u8
"""
    channels = parse_m3u(text, source_id="source", default_country="BO")
    assert [c.name for c in channels] == ["Valid"]
