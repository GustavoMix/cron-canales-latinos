# ChannelWatch Cron — Design

## Goal
Build a Python cron service that ingests multiple public/authorized M3U sources, validates live HLS streams deeply, remembers health history in SQLite, and publishes one stable JSON feed per country for a Next.js web app and Kotlin Android app.

## Scope
- 20 initial countries: Bolivia, Argentina, Brazil, Chile, Peru, Colombia, Ecuador, Paraguay, Uruguay, Venezuela, Mexico, Panama, Costa Rica, Guatemala, Honduras, El Salvador, Nicaragua, Dominican Republic, Puerto Rico, and Spain.
- Two built-in public sources are available for every country:
  1. IPTV-org country playlist: `https://iptv-org.github.io/iptv/countries/{cc}.m3u`.
  2. Free-TV global playlist: `https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8`, filtered using `tvg-country`.
- Every country has an unlimited `custom_urls` list prepared for future user-provided public/authorized M3U sources.
- The system does not accept credentials, Xtream account data, or private subscription lists.

## Architecture

```text
M3U sources (2 built-in + N custom per country)
                    |
                    v
            async source loader
                    |
                    v
               M3U parser
                    |
          normalize / filter / dedupe
                    |
                    v
             async HLS checker
       playlist -> media -> segment/key
                    |
                    v
                SQLite
          rolling stream health
                    |
             stable ranking
                    |
                    v
          atomic JSON publisher
                    |
      public/data/{country}.json
      public/data/countries.json
                    |
          Next.js / Kotlin clients
```

## Source handling
- Source URLs are fetched concurrently with an in-memory URL cache, so the Free-TV global playlist is downloaded only once per run even though it serves many countries.
- IPTV-org is treated as fixed-country input.
- Free-TV is filtered by the `tvg-country` M3U attribute.
- Custom URLs are configured under a country and are therefore treated as fixed-country input.
- If every source for a country fails to download, the previous published JSON is preserved.

## Channel normalization and filtering
A candidate is rejected before stream checking when any of the following is true:
- blank name or URL;
- scheme is not HTTP/HTTPS;
- URL embeds username/password credentials;
- known browser page URL instead of direct media (for example YouTube/Twitch page links);
- obvious temporary authorization/query parameters such as token, expires, signature, hdnts, jwt, session, auth, policy, key-pair-id;
- blocked adult-content name patterns.

Deduplication uses `tvg-id` when available, otherwise a normalized country + channel-name key. The same stream URL coming from multiple sources is merged. Different healthy URLs for the same channel remain as alternates.

## Deep HLS validation
A successful stream check requires all of these:
1. initial URL returns HTTP 2xx;
2. body is an HLS `#EXTM3U` playlist;
3. if it is a master playlist, at least one variant is resolved and fetched;
4. media playlist is live (no `#EXT-X-ENDLIST`);
5. at least one media segment or low-latency HLS part exists;
6. one segment/part can be fetched successfully using a small byte range;
7. if the playlist references an encryption key, that key is also reachable;
8. responses are not HTML masquerading as media.

Checks use bounded global concurrency and bounded per-host concurrency to avoid hammering broadcasters.

## Stability model
SQLite stores rolling checks per stream URL. A stream is publishable only when:
- its current check succeeds;
- it has at least 2 consecutive successful checks;
- its success rate over the most recent 5 checks is at least 80%.

A fresh database automatically performs two bootstrap rounds so a first deployment can promote genuinely healthy streams without waiting for a second cron execution.

Status semantics:
- `stable`: current success and stability gate passed;
- `warming`: current success but insufficient history;
- `degraded`: current failure but fewer than 2 consecutive failures;
- `offline`: 2+ consecutive failures.

## Ranking
For each deduplicated channel, stable candidate streams are ranked by:
1. rolling success rate and consecutive successes;
2. HTTPS preference;
3. lower observed latency;
4. appearance in multiple independent sources;
5. configurable source priority.

The top stream becomes `stream`; remaining stable streams become `alternates`.

## Web compatibility metadata
Every published channel includes:
- `android_playable`: true after successful direct-HLS validation;
- `https`: whether the stream is HTTPS;
- `cors`: `allowed`, `blocked`, or `unknown`;
- `web_playable`: true only when HLS succeeds, HTTPS is used, and CORS is allowed for a configured web origin. If no origin is configured, this value is null rather than guessed.

This metadata does not bypass CORS, geoblocking, tokens, DRM, or provider restrictions.

## Output
`public/data/{cc}.json` contains only channels with at least one stable stream. Schema:

```json
{
  "schema_version": 1,
  "country": {"code": "BO", "name": "Bolivia"},
  "generated_at": "2026-08-28T15:00:00Z",
  "source_health": [],
  "total_channels": 10,
  "channels": [
    {
      "id": "boliviatv.bo",
      "name": "Bolivia TV",
      "logo": "https://...",
      "category": "General",
      "stream": "https://.../index.m3u8",
      "alternates": [],
      "status": "stable",
      "stability": {"success_rate": 1.0, "consecutive_successes": 2},
      "latency_ms": 700,
      "sources": ["iptv_org"],
      "android_playable": true,
      "https": true,
      "cors": "unknown",
      "web_playable": null,
      "last_checked": "2026-08-28T15:00:00Z"
    }
  ]
}
```

`public/data/countries.json` is a lightweight index for clients. Writes are atomic. A large-drop safety guard quarantines suspicious outputs instead of replacing a healthy previous feed when the new channel count collapses unexpectedly.

## Operations
- Local/Windows/Linux CLI: `python -m channelwatch run`.
- Per-country test: `python -m channelwatch run --country BO`.
- URL diagnostic: `python -m channelwatch check-url <url>`.
- GitHub Actions workflow runs every 15 minutes, restores/saves SQLite state using Actions cache, runs tests, generates feeds, and deploys `public/` to GitHub Pages without committing generated JSON every cycle.
- Docker and Windows PowerShell runner are included.

## Safety and legal boundary
The built-in sources describe themselves as publicly available/free streams. Custom sources must likewise be public or authorized. The checker validates availability; it does not proxy, restream, defeat authentication, bypass geo restrictions, or remove access controls.
