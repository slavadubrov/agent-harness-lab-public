"""SQLite customer-account database: schema, seed data, fresh copies, and diffs.

The environment has a fixed clock (TODAY) so that "days since delivery" is the same on
every run.
"""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

TODAY = date(2026, 3, 15)

SCHEMA = """
CREATE TABLE accounts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    status      TEXT NOT NULL CHECK (status IN ('active', 'suspended', 'closed')),
    created_at  TEXT NOT NULL
);
CREATE TABLE addresses (
    id          INTEGER PRIMARY KEY,
    account_id  TEXT NOT NULL REFERENCES accounts(id),
    kind        TEXT NOT NULL CHECK (kind IN ('shipping', 'billing')),
    line1       TEXT NOT NULL,
    city        TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    country     TEXT NOT NULL,
    UNIQUE (account_id, kind)
);
CREATE TABLE orders (
    id           TEXT PRIMARY KEY,
    account_id   TEXT NOT NULL REFERENCES accounts(id),
    status       TEXT NOT NULL CHECK (status IN ('pending', 'shipped', 'delivered', 'cancelled')),
    item         TEXT NOT NULL,
    total_cents  INTEGER NOT NULL,
    placed_at    TEXT NOT NULL,
    delivered_at TEXT
);
CREATE TABLE refunds (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     TEXT NOT NULL REFERENCES orders(id),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    reason       TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
CREATE TABLE preferences (
    account_id  TEXT NOT NULL REFERENCES accounts(id),
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    PRIMARY KEY (account_id, key)
);
"""


def _d(days_ago: int) -> str:
    return (TODAY - timedelta(days=days_ago)).isoformat()


ACCOUNTS = [
    ("A-100", "Ana Novak", "ana.novak@example.com", "active", "2023-04-02"),
    ("A-101", "Ben Ortiz", "ben.ortiz@example.com", "active", "2024-01-19"),
    ("A-102", "Chloe Park", "chloe.park@example.com", "suspended", "2022-11-30"),
    ("A-103", "Dmitri Sokolov", "dmitri.sokolov@example.com", "active", "2025-06-11"),
    ("A-104", "Eva Lindqvist", "eva.lindqvist@example.com", "active", "2021-08-08"),
]

ADDRESSES = [
    (1, "A-100", "shipping", "14 Harbour Road", "Gdansk", "80-001", "PL"),
    (2, "A-100", "billing", "14 Harbour Road", "Gdansk", "80-001", "PL"),
    (3, "A-101", "shipping", "221 Elm Street", "Austin", "73301", "US"),
    (4, "A-101", "billing", "PO Box 90", "Austin", "73301", "US"),
    (5, "A-102", "shipping", "3 Rue Cler", "Paris", "75007", "FR"),
    (6, "A-102", "billing", "3 Rue Cler", "Paris", "75007", "FR"),
    (7, "A-103", "shipping", "Karl-Marx-Allee 90", "Berlin", "10243", "DE"),
    (8, "A-103", "billing", "Karl-Marx-Allee 90", "Berlin", "10243", "DE"),
    (9, "A-104", "shipping", "Drottninggatan 5", "Stockholm", "111 51", "SE"),
    (10, "A-104", "billing", "Drottninggatan 5", "Stockholm", "111 51", "SE"),
]

# (id, account, status, item, total_cents, placed_days_ago, delivered_days_ago | None)
ORDERS = [
    ("O-1001", "A-100", "delivered", "Ceramic teapot", 4800, 6, 2),
    ("O-1002", "A-100", "delivered", "Kitchen knife set", 12900, 20, 12),
    ("O-1003", "A-100", "delivered", "Linen tablecloth", 6500, 60, 45),
    ("O-1004", "A-100", "shipped", "Espresso machine", 18900, 3, None),
    ("O-2001", "A-101", "delivered", "Road bike helmet", 8900, 15, 9),
    ("O-2002", "A-101", "delivered", "Carbon bike wheels", 35000, 10, 5),
    ("O-3001", "A-102", "delivered", "Desk lamp", 3900, 30, 25),
    ("O-4001", "A-103", "delivered", "Wool blanket", 7400, 14, 8),
    ("O-4002", "A-103", "cancelled", "Standing desk", 42000, 7, None),
    ("O-5001", "A-104", "delivered", "Noise-cancelling headphones", 19900, 12, 6),
]

