"""Decrypts and installs a bundle created by export_for_usb_transfer.py.
Run from ibvap/: python scripts/import_from_usb_transfer.py <bundle_path>
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.transfer import import_bundle


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_from_usb_transfer.py <bundle_path>")
        sys.exit(1)

    bundle_path = sys.argv[1]
    extracted = import_bundle(bundle_path, output_dir="database")
    print(f"Imported {len(extracted)} file(s): {extracted}")


if __name__ == "__main__":
    main()
