from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


KST = ZoneInfo("Asia/Seoul")


SCHEMA = """
CREATE TABLE IF NOT EXISTS dashboard_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL,
    message TEXT
);

CREATE TABLE IF NOT EXISTS market_metrics (
    market TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    group_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    label TEXT NOT NULL,
    value TEXT NOT NULL,
    delta TEXT,
    tone TEXT NOT NULL DEFAULT 'neutral',
    note TEXT,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, as_of_date, group_name, sort_order, label)
);

CREATE TABLE IF NOT EXISTS sector_cards (
    market TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    tone TEXT NOT NULL DEFAULT 'neutral',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, as_of_date, sort_order)
);

CREATE TABLE IF NOT EXISTS issue_alerts (
    market TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, as_of_date, sort_order)
);

CREATE TABLE IF NOT EXISTS stock_ideas (
    market TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    rank INTEGER NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    rating INTEGER NOT NULL,
    big_picture TEXT NOT NULL,
    inflection TEXT NOT NULL,
    beneficiary_json TEXT NOT NULL,
    risk TEXT NOT NULL,
    rise_etf TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, as_of_date, rank)
);

CREATE TABLE IF NOT EXISTS calendar_events (
    market TEXT NOT NULL,
    as_of_date TEXT NOT NULL,
    event_date TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    region TEXT NOT NULL,
    label TEXT NOT NULL,
    body TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (market, as_of_date, event_date, sort_order)
);
"""


def now_kst() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def connect(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def start_run(conn: sqlite3.Connection, market: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO dashboard_runs (market, started_at, status)
        VALUES (?, ?, ?)
        """,
        (market, now_kst(), "RUNNING"),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(conn: sqlite3.Connection, run_id: int, status: str, message: str = "") -> None:
    conn.execute(
        """
        UPDATE dashboard_runs
        SET ended_at = ?, status = ?, message = ?
        WHERE id = ?
        """,
        (now_kst(), status, message, run_id),
    )
    conn.commit()


def replace_payload(conn: sqlite3.Connection, market: str, payload: dict[str, Any]) -> None:
    as_of_date = payload["as_of_date"]
    updated_at = payload["updated_at"]
    _replace_metrics(conn, market, as_of_date, updated_at, payload.get("metrics", []))
    _replace_sector_cards(conn, market, as_of_date, updated_at, payload.get("sector_cards", []))
    _replace_issue_alerts(conn, market, as_of_date, updated_at, payload.get("alerts", []))
    _replace_stock_ideas(conn, market, as_of_date, updated_at, payload.get("ideas", []))
    _replace_calendar_events(conn, market, as_of_date, updated_at, payload.get("events", []))
    conn.commit()


def latest_payload(conn: sqlite3.Connection, market: str) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT MAX(as_of_date) AS as_of_date
        FROM market_metrics
        WHERE market = ?
        """,
        (market,),
    ).fetchone()
    if not row or not row["as_of_date"]:
        return None

    as_of_date = row["as_of_date"]
    metrics = [
        dict(item)
        for item in conn.execute(
            """
            SELECT group_name, sort_order, label, value, delta, tone, note
            FROM market_metrics
            WHERE market = ? AND as_of_date = ?
            ORDER BY sort_order
            """,
            (market, as_of_date),
        ).fetchall()
    ]
    sectors = [
        dict(item)
        for item in conn.execute(
            """
            SELECT sort_order, title, body, tone
            FROM sector_cards
            WHERE market = ? AND as_of_date = ?
            ORDER BY sort_order
            """,
            (market, as_of_date),
        ).fetchall()
    ]
    alerts = [
        dict(item)
        for item in conn.execute(
            """
            SELECT sort_order, severity, title, body
            FROM issue_alerts
            WHERE market = ? AND as_of_date = ?
            ORDER BY sort_order
            """,
            (market, as_of_date),
        ).fetchall()
    ]
    ideas = []
    for item in conn.execute(
        """
        SELECT rank, title, category, rating, big_picture, inflection,
               beneficiary_json, risk, rise_etf
        FROM stock_ideas
        WHERE market = ? AND as_of_date = ?
        ORDER BY rank
        """,
        (market, as_of_date),
    ).fetchall():
        idea = dict(item)
        idea["beneficiaries"] = json.loads(idea.pop("beneficiary_json"))
        ideas.append(idea)

    events = [
        dict(item)
        for item in conn.execute(
            """
            SELECT event_date, sort_order, region, label, body
            FROM calendar_events
            WHERE market = ? AND as_of_date = ?
            ORDER BY event_date, sort_order
            """,
            (market, as_of_date),
        ).fetchall()
    ]

    updated_row = conn.execute(
        """
        SELECT MAX(updated_at) AS updated_at
        FROM market_metrics
        WHERE market = ? AND as_of_date = ?
        """,
        (market, as_of_date),
    ).fetchone()
    return {
        "market": market,
        "as_of_date": as_of_date,
        "updated_at": updated_row["updated_at"] if updated_row else now_kst(),
        "metrics": metrics,
        "sector_cards": sectors,
        "alerts": alerts,
        "ideas": ideas,
        "events": events,
    }


def _replace_metrics(
    conn: sqlite3.Connection,
    market: str,
    as_of_date: str,
    updated_at: str,
    rows: list[dict[str, Any]],
) -> None:
    conn.execute(
        "DELETE FROM market_metrics WHERE market = ? AND as_of_date = ?",
        (market, as_of_date),
    )
    conn.executemany(
        """
        INSERT INTO market_metrics (
            market, as_of_date, group_name, sort_order, label, value,
            delta, tone, note, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                market,
                as_of_date,
                row.get("group_name", "main"),
                index,
                row["label"],
                row["value"],
                row.get("delta"),
                row.get("tone", "neutral"),
                row.get("note"),
                updated_at,
            )
            for index, row in enumerate(rows, start=1)
        ],
    )


def _replace_sector_cards(
    conn: sqlite3.Connection,
    market: str,
    as_of_date: str,
    updated_at: str,
    rows: list[dict[str, Any]],
) -> None:
    conn.execute(
        "DELETE FROM sector_cards WHERE market = ? AND as_of_date = ?",
        (market, as_of_date),
    )
    conn.executemany(
        """
        INSERT INTO sector_cards (
            market, as_of_date, sort_order, title, body, tone, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                market,
                as_of_date,
                index,
                row["title"],
                row["body"],
                row.get("tone", "neutral"),
                updated_at,
            )
            for index, row in enumerate(rows, start=1)
        ],
    )


