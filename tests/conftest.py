"""Shared test bootstrap configuration."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "asyncio: mark test as async")


def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
    test_fn = pyfuncitem.obj
    if asyncio.iscoroutinefunction(test_fn):
        kwargs = {
            name: pyfuncitem.funcargs[name]
            for name in pyfuncitem._fixtureinfo.argnames
            if name in pyfuncitem.funcargs
        }
        asyncio.run(test_fn(**kwargs))
        return True
    return None
