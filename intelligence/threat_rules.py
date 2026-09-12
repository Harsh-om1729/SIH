import logging
import os
import sqlite3

log = logging.getLogger("ibvap.intelligence")

# Bumped whenever the shipped defaults below change. On startup, rows that
# still hold the *previous* version's default are updated in place; rows that
# were hand-edited locally are left alone (see _migrate). This keeps the
# "seeded once, never clobbered" promise for operator tuning while still
# letting a calibration change reach existing air-gapped installs.
RULES_VERSION = 2

# --- v2: border-surveillance calibration -----------------------------------
# Budget, so a sentry can reason about the 0-100 total:
#   sector 25 + time 18 + kinematics 10 + class 12
#   + direction 18 + loiter 10 + group 7  = 100
DEFAULT_SECTOR_RISK = {"red": 25.0, "yellow": 12.0, "green": 4.0, "none": 0.0}
DEFAULT_TIME_RISK = {
    **{h: 18.0 for h in range(0, 5)},   # 00:00-04:59, deep night — classic crossing window
    **{h: 14.0 for h in (5, 22, 23)},   # dawn/dusk transition
    **{h: 4.0 for h in range(6, 22)},   # daytime
}
DEFAULT_CLASS_CONFIDENCE = {"person": 12.0, "vehicle": 8.0, "animal": 2.0}

# Kinematics is a U-curve, not "faster = worse". At a border BOTH extremes are
# suspicious: near-stationary means crawling, lying up, or watching the fence
# (how infiltration actually looks), and running means a dash across the line.
# An ordinary walking pace in between is the *least* interesting thing on the
# feed. The previous linear "fast = risk" rule scored a man lying still at the
# fence as zero risk, which is backwards for this deployment.
DEFAULT_MOVEMENT_CONFIG = {
    "still_speed_px_per_frame": 1.0,   # at or below: fully "stationary"
    "walk_min_px_per_frame": 2.0,      # start of the low-risk walking band
    "walk_max_px_per_frame": 8.0,      # end of the low-risk walking band
    "fast_speed_px_per_frame": 14.0,   # at or above: fully "running"
    "max_movement_risk": 10.0,
}

# Direction of travel relative to the border line. Both crossing directions
# score high: inward is infiltration, outward is exfiltration/smuggling.
# "parallel" (moving along the line, not across it) is mildly interesting —
# that is what reconnaissance along a fence looks like.
DEFAULT_DIRECTION_RISK = {
    "inward": 18.0,
    "outward": 16.0,
    "crossing": 18.0,  # in a red zone with no green zone to resolve the sign
    "parallel": 5.0,
    "none": 0.0,       # stationary, or no direction resolved yet
}

# Dwell time inside a non-"none" zone, keyed off the Re-ID person_id so it
# survives ByteTrack losing and re-acquiring the track. Standing at the fence
# is reconnaissance; it is invisible to a speed-based rule.
DEFAULT_LOITER_CONFIG = {
    "warn_seconds": 30.0,
    "warn_risk": 5.0,
    "alert_seconds": 120.0,
    "alert_risk": 10.0,
}

# Number of people simultaneously inside a zone. A group at the line is a
# materially different event from one person.
DEFAULT_GROUP_RISK = {1: 0.0, 2: 3.0, 3: 5.0, 5: 7.0}  # keyed by minimum count

# --- v1 defaults, kept only to recognise untouched rows during migration ----
V1_SECTOR_RISK = {"red": 30.0, "yellow": 15.0, "green": 5.0, "none": 0.0}
V1_TIME_RISK = {
    **{h: 25.0 for h in range(0, 5)},
    **{h: 20.0 for h in (5, 22, 23)},
    **{h: 5.0 for h in range(6, 22)},
}
V1_CLASS_CONFIDENCE = {"person": 15.0, "vehicle": 10.0, "animal": 3.0}
V1_MOVEMENT_CONFIG = {
    "slow_speed_px_per_frame": 2.0,
    "fast_speed_px_per_frame": 15.0,
    "max_movement_risk": 30.0,
}


