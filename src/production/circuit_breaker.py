"""
Circuit Breaker (Phase 5 Operational Control)

Protects production from cascading failures and latency spikes.
Automatically disables Shadow Execution if thresholds are breached.
"""

import time
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

class CircuitBreaker:
    """
    Simple circuit breaker state machine.
    States: CLOSED (Normal), OPEN (Disabled), HALF-OPEN (Testing).
    """
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED" 
        
    def allow_request(self) -> bool:
        """Check if request allowed."""
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF-OPEN"
                return True
            return False
            
        return True
        
    def record_success(self):
        """Reset failures on success."""
        if self.state == "HALF-OPEN":
            self.state = "CLOSED"
        self.failures = 0
        
    def record_failure(self):
        """Record a failure or latency breach."""
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.failures >= self.failure_threshold:
            if self.state != "OPEN":
                logger.error("Circuit Breaker OPENED: Shadow Execution Disabled.")
                self.state = "OPEN"

    def protect(self, func: Callable, *args, **kwargs) -> Any:
        """Execute protected function."""
        if not self.allow_request():
            logger.warning("Circuit Open: Skipping execution.")
            return None
            
        try:
            start = time.time()
            result = func(*args, **kwargs)
            # Latency check could go here
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise e