# (order_id, amount_cents, reason, days_ago)
REFUNDS = [
    ("O-5001", 19900, "Defective left ear cup", 4),
]

PREFERENCES = [
    ("A-100", "marketing_emails", "on"),
    ("A-100", "sms_notifications", "off"),
    ("A-100", "language", "en"),
    ("A-100", "paperless_billing", "on"),
    ("A-101", "marketing_emails", "on"),
    ("A-101", "language", "en"),
    ("A-103", "marketing_emails", "on"),
    ("A-103", "sms_notifications", "on"),
    ("A-103", "language", "en"),
    ("A-104", "marketing_emails", "off"),
    ("A-104", "language", "sv"),
]


def create_seed(path: Path) -> Path:
    """Create the seed database at ``path`` (overwrites)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    con = sqlite3.connect(path)
    try:
        con.executescript(SCHEMA)
        con.executemany("INSERT INTO accounts VALUES (?,?,?,?,?)", ACCOUNTS)
        con.executemany("INSERT INTO addresses VALUES (?,?,?,?,?,?,?)", ADDRESSES)
        con.executemany(
            "INSERT INTO orders VALUES (?,?,?,?,?,?,?)",
            [
                (oid, acc, st, item, cents, _d(placed), _d(dlv) if dlv is not None else None)
                for oid, acc, st, item, cents, placed, dlv in ORDERS
            ],
        )
        con.executemany(
            "INSERT INTO refunds (order_id, amount_cents, reason, created_at) VALUES (?,?,?,?)",
            [(oid, cents, reason, _d(ago)) for oid, cents, reason, ago in REFUNDS],
        )
        con.executemany("INSERT INTO preferences VALUES (?,?,?)", PREFERENCES)
        con.commit()
    finally:
        con.close()
    return path


def fresh_copy(seed: Path, dest: Path, setup_sql: str | None = None) -> Path:
    """Copy the seed to ``dest`` and apply the task's optional setup SQL."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed, dest)
    if setup_sql:
        con = sqlite3.connect(dest)
        try:
            con.executescript(setup_sql)
            con.commit()
        finally:
            con.close()
    return dest


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


TABLE_KEYS = {
    "accounts": ("id",),
    "addresses": ("id",),
    "orders": ("id",),
    "refunds": ("id",),
    "preferences": ("account_id", "key"),
}


@dataclass(frozen=True)
class TableDiff:
    added: list[dict]
    removed: list[dict]
    changed: list[tuple[dict, dict]]  # (before, after)

    @property
    def empty(self) -> bool:
        return not (self.added or self.removed or self.changed)


def _rows(con: sqlite3.Connection, table: str) -> dict[tuple, dict]:
    keys = TABLE_KEYS[table]
    out = {}
    for row in con.execute(f"SELECT * FROM {table}"):
        d = dict(row)
        out[tuple(d[k] for k in keys)] = d
    return out


def diff(before: Path, after: Path) -> dict[str, TableDiff]:
    """Row-level diff of every table between two database files."""
    b, a = connect(before), connect(after)
    try:
        result = {}
        for table in TABLE_KEYS:
            rb, ra = _rows(b, table), _rows(a, table)
            result[table] = TableDiff(
                added=[ra[k] for k in ra.keys() - rb.keys()],
                removed=[rb[k] for k in rb.keys() - ra.keys()],
                changed=[(rb[k], ra[k]) for k in rb.keys() & ra.keys() if rb[k] != ra[k]],
            )
        return result
    finally:
        b.close()
        a.close()
