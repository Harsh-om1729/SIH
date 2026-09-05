"""Bundles threat_rules.db + watchlist.db into a single encrypted file for
physical (USB) transfer to an air-gapped deployment, per the roadmap's
"encrypted USB transfer" update mechanism.
Run from ibvap/: python scripts/export_for_usb_transfer.py [output_path]
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.transfer import export_bundle


def main() -> None:
    output_path = sys.argv[1] if len(sys.argv) > 1 else "transfer_bundle.enc"
    files = ["database/threat_rules.db", "database/watchlist.db"]

    export_bundle(files, output_path)
    print(f"Bundle written to: {output_path}")
    print(
        "Copy this file to the target device via USB, along with "
        "database/transfer.key (kept separately/securely, never on the same drive)."
    )


if __name__ == "__main__":
    main()
