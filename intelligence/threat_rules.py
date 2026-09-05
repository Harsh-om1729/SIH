import logging
import os
import sqlite3

log = logging.getLogger("ibvap.intelligence")

DEFAULT_SECTOR_RISK = {"red": 30.0, "yellow": 15.0, "green": 5.0, "none": 0.0}
DEFAULT_TIME_RISK = {  # hour (0-23) -> risk, 0-25 scale
    **{h: 25.0 for h in range(0, 5)},  # 00:00-04:59, deep night
    **{h: 20.0 for h in (5, 22, 23)},  # dawn/dusk transition
    **{h: 5.0 for h in range(6, 22)},  # daytime
}
DEFAULT_CLASS_CONFIDENCE = {"person": 15.0, "vehicle": 10.0, "animal": 3.0}
DEFAULT_MOVEMENT_CONFIG = {
    "slow_speed_px_per_frame": 2.0,
    "fast_speed_px_per_frame": 15.0,
    "max_movement_risk": 30.0,
}


class ThreatRulesDB:
    """Local, offline rules store (SQLite) feeding the Phase 10 threat-score
    formula: T = S_sector + T_time + K_kinematics + C_class (0-100). No
    network dependency — rules are seeded with sensible defaults on first
    run and, from then on, left untouched by seeding so they can be hand-
    edited (or swapped in via the encrypted-USB update mechanism the roadmap
    describes for air-gapped deployments) without ever touching code.
    """

    def __init__(self, db_path: str = "database/threat_rules.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
        self._seed_defaults()

    def _create_tables(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sector_risk (
                zone_tier TEXT PRIMARY KEY,
                risk REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS time_risk (
                hour INTEGER PRIMARY KEY,
                risk REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS class_confidence (
                category TEXT PRIMARY KEY,
                risk REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS movement_risk_config (
                key TEXT PRIMARY KEY,
                value REAL NOT NULL
            );
            """
        )
        self._conn.commit()

    def _seed_defaults(self) -> None:
        self._seed_table("sector_risk", "zone_tier", "risk", DEFAULT_SECTOR_RISK)
        self._seed_table("time_risk", "hour", "risk", DEFAULT_TIME_RISK)
        self._seed_table("class_confidence", "category", "risk", DEFAULT_CLASS_CONFIDENCE)
        self._seed_table("movement_risk_config", "key", "value", DEFAULT_MOVEMENT_CONFIG)

    def _seed_table(self, table: str, key_col: str, value_col: str, defaults: dict) -> None:
        cur = self._conn.execute(f"SELECT COUNT(*) FROM {table}")
        if cur.fetchone()[0] > 0:
            return  # already seeded (or hand-edited) — never overwrite
        self._conn.executemany(
            f"INSERT INTO {table} ({key_col}, {value_col}) VALUES (?, ?)",
            list(defaults.items()),
        )
        self._conn.commit()
        log.info("Seeded default rules into %s (%d rows)", table, len(defaults))

    def get_sector_risk(self, zone_tier: str) -> float:
        return self._lookup("sector_risk", "zone_tier", "risk", zone_tier, default=0.0)

    def get_time_risk(self, hour: int) -> float:
        return self._lookup("time_risk", "hour", "risk", hour, default=5.0)

    def get_class_confidence(self, category: str) -> float:
        return self._lookup("class_confidence", "category", "risk", category, default=0.0)

    def get_movement_config(self) -> dict:
        cur = self._conn.execute("SELECT key, value FROM movement_risk_config")
        return dict(cur.fetchall())

    def _lookup(self, table: str, key_col: str, value_col: str, key, default: float) -> float:
        cur = self._conn.execute(f"SELECT {value_col} FROM {table} WHERE {key_col} = ?", (key,))
        row = cur.fetchone()
        return row[0] if row is not None else default

    def close(self) -> None:
        self._conn.close()
