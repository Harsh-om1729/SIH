import io
import logging
import os
import zipfile

from cryptography.fernet import Fernet

log = logging.getLogger("ibvap.transfer")


def _load_or_create_key(key_path: str) -> bytes:
    os.makedirs(os.path.dirname(key_path) or ".", exist_ok=True)
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()
    key = Fernet.generate_key()
    with open(key_path, "wb") as f:
        f.write(key)
    log.info("Generated new transfer encryption key at %s", key_path)
    return key


def export_bundle(file_paths: list, output_path: str, key_path: str = "database/transfer.key") -> str:
    """Bundles the given files into a single Fernet-encrypted archive, for
    physical transfer (e.g. via USB) to an air-gapped deployment — the
    roadmap's "encrypted USB transfer" mechanism for threat-rule/watchlist
    updates, with no network path involved at any point.
    """
    fernet = Fernet(_load_or_create_key(key_path))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in file_paths:
            if os.path.exists(path):
                zf.write(path, arcname=os.path.basename(path))

    encrypted = fernet.encrypt(buffer.getvalue())
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(encrypted)
    log.info("Exported %d file(s) to encrypted bundle: %s", len(file_paths), output_path)
    return output_path


def import_bundle(bundle_path: str, output_dir: str, key_path: str = "database/transfer.key") -> list:
    """Decrypts and unpacks a bundle created by export_bundle(), writing
    files into output_dir. Requires the same key used to export — if the key
    file isn't present, that's the point: only a device that already has (or
    is separately handed) the key can read a transferred bundle.
    """
    fernet = Fernet(_load_or_create_key(key_path))
    with open(bundle_path, "rb") as f:
        encrypted = f.read()
    decrypted = fernet.decrypt(encrypted)

    os.makedirs(output_dir, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(decrypted)) as zf:
        zf.extractall(output_dir)
        extracted = [os.path.join(output_dir, name) for name in zf.namelist()]
    log.info("Imported %d file(s) from %s into %s", len(extracted), bundle_path, output_dir)
    return extracted
