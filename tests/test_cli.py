from pathlib import Path

from channelwatch.cli import build_parser, main

ROOT = Path(__file__).resolve().parents[1]


def test_run_parser_accepts_country_and_force_publish():
    parser = build_parser()
    args = parser.parse_args(["run", "--country", "BO", "--force-publish"])
    assert args.command == "run"
    assert args.country == ["BO"]
    assert args.force_publish is True


def test_run_parser_accepts_multiple_countries():
    parser = build_parser()
    args = parser.parse_args(["run", "--country", "BO", "--country", "AR"])
    assert args.country == ["BO", "AR"]


def test_validate_config_command_succeeds_offline(capsys):
    code = main(
        [
            "validate-config",
            "--settings",
            str(ROOT / "config/settings.toml"),
            "--countries",
            str(ROOT / "config/countries.toml"),
        ]
    )
    captured = capsys.readouterr().out
    assert code == 0
    assert "20 countries" in captured
    assert "iptv_org" in captured
    assert "free_tv" in captured


def test_list_countries_prints_all_initial_countries(capsys):
    code = main(["list-countries", "--countries", str(ROOT / "config/countries.toml")])
    lines = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert code == 0
    assert len(lines) == 20
    assert "BO  Bolivia" in lines
    assert "ES  España" in lines


def test_publish_index_command_builds_index_without_network(tmp_path, capsys):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "bo.json").write_text(
        '{"country":{"code":"BO","name":"Bolivia"},"total_channels":3,"generated_at":"x"}',
        encoding="utf-8",
    )
    settings = tmp_path / "settings.toml"
    settings.write_text(
        """
[checker]
source_timeout_seconds = 1
stream_timeout_seconds = 1
channel_timeout_seconds = 2
global_concurrency = 1
per_host_concurrency = 1
country_concurrency = 1
history_window = 5
min_consecutive_successes = 2
min_success_rate = 0.8
bootstrap_rounds = 2
bootstrap_pause_seconds = 0
max_history_rows_per_stream = 5
allow_http = true
block_temporary_urls = true
web_origin = ""
user_agent = "test"

[publishing]
output_dir = "PLACEHOLDER"
state_dir = "state"
drop_guard_ratio = 0.3
drop_guard_min_previous = 10

[filters]
blocked_name_patterns = []

[[builtin_sources]]
id = "one"
url_template = "https://example.test/{country_lower}.m3u"
mode = "fixed"
priority = 1

[[builtin_sources]]
id = "two"
url = "https://example.test/all.m3u"
mode = "attribute"
priority = 2
""".replace("PLACEHOLDER", data_dir.as_posix()),
        encoding="utf-8",
    )

    code = main(
        [
            "publish-index",
            "--settings",
            str(settings),
            "--countries",
            str(ROOT / "config/countries.toml"),
        ]
    )

    assert code == 0
    assert (data_dir / "countries.json").exists()
    assert "Index:" in capsys.readouterr().out
