# ChannelWatch Cron Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a production-ready Python cron that aggregates two built-in public IPTV sources plus future custom sources per country, deeply validates HLS streams, stores health in SQLite, and atomically publishes stable country JSON feeds.

**Architecture:** Async ingestion and HLS checks feed a small SQLite health store. Candidates are normalized, filtered, deduplicated, stability-gated and ranked before country JSON is written atomically with large-drop protection. GitHub Actions can persist state in cache and deploy `public/` to Pages.

**Tech Stack:** Python 3.11+, standard library, httpx, SQLite, pytest, pytest-asyncio, GitHub Actions, Docker.

**Spec:** `docs/superpowers/specs/2026-08-28-channelwatch-design.md`

## Global Constraints
- Two built-in sources per country: IPTV-org country playlist and Free-TV global playlist filtered by `tvg-country`.
- Unlimited future `custom_urls` are configurable independently per country.
- Only public/authorized HTTP(S) M3U inputs; no credentials/private subscription handling.
- Published feeds contain only stable streams: current success, >=2 consecutive successes, >=80% success rate over last 5 checks.
- Fresh state performs 2 bootstrap rounds.
- Deep HLS validation must reach a live media playlist and a real segment/part, plus encryption key when present.
- Writes are atomic and large suspicious channel-count drops are quarantined.
- 20 initial countries listed in the spec.

---

### Task 1: Project configuration and models

**Files:**
- Create: `pyproject.toml`
- Create: `config/settings.toml`
- Create: `config/countries.toml`
- Create: `src/channelwatch/models.py`
- Create: `src/channelwatch/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `load_settings(path) -> Settings`, `load_countries(path) -> dict[str, CountryConfig]`, dataclasses for candidates/checks/health.

- [ ] Write failing tests for 20 countries, built-in source expansion, and unlimited custom URL expansion.
- [ ] Run `pytest tests/test_config.py -v` and confirm missing modules fail.
- [ ] Implement configuration dataclasses/loaders and source-spec expansion.
- [ ] Re-run tests and confirm pass.

### Task 2: M3U parsing, normalization, filtering and deduplication

**Files:**
- Create: `src/channelwatch/m3u.py`
- Create: `src/channelwatch/filters.py`
- Create: `src/channelwatch/dedupe.py`
- Test: `tests/test_m3u.py`
- Test: `tests/test_filters.py`
- Test: `tests/test_dedupe.py`

**Interfaces:**
- Produces: `parse_m3u(text, source_id, default_country)`, `filter_candidate(candidate, settings)`, `merge_candidates(candidates)`.

- [ ] Write failing parser tests for EXTINF attributes, country filtering, URL extraction, and Unicode flags.
- [ ] Implement parser minimally and pass tests.
- [ ] Write failing filter tests for credentials, temporary tokens, page URLs, adult patterns, and valid direct HLS URLs.
- [ ] Implement filters and pass tests.
- [ ] Write failing dedupe tests for tvg-id grouping, normalized-name fallback, same-URL source merging, and alternate preservation.
- [ ] Implement dedupe and pass tests.

### Task 3: Deep async HLS checker

**Files:**
- Create: `src/channelwatch/hls.py`
- Test: `tests/test_hls.py`

**Interfaces:**
- Produces: `HlsChecker.check(StreamCandidate) -> CheckResult` and `HlsChecker.check_url(url) -> CheckResult`.

- [ ] Write failing async test for master playlist -> media playlist -> segment success using `httpx.MockTransport`.
- [ ] Implement master/media/segment resolution and pass test.
- [ ] Write failing tests for VOD endlist rejection, HTML masquerading as media, LL-HLS part support, key validation, redirects, and CORS metadata.
- [ ] Implement each behavior minimally and pass all HLS tests.
- [ ] Add global and per-host semaphores and verify concurrency behavior with a focused test.

### Task 4: SQLite rolling health and stability gate

**Files:**
- Create: `src/channelwatch/store.py`
- Create: `src/channelwatch/stability.py`
- Test: `tests/test_store.py`
- Test: `tests/test_stability.py`

**Interfaces:**
- Produces: `HealthStore.record(...)`, `HealthStore.recent(...)`, `classify_health(checks, settings) -> StreamHealth`.

- [ ] Write failing persistence test and implement SQLite schema/record/query/pruning.
- [ ] Write failing stability tests for warming -> stable, degraded, offline, 80% rolling threshold.
- [ ] Implement classification and pass tests.

### Task 5: Source loader and run orchestration

**Files:**
- Create: `src/channelwatch/source_loader.py`
- Create: `src/channelwatch/ranking.py`
- Create: `src/channelwatch/runner.py`
- Test: `tests/test_source_loader.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Produces: `SourceLoader.load_country(...)`, `rank_channel_streams(...)`, `ChannelWatchRunner.run(...)`.

- [ ] Write failing test proving a shared global source URL is downloaded once then filtered for multiple countries.
- [ ] Implement source fetch cache and country filtering.
- [ ] Write failing ranking tests for health, HTTPS, latency, source multiplicity and alternates.
- [ ] Implement ranking.
- [ ] Write failing runner integration test with fake source loader/checker/store proving bootstrap rounds and stable-only output model.
- [ ] Implement runner orchestration and pass tests.

### Task 6: Fail-safe atomic JSON publishing

**Files:**
- Create: `src/channelwatch/publisher.py`
- Test: `tests/test_publisher.py`

**Interfaces:**
- Produces: `Publisher.publish_country(...)`, `Publisher.publish_index(...)`.

- [ ] Write failing atomic-output schema test.
- [ ] Implement deterministic JSON payload and atomic replace.
- [ ] Write failing test for all-source failure preserving previous output.
- [ ] Implement preservation behavior.
- [ ] Write failing large-drop guard test and implement quarantine behavior.

### Task 7: CLI and operational packaging

**Files:**
- Create: `src/channelwatch/__init__.py`
- Create: `src/channelwatch/__main__.py`
- Create: `src/channelwatch/cli.py`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `scripts/run_windows.ps1`
- Create: `.github/workflows/check-and-publish.yml`
- Create: `public/index.html`
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces CLI commands `run`, `check-url`, `validate-config`, `list-countries`.

- [ ] Write failing CLI parser tests and implement commands.
- [ ] Add Docker and Windows launchers.
- [ ] Add scheduled GitHub Actions generation + Pages deployment with SQLite cache.

### Task 8: Documentation and final verification

**Files:**
- Create: `README.md`
- Create: `docs/ADD_SOURCES.md`
- Create: `docs/WEB_INTEGRATION.md`
- Create: `.gitignore`
- Create: `.env.example`

**Interfaces:** Documentation only.

- [ ] Document Windows setup, local run, cron behavior, adding custom source URLs, adding new countries, JSON schema, Next.js fetch example, Kotlin consumption, GitHub Pages deployment, and legal/public-source boundary.
- [ ] Run `pytest -q`.
- [ ] Run `python -m channelwatch validate-config`.
- [ ] Run `python -m channelwatch list-countries` and verify 20 countries.
- [ ] Run a fully mocked/offline integration generation test.
- [ ] Run `python -m compileall src`.
