# GitHub Weekly Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run ChannelWatch automatically once per week on GitHub, checking countries independently in parallel and publishing stable JSON feeds to GitHub Pages.

**Architecture:** A GitHub Actions matrix runs one country per job with a maximum of five jobs at once. Each job restores its country health history and the previous published snapshot, generates one country JSON, uploads it as an artifact, and a final deploy job overlays all successful artifacts on the previous snapshot, regenerates `countries.json`, and deploys `public/` to GitHub Pages.

**Tech Stack:** Python 3.12, pytest, GitHub Actions, GitHub Pages, actions/cache, actions/upload-artifact.

**Spec:** Approved in conversation on 2026-08-28: weekly execution, automatic/no prompts, country-parallel runs, JSON per country, GitHub Pages output, web origin inferred from the GitHub owner.

## Global Constraints

- Schedule: once per week, Sunday 08:00 UTC (04:00 Bolivia time).
- Matrix contains the 20 configured countries and uses `max-parallel: 5`.
- Manual `workflow_dispatch` remains available for an initial or emergency run and has no required inputs.
- Existing country JSON schema must not change.
- Existing local `PROBAR_LOCAL.bat` workflow must remain usable.
- Production web Origin is `https://<github-owner>.github.io` because GitHub Pages project sites share that browser origin.
- A failed country check must not erase the previously published country JSON.

---

### Task 1: Add standalone index publishing command

**Files:**
- Modify: `src/channelwatch/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: configured `publishing.output_dir` and existing `<country>.json` files.
- Produces: CLI command `python -m channelwatch publish-index` that writes `countries.json` without network checks.

- [ ] Write a failing parser/command test for `publish-index`.
- [ ] Run the focused CLI tests and confirm failure because the subcommand does not exist.
- [ ] Implement the minimal `publish-index` parser and command branch using `Publisher.publish_index()`.
- [ ] Run CLI tests and then the complete pytest suite.

### Task 2: Replace single-job workflow with weekly country matrix

**Files:**
- Modify: `.github/workflows/check-and-publish.yml`
- Create: `docs/GITHUB_SETUP.md`

**Interfaces:**
- Consumes: `config/countries.toml`, ChannelWatch CLI, GitHub cache/artifacts.
- Produces: 20 country artifacts, aggregated static site, weekly GitHub Pages deployment.

- [ ] Add a one-time `test` job.
- [ ] Add matrix `check-country` job with all 20 ISO codes, `fail-fast: false`, and `max-parallel: 5`.
- [ ] Restore per-country `.state/<CODE>` cache and shared previous published snapshot cache.
- [ ] Seed previous `<code>.json`, run exactly one country with noninteractive environment variables, and upload the resulting JSON artifact.
- [ ] Add `deploy` job that restores previous snapshot, merges all country artifacts, runs `publish-index`, saves the new snapshot, and deploys `public/` to Pages.
- [ ] Document exact GitHub repository names, Pages settings, first manual run, and weekly schedule.

### Task 3: Verify repository package

**Files:**
- Verify all project files.

**Interfaces:**
- Produces: repository ready to upload as `channelwatch-cron`.

- [ ] Run `pytest -q`.
- [ ] Run `python -m channelwatch validate-config`.
- [ ] Parse the workflow YAML if a YAML parser is available; otherwise perform structural checks for schedule, matrix, max-parallel, artifacts, index generation, and Pages deployment.
- [ ] Ensure no `.git`, `.pytest_cache`, generated database, or temporary output is included in the final ZIP.
