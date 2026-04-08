#!/usr/bin/env python3
"""
Run release gates in order with explicit latency and error-rate thresholds.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Gate:
    name: str
    command: list[str]
    max_latency_seconds: float
    max_error_rate: float


GATES = [
    Gate(
        name="Contract tests (schema/envelope consistency)",
        command=["pytest", "tests/unit/test_schemas.py", "-q"],
        max_latency_seconds=5.0,
        max_error_rate=0.0,
    ),
    Gate(
        name="Auth tests (valid/invalid/replay/stale headers)",
        command=["pytest", "tests/unit/test_admin_auth.py", "-q"],
        max_latency_seconds=5.0,
        max_error_rate=0.0,
    ),
    Gate(
        name="Job lifecycle tests (queued -> terminal paths)",
        command=["pytest", "tests/ingestion/test_job_lifecycle.py", "-q"],
        max_latency_seconds=5.0,
        max_error_rate=0.0,
    ),
    Gate(
        name="Staging E2E (Hub submit -> poll -> save)",
        command=["pytest", "tests/integration/test_hub_submit_poll_save.py", "-q"],
        max_latency_seconds=10.0,
        max_error_rate=0.0,
    ),
    Gate(
        name="Canary rollout (10% -> 50% -> 100%) with rollback toggle",
        command=["pytest", "tests/unit/test_canary_rollout.py", "-q"],
        max_latency_seconds=5.0,
        max_error_rate=0.0,
    ),
]


def main() -> int:
    print("Release gate thresholds:")
    for gate in GATES:
        print(
            f"- {gate.name}: latency <= {gate.max_latency_seconds:.1f}s, "
            f"error rate <= {gate.max_error_rate:.1%}"
        )

    for index, gate in enumerate(GATES, start=1):
        print(f"\n[{index}/{len(GATES)}] {gate.name}")
        started = time.perf_counter()
        result = subprocess.run(gate.command, check=False)
        elapsed = time.perf_counter() - started
        error_rate = 0.0 if result.returncode == 0 else 1.0

        print(
            f"Gate result: returncode={result.returncode}, "
            f"latency={elapsed:.2f}s, error_rate={error_rate:.1%}"
        )

        if result.returncode != 0:
            print("Halting promotion: gate command failed.")
            return result.returncode
        if elapsed > gate.max_latency_seconds:
            print("Halting promotion: gate latency threshold exceeded.")
            return 1
        if error_rate > gate.max_error_rate:
            print("Halting promotion: gate error-rate threshold exceeded.")
            return 1

    print("\nAll release gates passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
