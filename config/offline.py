"""Offline configuration for third-party libraries, applied before import.

Ultralytics evaluates `ONLINE = is_online()` at import of `ultralytics.utils`,
and `is_online()` opens a TCP connection to public DNS (1.1.1.1:80, then
8.8.8.8:80, 2s timeout each) unless the `YOLO_OFFLINE` environment variable
says otherwise. IBVAP is specified to run air-gapped, so that probe is both
useless and a startup stall of up to ~4s on a host with no route out.

`YOLO_OFFLINE` is the library's own offline switch and `ONLINE` is a
module-level constant, so the variable has to be set *before* anything imports
ultralytics. That is why this module is imported and called explicitly at the
top of the two modules that import ultralytics, ahead of the import itself,
rather than being left to import-order luck.

Verified against ultralytics 8.3.40, `utils/__init__.py:626`:

    assert str(os.getenv("YOLO_OFFLINE", "")).lower() != "true"

The comparison is against the literal string "true", so "1" or "yes" do NOT
disable the probe. Hence the exact value written here, and the test that pins
it - a plausible-looking "1" would silently restore the outbound connection.

`ONLINE` gates only telemetry (Google Analytics events, Sentry), the PyPI
version check, and pip auto-install. Nothing on the inference path reads it,
so this cannot change detection results.
"""

import logging
import os
import sys

log = logging.getLogger("ibvap.offline")

ULTRALYTICS_OFFLINE_ENV = "YOLO_OFFLINE"
# Must be exactly this string (case-insensitively) - see module docstring.
ULTRALYTICS_OFFLINE_VALUE = "True"


def configure_ultralytics_offline() -> str:
    """Disables the ultralytics connectivity probe. Returns the value in force.

    Uses `setdefault`, so an operator who deliberately exports
    `YOLO_OFFLINE=false` still wins; silently overriding an explicit choice
    would be exactly the kind of hidden behaviour this codebase avoids.

    Warns if this call is what first sets the variable *and* ultralytics has
    already been imported, because at that point the setting can no longer
    take effect. That makes an import-order regression visible instead of
    quietly restoring the network probe.

    Being called again after ultralytics is imported is normal and silent:
    every module that imports ultralytics calls this before doing so, so the
    second and later calls necessarily run once it is in `sys.modules`. The
    value was already in force by then, so there is nothing to warn about.
    """
    already_imported = "ultralytics.utils" in sys.modules
    already_set = ULTRALYTICS_OFFLINE_ENV in os.environ
    value = os.environ.setdefault(ULTRALYTICS_OFFLINE_ENV, ULTRALYTICS_OFFLINE_VALUE)

    if already_imported and not already_set:
        log.warning(
            "%s set to %r after ultralytics was already imported - its ONLINE "
            "constant is already fixed and the connectivity probe has run. "
            "Import order regression: configure_ultralytics_offline() must run "
            "before any ultralytics import.",
            ULTRALYTICS_OFFLINE_ENV, value,
        )
    elif value.lower() != "true":
        log.warning(
            "%s=%r was set in the environment, so the ultralytics connectivity "
            "probe to public DNS remains ENABLED. Unset it to restore "
            "air-gapped behaviour.",
            ULTRALYTICS_OFFLINE_ENV, value,
        )
    return value
