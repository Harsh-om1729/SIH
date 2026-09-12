"""Audit incidents.db and decrypt evidence snapshots on demand.

Usage from ibvap/:
  # 1. List recent incidents in terminal:
  python scripts/audit_evidence.py

  # 2. Decrypt and view evidence for a specific incident ID:
  python scripts/audit_evidence.py --incident 591

  # 3. Decrypt and view a specific .enc snapshot directly:
  python scripts/audit_evidence.py snapshots/red_person_1_20260905-172038_burst0.jpg.enc

  # 4. Decrypt all snapshots into a folder:
  python scripts/audit_evidence.py --export-all
"""

import argparse
import glob
import os
import subprocess
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.incident_store import IncidentStore


def list_incidents(store: IncidentStore, limit: int = 15) -> None:
    incidents = store.list_incidents(limit=limit)
    if not incidents:
        print("No incidents recorded in database/incidents.db yet.")
        return

    print(f"\n{'ID':<5} {'Timestamp':<10} {'Category':<10} {'Zone':<8} {'Score':<7} {'Tier':<8} {'Status':<14} {'Resolution / Operator'}")
    print("-" * 85)
    for inc in incidents:
        ts = datetime.fromtimestamp(inc["timestamp"]).strftime("%H:%M:%S")
        score = f"{inc['score']:.1f}"
        res = ""
        if inc.get("status") == "resolved":
            res = f"{inc.get('resolved_by')} ({inc.get('resolution_reason')})"
        elif inc.get("status") == "acknowledged":
            res = f"Ack: {inc.get('acknowledged_by')}"

        print(f"#{inc['id']:<4} {ts:<10} {inc['category']:<10} {inc['zone_tier']:<8} {score:<7} {inc['tier']:<8} {inc['status']:<14} {res}")
    print("\nTo decrypt and view evidence, run:")
    print("  python scripts/audit_evidence.py --incident <ID>")
    print("  python scripts/audit_evidence.py <path/to/image.jpg.enc>")
    print("  python scripts/audit_evidence.py --export-all\n")


def open_file_in_viewer(file_path: str) -> None:
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", file_path], check=False)
        elif sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", file_path], check=False)
        elif sys.platform == "win32":
            os.startfile(file_path)
    except Exception as e:
        print(f"Could not open image viewer: {e}")


def decrypt_file(store: IncidentStore, enc_path: str, output_path: str | None = None, auto_open: bool = True) -> str:
    if not os.path.exists(enc_path):
        print(f"Error: Encrypted file not found at: {enc_path}")
        sys.exit(1)

    decrypted_bytes = store.decrypt_image_bytes(enc_path)
    if not output_path:
        base_name = os.path.basename(enc_path).replace(".jpg.enc", ".jpg").replace(".enc", ".jpg")
        output_path = os.path.join(tempfile.gettempdir(), f"decrypted_{base_name}")

    with open(output_path, "wb") as f:
        f.write(decrypted_bytes)

    print(f"✅ Successfully decrypted: {enc_path}")
    print(f"📁 Decrypted image saved to: {output_path} ({len(decrypted_bytes)} bytes)")
    if auto_open:
        open_file_in_viewer(output_path)
    return output_path


def decrypt_incident(store: IncidentStore, incident_id: int) -> None:
    inc = store.get_incident(incident_id)
    if not inc:
        print(f"Error: Incident #{incident_id} not found in database.")
        return

    print(f"\n--- Incident #{inc['id']} Details ---")
    print(f"Timestamp: {datetime.fromtimestamp(inc['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Category:  {inc['category']} (Track {inc['track_id']}, Person {inc['person_id']})")
    print(f"Zone:      {inc['zone_tier']}")
    print(f"Score:     {inc['score']:.1f} ({inc['tier']})")
    print(f"Status:    {inc['status']}")
    if inc.get("acknowledged_by"):
        print(f"Ack by:    {inc['acknowledged_by']}")
    if inc.get("resolved_by"):
        print(f"Resolved:  {inc['resolved_by']} ({inc['resolution_reason']})")

    paths = []
    if inc.get("snapshot_path"):
        paths.append(("Full Snapshot", inc["snapshot_path"]))
    if inc.get("crop_path"):
        paths.append(("Crop", inc["crop_path"]))

    for label, path in paths:
        if path and os.path.exists(path):
            print(f"\nDecrypting {label} ({path})...")
            decrypt_file(store, path)
        elif path:
            print(f"Notice: {label} file not found on disk at {path}")


def export_all_snapshots(store: IncidentStore, output_dir: str = "decrypted_snapshots") -> None:
    os.makedirs(output_dir, exist_ok=True)
    enc_files = glob.glob("snapshots/*.enc")
    if not enc_files:
        print("No .enc files found in snapshots/.")
        return

    print(f"Decrypting {len(enc_files)} snapshots into '{output_dir}/'...")
    count = 0
    for enc_path in enc_files:
        filename = os.path.basename(enc_path).replace(".jpg.enc", ".jpg").replace(".enc", ".jpg")
        out_path = os.path.join(output_dir, filename)
        try:
            decrypted = store.decrypt_image_bytes(enc_path)
            with open(out_path, "wb") as f:
                f.write(decrypted)
            count += 1
        except Exception as e:
            print(f"Error decrypting {enc_path}: {e}")

    print(f"✅ Finished! Successfully decrypted {count} images to {output_dir}/.")
    open_file_in_viewer(output_dir)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit database/incidents.db and decrypt evidence.")
    parser.add_argument("file", nargs="?", help="Direct path to a .jpg.enc file to decrypt and view")
    parser.add_argument("--incident", "-i", type=int, help="Incident ID to inspect and decrypt")
    parser.add_argument("--limit", "-l", type=int, default=15, help="Number of incidents to list")
    parser.add_argument("--export-all", action="store_true", help="Decrypt all snapshots into decrypted_snapshots/ folder")
    args = parser.parse_args()

    store = IncidentStore()

    if args.export_all:
        export_all_snapshots(store)
    elif args.file:
        decrypt_file(store, args.file)
    elif args.incident:
        decrypt_incident(store, args.incident)
    else:
        list_incidents(store, limit=args.limit)


if __name__ == "__main__":
    main()
