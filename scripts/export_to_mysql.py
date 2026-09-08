#!/usr/bin/env python3
"""Export the SQLite databases to a MySQL-compatible .sql dump.

    python scripts/export_to_mysql.py [-o ibvap_mysql.sql]

Import the result with MySQL Workbench (Server > Data Import > Import from
Self-Contained File) or `mysql -u root -p < ibvap_mysql.sql`.

This is a one-way snapshot for inspection: the running app keeps writing to
SQLite, so re-run this to refresh. The watchlist is deliberately excluded —
it holds biometric face embeddings that should not be copied into a second
datastore without the DPDP handling procedures noted in the README.
"""

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_DIR = Path(__file__).resolve().parent.parent / "database"
SCHEMA = "ibvap"

# Hand-written DDL rather than a generic type mapping: SQLite is untyped
# enough that guessing VARCHAR widths from the data produces a worse schema
# than just declaring the real one.
TABLES = {
    "incidents": {
        "db": "incidents.db",
        "ddl": """CREATE TABLE incidents (
  id                INT AUTO_INCREMENT PRIMARY KEY,
  track_id          INT,
  person_id         INT,
  category          VARCHAR(32),
  zone_tier         VARCHAR(16),
  score             DOUBLE,
  tier              VARCHAR(16),
  timestamp         DOUBLE,
  occurred_at       DATETIME,
  snapshot_path     VARCHAR(255),
  crop_path         VARCHAR(255),
  burst_paths       TEXT,
  status            VARCHAR(16) NOT NULL DEFAULT 'open',
  acknowledged_by   VARCHAR(64),
  acknowledged_at   DOUBLE,
  resolved_by       VARCHAR(64),
  resolved_at       DOUBLE,
  resolution_reason VARCHAR(32),
  INDEX idx_tier (tier),
  INDEX idx_status (status),
  INDEX idx_occurred_at (occurred_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
        # occurred_at is derived below — SQLite stores only the raw epoch,
        # which is unreadable when browsing tables by hand.
        "derive": "occurred_at",
    },
    "sector_risk": {
        "db": "threat_rules.db",
        "ddl": """CREATE TABLE sector_risk (
  zone_tier VARCHAR(16) PRIMARY KEY,
  risk      DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
    },
    "time_risk": {
        "db": "threat_rules.db",
        "ddl": """CREATE TABLE time_risk (
  hour INT PRIMARY KEY,
  risk DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
    },
    "class_confidence": {
        "db": "threat_rules.db",
        "ddl": """CREATE TABLE class_confidence (
  category VARCHAR(32) PRIMARY KEY,
  risk     DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
    },
    "movement_risk_config": {
        "db": "threat_rules.db",
        "ddl": """CREATE TABLE movement_risk_config (
  `key`  VARCHAR(64) PRIMARY KEY,
  value  DOUBLE NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
    },
}

_ESCAPES = str.maketrans(
    {"\\": "\\\\", "'": "\\'", '"': '\\"', "\n": "\\n", "\r": "\\r", "\x00": "\\0", "\x1a": "\\Z"}
)


def literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return repr(value)
    return "'" + str(value).translate(_ESCAPES) + "'"


def export_table(name: str, spec: dict, out) -> int:
    conn = sqlite3.connect(f"file:{DB_DIR / spec['db']}?mode=ro", uri=True)
    try:
        cursor = conn.execute(f"SELECT * FROM {name}")
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
    finally:
        conn.close()

    derived = spec.get("derive")
    if derived:
        columns = columns + [derived]

    out.write(f"\n--\n-- {name} ({len(rows)} rows)\n--\n")
    out.write(f"DROP TABLE IF EXISTS `{name}`;\n{spec['ddl']}\n\n")
    if not rows:
        return 0

    quoted = ", ".join(f"`{c}`" for c in columns)
    out.write(f"INSERT INTO `{name}` ({quoted}) VALUES\n")
    values = []
    for row in rows:
        row = list(row)
        if derived:
            epoch = row[columns.index("timestamp")]
            stamp = (
                datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                if epoch
                else None
            )
            row.append(stamp)
        values.append("  (" + ", ".join(literal(v) for v in row) + ")")
    out.write(",\n".join(values) + ";\n")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", default="ibvap_mysql.sql", type=Path)
    args = parser.parse_args()

    with args.output.open("w", encoding="utf-8") as out:
        out.write(f"-- IBVAP SQLite -> MySQL export, generated {datetime.now():%Y-%m-%d %H:%M}\n")
        out.write("-- Snapshot for inspection only; the app continues writing to SQLite.\n\n")
        out.write("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\n\n")
        out.write(f"CREATE DATABASE IF NOT EXISTS `{SCHEMA}` ")
        out.write("DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n")
        out.write(f"USE `{SCHEMA}`;\n")

        total = 0
        for name, spec in TABLES.items():
            count = export_table(name, spec, out)
            print(f"  {name:22} {count:>5} rows")
            total += count

        out.write("\nSET FOREIGN_KEY_CHECKS=1;\n")

    print(f"\nWrote {total} rows to {args.output} (schema `{SCHEMA}`)")


if __name__ == "__main__":
    main()
