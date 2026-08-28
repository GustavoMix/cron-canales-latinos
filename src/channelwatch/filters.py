from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

from .models import ChannelCandidate, FilterDecision, Settings

_TEMP_KEYS = {
    "token",
    "auth",
    "authorization",
    "expires",
    "expire",
    "expiry",
    "signature",
    "sig",
    "hdnts",
    "jwt",
    "session",
    "policy",
    "key-pair-id",
    "key_pair_id",
}
_PAGE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "twitch.tv",
    "www.twitch.tv",
    "dailymotion.com",
    "www.dailymotion.com",
}


def filter_candidate(candidate: ChannelCandidate, settings: Settings) -> FilterDecision:
    if not candidate.name.strip():
        return FilterDecision(False, "blank_name")
    if not candidate.url.strip():
        return FilterDecision(False, "blank_url")

    parsed = urlparse(candidate.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return FilterDecision(False, "unsupported_scheme")
    if parsed.username or parsed.password:
        return FilterDecision(False, "embedded_credentials")
    if parsed.scheme == "http" and not settings.allow_http:
        return FilterDecision(False, "http_disabled")

    host = (parsed.hostname or "").lower()
    if host in _PAGE_HOSTS and not parsed.path.lower().endswith(".m3u8"):
        return FilterDecision(False, "page_url_not_direct_media")

    if settings.block_temporary_urls:
        query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
        if query_keys & _TEMP_KEYS:
            return FilterDecision(False, "temporary_auth_url")

    lower_name = candidate.name.casefold()
    if any(pattern.casefold() in lower_name for pattern in settings.blocked_name_patterns):
        return FilterDecision(False, "blocked_name")

    return FilterDecision(True, "")
