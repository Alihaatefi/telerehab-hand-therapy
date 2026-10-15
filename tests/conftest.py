"""Shared test setup.

Qt must run without a display, and must be told where to find fonts, before it
is imported anywhere - so this is set at the very top, ahead of every import.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", r"C:\Windows\Fonts")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mock_server"))

import pytest
from server import Store, build_server


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def live_backend(tmp_path):
    """The bundled mock backend on a throwaway port, with an isolated store.

    Yields ``(base_url, store)`` so a test can both talk to it over HTTP and
    inspect what actually reached it.
    """
    store = Store(tmp_path / "store.json")
    server = build_server("127.0.0.1", free_port(), store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", store
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