def _replace_issue_alerts(
    conn: sqlite3.Connection,
    market: str,
    as_of_date: str,
    updated_at: str,
    rows: list[dict[str, Any]],
) -> None:
    conn.execute(
        "DELETE FROM issue_alerts WHERE market = ? AND as_of_date = ?",
        (market, as_of_date),
    )
    conn.executemany(
        """
        INSERT INTO issue_alerts (
            market, as_of_date, sort_order, severity, title, body, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                market,
                as_of_date,
                index,
                row.get("severity", "normal"),
                row["title"],
                row["body"],
                updated_at,
            )
            for index, row in enumerate(rows, start=1)
        ],
    )


def _replace_stock_ideas(
    conn: sqlite3.Connection,
    market: str,
    as_of_date: str,
    updated_at: str,
    rows: list[dict[str, Any]],
) -> None:
    conn.execute(
        "DELETE FROM stock_ideas WHERE market = ? AND as_of_date = ?",
        (market, as_of_date),
    )
    conn.executemany(
        """
        INSERT INTO stock_ideas (
            market, as_of_date, rank, title, category, rating, big_picture,
            inflection, beneficiary_json, risk, rise_etf, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                market,
                as_of_date,
                row.get("rank", index),
                row["title"],
                row["category"],
                int(row.get("rating", 4)),
                row["big_picture"],
                row["inflection"],
                json.dumps(row.get("beneficiaries", []), ensure_ascii=False),
                row.get("risk", ""),
                row.get("rise_etf", ""),
                updated_at,
            )
            for index, row in enumerate(rows, start=1)
        ],
    )


def _replace_calendar_events(
    conn: sqlite3.Connection,
    market: str,
    as_of_date: str,
    updated_at: str,
    rows: list[dict[str, Any]],
) -> None:
    conn.execute(
        "DELETE FROM calendar_events WHERE market = ? AND as_of_date = ?",
        (market, as_of_date),
    )
    conn.executemany(
        """
        INSERT INTO calendar_events (
            market, as_of_date, event_date, sort_order, region, label, body, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                market,
                as_of_date,
                row["event_date"],
                index,
                row["region"],
                row["label"],
                row["body"],
                updated_at,
            )
            for index, row in enumerate(rows, start=1)
        ],
    )
