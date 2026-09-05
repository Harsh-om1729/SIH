"""Offline unit tests for the encrypted USB-transfer bundle — no camera or
network required.
Run from ibvap/: python -m unittest tests.test_transfer
"""

import tempfile
import unittest
from pathlib import Path

from database.transfer import export_bundle, import_bundle


class TestTransferBundle(unittest.TestCase):
    def test_export_then_import_round_trips_file_contents(self):
        src_dir = Path(tempfile.mkdtemp())
        rules_path = src_dir / "threat_rules.db"
        rules_path.write_bytes(b"fake sqlite rules content")
        watchlist_path = src_dir / "watchlist.db"
        watchlist_path.write_bytes(b"fake sqlite watchlist content")

        transfer_dir = Path(tempfile.mkdtemp())
        bundle_path = str(transfer_dir / "bundle.enc")
        key_path = str(transfer_dir / "transfer.key")

        export_bundle([str(rules_path), str(watchlist_path)], bundle_path, key_path=key_path)

        output_dir = Path(tempfile.mkdtemp())
        extracted = import_bundle(bundle_path, str(output_dir), key_path=key_path)

        self.assertEqual(len(extracted), 2)
        self.assertEqual((output_dir / "threat_rules.db").read_bytes(), b"fake sqlite rules content")
        self.assertEqual((output_dir / "watchlist.db").read_bytes(), b"fake sqlite watchlist content")

    def test_bundle_file_is_encrypted_not_a_plain_zip(self):
        src_dir = Path(tempfile.mkdtemp())
        rules_path = src_dir / "threat_rules.db"
        rules_path.write_bytes(b"some content")

        transfer_dir = Path(tempfile.mkdtemp())
        bundle_path = str(transfer_dir / "bundle.enc")
        export_bundle([str(rules_path)], bundle_path, key_path=str(transfer_dir / "transfer.key"))

        raw = Path(bundle_path).read_bytes()
        self.assertNotEqual(raw[:2], b"PK")  # ZIP files start with "PK"

    def test_wrong_key_fails_to_decrypt(self):
        src_dir = Path(tempfile.mkdtemp())
        rules_path = src_dir / "threat_rules.db"
        rules_path.write_bytes(b"some content")

        transfer_dir = Path(tempfile.mkdtemp())
        bundle_path = str(transfer_dir / "bundle.enc")
        export_bundle([str(rules_path)], bundle_path, key_path=str(transfer_dir / "key_a.key"))

        output_dir = Path(tempfile.mkdtemp())
        with self.assertRaises(Exception):
            import_bundle(bundle_path, str(output_dir), key_path=str(transfer_dir / "key_b.key"))

    def test_key_persists_across_separate_export_calls(self):
        transfer_dir = Path(tempfile.mkdtemp())
        key_path = str(transfer_dir / "transfer.key")

        src_dir = Path(tempfile.mkdtemp())
        file_a = src_dir / "a.db"
        file_a.write_bytes(b"a")
        file_b = src_dir / "b.db"
        file_b.write_bytes(b"b")

        bundle_a = str(transfer_dir / "a.enc")
        bundle_b = str(transfer_dir / "b.enc")
        export_bundle([str(file_a)], bundle_a, key_path=key_path)
        export_bundle([str(file_b)], bundle_b, key_path=key_path)

        # Both bundles must be readable with the same (reused, not regenerated) key.
        output_dir = Path(tempfile.mkdtemp())
        import_bundle(bundle_a, str(output_dir / "out_a"), key_path=key_path)
        import_bundle(bundle_b, str(output_dir / "out_b"), key_path=key_path)

        self.assertEqual((output_dir / "out_a" / "a.db").read_bytes(), b"a")
        self.assertEqual((output_dir / "out_b" / "b.db").read_bytes(), b"b")


if __name__ == "__main__":
    unittest.main()
