from pathlib import Path

from channelwatch.config import build_source_specs, load_countries, load_settings

ROOT = Path(__file__).resolve().parents[1]


def test_loads_twenty_initial_countries():
    countries = load_countries(ROOT / "config/countries.toml")
    assert len(countries) == 20
    assert countries["BO"].name == "Bolivia"
    assert countries["ES"].name == "España"


def test_builds_two_builtin_sources_for_each_country():
    settings = load_settings(ROOT / "config/settings.toml")
    countries = load_countries(ROOT / "config/countries.toml")

    specs = build_source_specs(settings, countries["BO"])

    assert [(s.id, s.mode) for s in specs] == [
        ("iptv_org", "fixed"),
        ("free_tv", "attribute"),
    ]
    assert specs[0].url.endswith("/bo.m3u")
    assert specs[1].url.endswith("/Free-TV/IPTV/master/playlist.m3u8")


def test_custom_sources_are_unlimited_and_fixed_to_country(tmp_path):
    countries_file = tmp_path / "countries.toml"
    countries_file.write_text(
        """
[countries.BO]
name = "Bolivia"
custom_urls = [
  "https://example.test/one.m3u",
  "https://example.test/two.m3u",
  "https://example.test/three.m3u",
]
""".strip(),
        encoding="utf-8",
    )
    settings = load_settings(ROOT / "config/settings.toml")
    country = load_countries(countries_file)["BO"]

    specs = build_source_specs(settings, country)
    custom = [s for s in specs if s.id.startswith("custom_")]

    assert len(custom) == 3
    assert [s.url for s in custom] == [
        "https://example.test/one.m3u",
        "https://example.test/two.m3u",
        "https://example.test/three.m3u",
    ]
    assert all(s.mode == "fixed" and s.country_code == "BO" for s in custom)


def test_fast_defaults_include_a_total_channel_timeout():
    settings = load_settings(ROOT / "config/settings.toml")
    assert settings.channel_timeout_seconds <= 8.0
    assert settings.stream_timeout_seconds <= 5.0
    assert settings.global_concurrency >= 50
    assert settings.per_host_concurrency >= 4