class ThreatRulesDB:
    """Local, offline rules store (SQLite) feeding the border threat-score
    formula (0-100):

        T = S_sector + T_time + K_kinematics + C_class
            + D_direction + L_loiter + G_group

    No network dependency — rules are seeded with border-calibrated defaults
    on first run. Existing databases are migrated by RULES_VERSION, and any
    row an operator has hand-edited is preserved rather than overwritten, so
    local tuning survives an update arriving over the encrypted-USB channel.
    """

    def __init__(self, db_path: str = "database/threat_rules.db"):
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._create_tables()
        self._seed_defaults()
        self._migrate()

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
            CREATE TABLE IF NOT EXISTS direction_risk (
                direction TEXT PRIMARY KEY,
                risk REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS loiter_config (
                key TEXT PRIMARY KEY,
                value REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS group_risk (
                min_count INTEGER PRIMARY KEY,
                risk REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS rules_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def _seed_defaults(self) -> None:
        self._seed_table("sector_risk", "zone_tier", "risk", DEFAULT_SECTOR_RISK)
        self._seed_table("time_risk", "hour", "risk", DEFAULT_TIME_RISK)
        self._seed_table("class_confidence", "category", "risk", DEFAULT_CLASS_CONFIDENCE)
        self._seed_table("movement_risk_config", "key", "value", DEFAULT_MOVEMENT_CONFIG)
        self._seed_table("direction_risk", "direction", "risk", DEFAULT_DIRECTION_RISK)
        self._seed_table("loiter_config", "key", "value", DEFAULT_LOITER_CONFIG)
        self._seed_table("group_risk", "min_count", "risk", DEFAULT_GROUP_RISK)

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

    # -- migration ----------------------------------------------------------
    def _stored_version(self) -> int:
        cur = self._conn.execute("SELECT value FROM rules_meta WHERE key = 'version'")
        row = cur.fetchone()
        if row is not None:
            return int(row[0])
        # No version row: either a brand-new DB (tables just seeded with v2
        # values) or a v1 DB predating this column. Tell them apart by looking
        # at a value the two versions disagree on.
        cur = self._conn.execute("SELECT risk FROM sector_risk WHERE zone_tier = 'red'")
        row = cur.fetchone()
        return 1 if row is not None and abs(row[0] - V1_SECTOR_RISK["red"]) < 1e-9 else RULES_VERSION

    def _migrate(self) -> None:
        version = self._stored_version()
        if version >= RULES_VERSION:
            self._set_version(RULES_VERSION)
            return

        log.warning(
            "Migrating threat rules v%d -> v%d (border calibration). Rows still "
            "holding a v%d default are updated; hand-edited rows are kept.",
            version, RULES_VERSION, version,
        )
        updated = kept = 0
        for table, key_col, val_col, old, new in (
            ("sector_risk", "zone_tier", "risk", V1_SECTOR_RISK, DEFAULT_SECTOR_RISK),
            ("time_risk", "hour", "risk", V1_TIME_RISK, DEFAULT_TIME_RISK),
            ("class_confidence", "category", "risk", V1_CLASS_CONFIDENCE, DEFAULT_CLASS_CONFIDENCE),
        ):
            for key, old_value in old.items():
                cur = self._conn.execute(
                    f"SELECT {val_col} FROM {table} WHERE {key_col} = ?", (key,)
                )
                row = cur.fetchone()
                if row is None:
                    continue
                if abs(row[0] - old_value) < 1e-9:
                    self._conn.execute(
                        f"UPDATE {table} SET {val_col} = ? WHERE {key_col} = ?", (new[key], key)
                    )
                    updated += 1
                else:
                    kept += 1

        # The movement config changed shape entirely (linear slow/fast -> a
        # U-curve with new keys), so it can't be migrated key-by-key. Replace
        # it only if every old key still holds its v1 default.
        cur = self._conn.execute("SELECT key, value FROM movement_risk_config")
        existing = dict(cur.fetchall())
        untouched = all(
            k in existing and abs(existing[k] - v) < 1e-9 for k, v in V1_MOVEMENT_CONFIG.items()
        )
        if untouched:
            self._conn.execute("DELETE FROM movement_risk_config")
            self._conn.executemany(
                "INSERT INTO movement_risk_config (key, value) VALUES (?, ?)",
                list(DEFAULT_MOVEMENT_CONFIG.items()),
            )
            updated += len(DEFAULT_MOVEMENT_CONFIG)
        else:
            log.warning(
                "movement_risk_config was hand-edited under the old linear rule and "
                "cannot be auto-converted to the v%d U-curve; missing keys fall back "
                "to defaults. Review it: %s", RULES_VERSION, sorted(existing),
            )
            kept += len(existing)

        self._conn.commit()
        self._set_version(RULES_VERSION)
        log.warning("Threat rules migration complete: %d updated, %d kept as-is", updated, kept)

    def _set_version(self, version: int) -> None:
        self._conn.execute(
            "INSERT INTO rules_meta (key, value) VALUES ('version', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(version),),
        )
        self._conn.commit()

    # -- lookups ------------------------------------------------------------
    def get_sector_risk(self, zone_tier: str) -> float:
        return self._lookup("sector_risk", "zone_tier", "risk", zone_tier, default=0.0)

    def get_time_risk(self, hour: int) -> float:
        return self._lookup("time_risk", "hour", "risk", hour, default=4.0)

    def get_class_confidence(self, category: str) -> float:
        return self._lookup("class_confidence", "category", "risk", category, default=0.0)

    def get_direction_risk(self, direction: "str | None") -> float:
        return self._lookup(
            "direction_risk", "direction", "risk", direction or "none", default=0.0
        )

    def get_movement_config(self) -> dict:
        cur = self._conn.execute("SELECT key, value FROM movement_risk_config")
        stored = dict(cur.fetchall())
        # Fall back per-key: a DB hand-edited under the old linear rule won't
        # have the U-curve keys, and a KeyError here would take down scoring.
        return {**DEFAULT_MOVEMENT_CONFIG, **stored}

    def get_loiter_config(self) -> dict:
        cur = self._conn.execute("SELECT key, value FROM loiter_config")
        return {**DEFAULT_LOITER_CONFIG, **dict(cur.fetchall())}

    def get_group_risk(self, count: int) -> float:
        """Risk for `count` people seen together — the highest threshold at or
        below `count` wins, so the table stays sparse and easy to hand-edit."""
        cur = self._conn.execute(
            "SELECT risk FROM group_risk WHERE min_count <= ? ORDER BY min_count DESC LIMIT 1",
            (count,),
        )
        row = cur.fetchone()
        return row[0] if row is not None else 0.0

    def _lookup(self, table: str, key_col: str, value_col: str, key, default: float) -> float:
        cur = self._conn.execute(f"SELECT {value_col} FROM {table} WHERE {key_col} = ?", (key,))
        row = cur.fetchone()
        return row[0] if row is not None else default

    def close(self) -> None:
        self._conn.close()
