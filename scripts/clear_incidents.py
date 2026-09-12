"""Clear recorded incidents and their evidence files — a pre-demo reset.

    python scripts/clear_incidents.py            # dry run: report only
    python scripts/clear_incidents.py --yes      # actually delete

Removes every row from incidents.db and the encrypted evidence each row
points at, then VACUUMs so the database actually gives the disk space back.
Orphaned files in the evidence directory (written by a run whose rows were
already cleared, or by the unencrypted fallback path) are removed too.

Deliberately all-or-nothing and gated behind --yes: this destroys evidence,
which in a real deployment is exactly what a retention policy governs. It
exists for clearing accumulated *test* data before a demo.
"""
import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DB_PATH = "database/incidents.db"
EVIDENCE_DIR = "snapshots"


def referenced_paths(conn) -> set:
    paths = set()
    for snap, crop, burst in conn.execute(
        "SELECT snapshot_path, crop_path, burst_paths FROM incidents"
    ):
        for p in (snap, crop):
            if p:
                paths.add(p)
        if burst:
            try:
                paths.update(p for p in json.loads(burst) if p)
            except (ValueError, TypeError):
                # A malformed burst_paths cell shouldn't strand the whole reset;
                # the file sweep below still catches those files as orphans.
                pass
    return paths


def human(n_bytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n_bytes < 1024 or unit == "GB":
            return f"{n_bytes:.1f} {unit}"
        n_bytes /= 1024


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes", action="store_true", help="perform the deletion")
    ap.add_argument("--db", default=DB_PATH)
    ap.add_argument("--evidence-dir", default=EVIDENCE_DIR)
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"No incident database at {args.db} — nothing to clear.")
        return

    conn = sqlite3.connect(args.db)
    rows = conn.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]
    by_tier = dict(conn.execute("SELECT tier, COUNT(*) FROM incidents GROUP BY tier"))
    refs = referenced_paths(conn)

    on_disk = set()
    if os.path.isdir(args.evidence_dir):
        for name in os.listdir(args.evidence_dir):
            full = os.path.join(args.evidence_dir, name)
            if os.path.isfile(full):
                on_disk.add(full)

    # Row paths may be stored relative or absolute; match on basename so a
    # path recorded from a different working directory still lines up.
    ref_names = {os.path.basename(p) for p in refs}
    orphans = {p for p in on_disk if os.path.basename(p) not in ref_names}

    total_bytes = sum(os.path.getsize(p) for p in on_disk)
    print(f"incidents.db : {rows} rows {by_tier or ''}")
    print(f"evidence     : {len(on_disk)} files, {human(total_bytes)} "
          f"({len(orphans)} not referenced by any row)")

    if not args.yes:
        print("\nDry run. Re-run with --yes to delete all of the above.")
        conn.close()
        return

    removed = failed = 0
    for path in on_disk:
        try:
            os.remove(path)
            removed += 1
        except OSError as e:
            failed += 1
            print(f"  could not remove {path}: {e}")

    conn.execute("DELETE FROM incidents")
    conn.commit()
    conn.execute("VACUUM")  # reclaim the pages, not just mark them free
    conn.close()

    print(f"\nDeleted {rows} rows and {removed} evidence files"
          + (f" ({failed} could not be removed)" if failed else "") + ".")
    print(f"database/incidents.db is now {human(os.path.getsize(args.db))}.")


if __name__ == "__main__":
    main()
