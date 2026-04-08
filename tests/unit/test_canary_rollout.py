from src.release.canary import CanaryController, GateObservation, GateThreshold


def _controller() -> CanaryController:
    threshold = GateThreshold(max_p95_latency_ms=750.0, max_error_rate=0.01)
    return CanaryController(
        threshold_10=threshold,
        threshold_50=threshold,
        threshold_100=threshold,
    )


def test_canary_rollout_advances_10_50_100():
    controller = _controller()

    assert controller.advance(10, GateObservation(p95_latency_ms=400.0, error_rate=0.0)) is True
    assert controller.advance(50, GateObservation(p95_latency_ms=500.0, error_rate=0.005)) is True
    assert controller.advance(100, GateObservation(p95_latency_ms=650.0, error_rate=0.009)) is True
    assert controller.traffic_percent == 100
    assert controller.rollback_enabled is False


def test_canary_rollout_enables_rollback_on_threshold_breach():
    controller = _controller()

    assert controller.advance(10, GateObservation(p95_latency_ms=400.0, error_rate=0.0)) is True
    assert controller.advance(50, GateObservation(p95_latency_ms=900.0, error_rate=0.0)) is False
    assert controller.rollback_enabled is True

    controller.rollback()
    assert controller.traffic_percent == 0
    assert controller.rollback_enabled is True
