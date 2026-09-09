"""Ultralytics must not probe the network at import time.

`ultralytics.utils` evaluates `ONLINE = is_online()` when imported, which
opens a TCP connection to 1.1.1.1:80 then 8.8.8.8:80 (2s timeout each) unless
`YOLO_OFFLINE` is set. IBVAP runs air-gapped, so the probe is disabled through
the library's own switch before ultralytics is ever imported.
"""

import os
import subprocess
import sys

import pytest

from config.offline import (
    ULTRALYTICS_OFFLINE_ENV,
    ULTRALYTICS_OFFLINE_VALUE,
    configure_ultralytics_offline,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(code: str, env_overrides: dict) -> subprocess.CompletedProcess:
    """Runs code in a clean interpreter - import-time state cannot be undone
    inside a running process, so these must be separate processes."""
    env = dict(os.environ)
    env.pop(ULTRALYTICS_OFFLINE_ENV, None)
    env["PYTHONPATH"] = REPO_ROOT
    env["KMP_DUPLICATE_LIB_OK"] = "TRUE"
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, cwd=REPO_ROOT, env=env, timeout=300,
    )


# --------------------------------------------------------------------------
# The switch itself
# --------------------------------------------------------------------------

def test_sets_the_documented_env_var(monkeypatch):
    monkeypatch.delenv(ULTRALYTICS_OFFLINE_ENV, raising=False)
    assert configure_ultralytics_offline() == ULTRALYTICS_OFFLINE_VALUE
    assert os.environ[ULTRALYTICS_OFFLINE_ENV] == ULTRALYTICS_OFFLINE_VALUE


def test_value_matches_what_ultralytics_actually_checks():
    """ultralytics compares `.lower() != "true"`, so "1"/"yes" do NOT work.

    Pinning this stops the value drifting to something plausible-looking that
    silently restores the outbound probe.
    """
    assert ULTRALYTICS_OFFLINE_VALUE.lower() == "true"


def test_explicit_operator_override_is_respected(monkeypatch):
    monkeypatch.setenv(ULTRALYTICS_OFFLINE_ENV, "false")
    assert configure_ultralytics_offline() == "false"
    assert os.environ[ULTRALYTICS_OFFLINE_ENV] == "false"


def test_override_that_reenables_the_probe_is_logged(monkeypatch, caplog):
    monkeypatch.setenv(ULTRALYTICS_OFFLINE_ENV, "false")
    with caplog.at_level("WARNING", logger="ibvap.offline"):
        configure_ultralytics_offline()
    assert "remains ENABLED" in caplog.text


def test_repeat_calls_after_ultralytics_import_are_silent(monkeypatch, caplog):
    """Every module importing ultralytics calls this first, so later calls
    necessarily run once ultralytics is loaded. That is not a regression."""
    monkeypatch.delenv(ULTRALYTICS_OFFLINE_ENV, raising=False)
    # Another test in the suite may already have imported ultralytics, which
    # would make the first call below warn legitimately. Pin both sides of the
    # scenario so this test measures only the repeat call.
    monkeypatch.delitem(sys.modules, "ultralytics.utils", raising=False)
    configure_ultralytics_offline()

    monkeypatch.setitem(sys.modules, "ultralytics.utils", object())
    caplog.clear()  # caplog.text spans the whole test, not just the block below
    with caplog.at_level("WARNING", logger="ibvap.offline"):
        configure_ultralytics_offline()
    assert caplog.text == ""


def test_first_set_after_ultralytics_import_warns(monkeypatch, caplog):
    """The real regression - setting it too late - must be loud."""
    monkeypatch.delenv(ULTRALYTICS_OFFLINE_ENV, raising=False)
    monkeypatch.setitem(sys.modules, "ultralytics.utils", object())

    caplog.clear()
    with caplog.at_level("WARNING", logger="ibvap.offline"):
        configure_ultralytics_offline()
    assert "Import order regression" in caplog.text


# --------------------------------------------------------------------------
# The effect on ultralytics, in real interpreters
# --------------------------------------------------------------------------

@pytest.mark.parametrize("importer", ["detection.detector", "tracking.tracker"])
def test_importing_project_module_leaves_ultralytics_offline(importer):
    """Both modules that import ultralytics must disable the probe first."""
    result = _run(
        f"import {importer}\n"
        "from ultralytics.utils import ONLINE\n"
        "print('ONLINE=', ONLINE)\n",
        {},
    )
    assert result.returncode == 0, result.stderr
    assert "ONLINE= False" in result.stdout


# Records every outbound attempt and blocks it, so nothing leaves the host.
# `create_connection` must accept `address` as a KEYWORD - ultralytics calls
# `socket.create_connection(address=(dns, 80), timeout=2.0)`, and a
# positional-only guard raises TypeError, which is swallowed by is_online()'s
# bare `except Exception`. That failure mode makes a guard silently blind, so
# the signatures here are deliberate and the control test below proves the
# guard still sees a real probe.
_NETWORK_GUARD = """
import socket
attempts = []


def _blocked(kind, target):
    attempts.append((kind, target))
    raise OSError("blocked " + kind)


socket.socket.connect = lambda self, address, *a, **k: _blocked("connect", address)
socket.socket.connect_ex = lambda self, address, *a, **k: _blocked("connect_ex", address)
socket.create_connection = lambda address=None, *a, **k: _blocked("create_connection", address)

_real_gai = socket.getaddrinfo


def _gai(host=None, port=None, *a, **k):
    if host not in (None, "", "localhost", "127.0.0.1", "::1"):
        _blocked("getaddrinfo", (host, port))
    return _real_gai(host, port, *a, **k)


socket.getaddrinfo = _gai
"""


@pytest.mark.parametrize("importer", ["detection.detector", "tracking.tracker"])
def test_importing_project_module_makes_no_outbound_connection(importer):
    """Records any outbound socket use during import. Must be none."""
    result = _run(
        _NETWORK_GUARD + f"import {importer}\nprint('ATTEMPTS=', attempts)\n", {}
    )
    assert result.returncode == 0, result.stderr
    assert "ATTEMPTS= []" in result.stdout


def test_probe_still_fires_without_the_switch():
    """Control: proves the guard above is actually capable of seeing a probe.

    Imports ultralytics with YOLO_OFFLINE explicitly disabled, so the probe
    runs. The attempt is recorded and blocked - no packet leaves the host.
    Without this control, a blind guard would make the test above pass
    vacuously.
    """
    result = _run(
        _NETWORK_GUARD + "import ultralytics.utils\nprint('ATTEMPTS=', attempts)\n",
        {ULTRALYTICS_OFFLINE_ENV: "false"},
    )
    assert result.returncode == 0, result.stderr
    assert "('1.1.1.1', 80)" in result.stdout
