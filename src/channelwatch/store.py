from __future__ import annotations

import sqlite3
from pathlib import Path

from .models import CheckResult, HealthRecord


class HealthStore:
    def __init__(self, path: str | Path, max_history_rows_per_stream: int = 20):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_history_rows_per_stream = max(1, int(max_history_rows_per_stream))
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=5000")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS stream_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                country_code TEXT NOT NULL,
                channel_key TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                success INTEGER NOT NULL,
                latency_ms INTEGER,
                error TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_stream_checks_url_id ON stream_checks(url, id DESC)"
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS country_runs (
                country_code TEXT PRIMARY KEY,
                completed_at TEXT NOT NULL
            )
            """
        )
        self.conn.commit()

    def record(self, url: str, country_code: str, channel_key: str, result: CheckResult) -> None:
        self.conn.execute(
            """
            INSERT INTO stream_checks(url, country_code, channel_key, checked_at, success, latency_ms, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                country_code,
                channel_key,
                result.checked_at,
                1 if result.success else 0,
                result.latency_ms,
                result.error,
            ),
        )
        self.conn.execute(
            """
            DELETE FROM stream_checks
            WHERE url = ?
              AND id NOT IN (
                SELECT id FROM stream_checks
                WHERE url = ?
                ORDER BY id DESC
                LIMIT ?
              )
            """,
            (url, url, self.max_history_rows_per_stream),
        )
        self.conn.commit()

    def recent(self, url: str, limit: int = 5) -> list[HealthRecord]:
        rows = self.conn.execute(
            """
            SELECT checked_at, success, latency_ms, error
            FROM stream_checks
            WHERE url = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (url, max(1, int(limit))),
        ).fetchall()
        return [
            HealthRecord(
                checked_at=row[0],
                success=bool(row[1]),
                latency_ms=row[2],
                error=row[3] or "",
            )
            for row in rows
        ]

    def has_history(self) -> bool:
        row = self.conn.execute("SELECT 1 FROM stream_checks LIMIT 1").fetchone()
        return row is not None

    def has_country_history(self, country_code: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM stream_checks WHERE country_code = ? LIMIT 1",
            (country_code.upper(),),
        ).fetchone()
        return row is not None



    def clear_country_history(self, country_code: str) -> None:
        self.conn.execute(
            "DELETE FROM stream_checks WHERE country_code = ?",
            (country_code.upper(),),
        )
        self.conn.commit()

    def has_completed_country_run(self, country_code: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM country_runs WHERE country_code = ? LIMIT 1",
            (country_code.upper(),),
        ).fetchone()
        return row is not None

    def mark_country_run_complete(self, country_code: str, completed_at: str) -> None:
        self.conn.execute(
            """
            INSERT INTO country_runs(country_code, completed_at)
            VALUES (?, ?)
            ON CONFLICT(country_code) DO UPDATE SET completed_at = excluded.completed_at
            """,
            (country_code.upper(), completed_at),
        )
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
