"""Shared local Fernet key handling (Phase 0B, item 3).

`IncidentStore` and the USB-transfer bundler each already load-or-create a
Fernet key this way. Watchlist embeddings need the same treatment, so the
pattern lives here rather than being written a third time — one mechanism,
not a new key system.

Keys are per-purpose files, not one shared secret: biometric watchlist data
and evidence images are separate scopes, so compromising or rotating one does
not expose the other. Same local-key tradeoff as the rest of this air-gapped
build — lose the key and the data it protects is unreadable.
"""

import logging
import os
import stat

from cryptography.fernet import Fernet

log = logging.getLogger("ibvap.keys")


def load_or_create_key(key_path: str, purpose: str = "data") -> bytes:
    """Returns the Fernet key at `key_path`, generating it on first use.

    The key material itself is never logged — only the path.
    """
    os.makedirs(os.path.dirname(key_path) or ".", exist_ok=True)
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            return f.read()

    key = Fernet.generate_key()
    # Create 0600 where the platform honours it, so the key is not world
    # readable in the window between creation and first use. Windows ignores
    # POSIX modes; NTFS ACLs govern there instead.
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    log.info("Generated new %s encryption key at %s", purpose, key_path)
    return key
