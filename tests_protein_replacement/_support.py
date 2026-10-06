"""Shared synthetic fixtures. Everything here is fabricated; nothing touches real data or network."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
TMP = HERE / "_tmp"
TMP.mkdir(exist_ok=True)
# All temporary files and caches stay inside the owned test directory.
tempfile.tempdir = str(TMP)
for k, sub in (("TMPDIR", ""), ("MPLCONFIGDIR", "mpl"), ("NUMBA_CACHE_DIR", "numba"), ("XDG_CACHE_HOME", "xdg")):
    os.environ.setdefault(k, str(TMP / sub) if sub else str(TMP))
sys.dont_write_bytecode = True

spec = importlib.util.spec_from_file_location("build_cite_totalvi", REPO / "companion/scripts/build_cite_totalvi.py")
B = importlib.util.module_from_spec(spec)
sys.modules["build_cite_totalvi"] = B
spec.loader.exec_module(B)

HDF5 = b"\x89HDF\r\n\x1a\n"


def synthetic_bytes(n: int, seed: int = 0) -> bytes:
    body = hashlib.sha256(str(seed).encode()).digest() * (n // 32 + 1)
    return (HDF5 + body)[:n]


def have(*mods) -> bool:
    try:
        for m in mods:
            __import__(m)
        return True
    except Exception:
        return False


def load_protein_check():
    p = REPO / "companion/scripts/protein_check.py"
    s = importlib.util.spec_from_file_location("protein_check_frozen_t", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


class FakeResponse:
    def __init__(self, body: bytes, status=200, ctype="application/octet-stream", clen=True):
        self.body, self.status, self.pos = body, status, 0
        self.headers = {"Content-Type": ctype}
        if clen:
            self.headers["Content-Length"] = str(len(body))

    def getcode(self):
        return self.status

    def read(self, n=-1):
        b = self.body[self.pos:self.pos + (n if n > 0 else len(self.body))]
        self.pos += len(b)
        return b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class Opener:
    """Records every request; returns queued responses or raises queued exceptions."""

    def __init__(self, items):
        self.items, self.calls = list(items), []

    def __call__(self, req, timeout=None):
        self.calls.append(req.full_url)
        it = self.items.pop(0)
        if isinstance(it, BaseException):
            raise it
        return it
