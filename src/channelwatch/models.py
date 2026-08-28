from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

SourceMode = Literal["fixed", "attribute"]
CorsState = Literal["allowed", "blocked", "unknown"]
HealthStatus = Literal["stable", "warming", "degraded", "offline"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass(slots=True, frozen=True)
class SourceTemplate:
    id: str
    mode: SourceMode
    priority: int = 0
    url: str = ""
    url_template: str = ""


@dataclass(slots=True, frozen=True)
class SourceSpec:
    id: str
    url: str
    mode: SourceMode
    country_code: str
    priority: int = 0


@dataclass(slots=True, frozen=True)
class CountryConfig:
    code: str
    name: str
    custom_urls: tuple[str, ...] = ()


@dataclass(slots=True, frozen=True)
class Settings:
    source_timeout_seconds: float = 8.0
    stream_timeout_seconds: float = 4.0
    channel_timeout_seconds: float = 8.0
    global_concurrency: int = 80
    per_host_concurrency: int = 6
    country_concurrency: int = 4
    history_window: int = 5
    min_consecutive_successes: int = 2
    min_success_rate: float = 0.8
    bootstrap_rounds: int = 2
    bootstrap_pause_seconds: float = 1.0
    max_history_rows_per_stream: int = 20
    allow_http: bool = True
    block_temporary_urls: bool = True
    web_origin: str = ""
    user_agent: str = "ChannelWatch/0.3"
    output_dir: str = "public/data"
    state_dir: str = "state"
    drop_guard_ratio: float = 0.3
    drop_guard_min_previous: int = 10
    blocked_name_patterns: tuple[str, ...] = ("xxx", "adult", "porn", "porno")
    builtin_sources: tuple[SourceTemplate, ...] = ()


@dataclass(slots=True)
class ChannelCandidate:
    name: str
    url: str
    source_ids: set[str]
    country_code: str
    tvg_id: str = ""
    logo: str = ""
    group: str = ""
    tvg_country: str = ""
    attributes: dict[str, str] = field(default_factory=dict)
    source_priority: int = 0


@dataclass(slots=True)
class ChannelGroup:
    key: str
    name: str
    country_code: str
    tvg_id: str
    logo: str
    group: str
    streams: list[ChannelCandidate] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class FilterDecision:
    accepted: bool
    reason: str = ""


@dataclass(slots=True, frozen=True)
class CheckResult:
    url: str
    success: bool
    checked_at: str
    latency_ms: int | None = None
    error: str = ""
    media_url: str = ""
    segment_url: str = ""
    cors: CorsState = "unknown"
    https: bool = False
    android_playable: bool = False
    web_playable: bool | None = None


@dataclass(slots=True, frozen=True)
class HealthRecord:
    checked_at: str
    success: bool
    latency_ms: int | None
    error: str = ""


@dataclass(slots=True, frozen=True)
class StreamHealth:
    status: HealthStatus
    success_rate: float
    consecutive_successes: int
    consecutive_failures: int
    total_considered: int
    last_checked: str
    latency_ms: int | None


@dataclass(slots=True, frozen=True)
class SourceHealth:
    id: str
    url: str
    success: bool
    error: str = ""
    candidate_count: int = 0


@dataclass(slots=True)
class CountrySourceLoad:
    country_code: str
    candidates: list[ChannelCandidate]
    sources: list[SourceHealth]


@dataclass(slots=True)
class EvaluatedStream:
    candidate: ChannelCandidate
    check: CheckResult
    health: StreamHealth
    score: float = 0.0


@dataclass(slots=True)
class RankedChannel:
    key: str
    name: str
    country_code: str
    tvg_id: str
    logo: str
    category: str
    primary: EvaluatedStream
    alternates: list[EvaluatedStream] = field(default_factory=list)


@dataclass(slots=True)
class CountryRunResult:
    country: CountryConfig
    channels: list[RankedChannel]
    sources: list[SourceHealth]
    discovered_candidates: int
    rejected_candidates: int
    bootstrap_rounds: int

    @property
    def successful_sources(self) -> int:
        return sum(1 for source in self.sources if source.success)


@dataclass(slots=True, frozen=True)
class PublishOutcome:
    country_code: str
    status: str
    path: str
    channel_count: int
