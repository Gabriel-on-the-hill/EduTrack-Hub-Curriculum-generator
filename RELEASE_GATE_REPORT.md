# Release Gate Report

## Thresholds

| Gate | Latency threshold | Error-rate threshold | Additional gate invariant |
|---|---:|---:|---|
| Contract tests (schema/envelope consistency) | ≤ 5.0s wall time | 0% failed tests | All schema and envelope contract assertions must pass. |
| Auth tests (valid/invalid/replay/stale headers) | ≤ 5.0s wall time | 0% failed tests | Signed admin requests must accept valid headers and reject invalid, replayed, and stale requests. |
| Job lifecycle tests (queued → terminal paths) | ≤ 5.0s wall time | 0% failed tests | Jobs must transition through `running` into `success`, `pending_manual_review`, or `failed`. |
| Staging E2E (Hub submit → poll → save) | ≤ 10.0s wall time | 0% failed tests | The Hub flow must submit a job, poll terminal status, and save a successful result. |
| Canary rollout (10% → 50% → 100%) with rollback toggle | ≤ 5.0s wall time | 0% failed tests | Promotion only advances when p95 latency stays ≤ 750ms and error rate stays ≤ 1%; rollback must reset traffic to 0%. |

## Ordered Gate Execution

1. Contract gate command: `pytest tests/unit/test_schemas.py -q`
2. Auth gate command: `pytest tests/unit/test_admin_auth.py -q`
3. Job lifecycle gate command: `pytest tests/ingestion/test_job_lifecycle.py -q`
4. Staging E2E gate command: `pytest tests/integration/test_hub_submit_poll_save.py -q`
5. Canary gate command: `pytest tests/unit/test_canary_rollout.py -q`

## Result

- Release gate runner: **PASS**
- Promotion decision: **Advance through all five gates**

The ordered gate sequence now exists as a runnable script in `scripts/run_release_gates.py`, and the repo includes focused test coverage for auth headers, job lifecycle transitions, Hub submit/poll/save flow, and canary promotion/rollback behavior.
