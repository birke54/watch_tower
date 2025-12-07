"""
Performance monitoring utilities for Watch Tower.

This module provides decorators and utilities for monitoring performance
across the application.
"""

import time
import functools
from typing import Any, Callable, Dict, Optional
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime

from utils.logging_config import get_logger

LOGGER = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Container for performance metrics."""
    operation: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    success: bool = True
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """Performance monitoring utility."""

    def __init__(self):
        self.metrics: Dict[str, PerformanceMetrics] = {}

    def start_operation(self, operation: str, **metadata: Any) -> str:
        """
        Start monitoring an operation.

        Args:
            operation: Operation name
            **metadata: Additional metadata

        Returns:
            Operation ID
        """
        operation_id = f"{operation}_{int(time.time() * 1000)}"
        self.metrics[operation_id] = PerformanceMetrics(
            operation=operation,
            start_time=datetime.now(),
            metadata=metadata
        )
        return operation_id

    def end_operation(
            self,
            operation_id: str,
            success: bool = True,
            error: Optional[str] = None) -> None:
        """
        End monitoring an operation.

        Args:
            operation_id: Operation ID from start_operation
            success: Whether the operation succeeded
            error: Error message if failed
        """
        if operation_id in self.metrics:
            metric = self.metrics[operation_id]
            metric.end_time = datetime.now()
            metric.duration = (metric.end_time - metric.start_time).total_seconds()
            metric.success = success
            metric.error = error

            # Log performance metrics
            if success:
                LOGGER.info(
                    "Operation '%s' completed in %.3fs",
                    metric.operation,
                    metric.duration
                )
            else:
                LOGGER.error(
                    "Operation '%s' failed after %.3fs: %s",
                    metric.operation,
                    metric.duration,
                    error
                )

    def get_metrics(self, operation: Optional[str]
                    = None) -> Dict[str, PerformanceMetrics]:
        """
        Get performance metrics.

        Args:
            operation: Optional operation name filter

        Returns:
            Dictionary of metrics
        """
        if operation:
            return {k: v for k, v in self.metrics.items() if v.operation == operation}
        return self.metrics.copy()

    def get_average_duration(self, operation: str) -> Optional[float]:
        """
        Get average duration for an operation.

        Args:
            operation: Operation name

        Returns:
            Average duration in seconds, or None if no metrics
        """
        durations = [
            m.duration for m in self.metrics.values()
            if m.operation == operation and m.duration is not None
        ]
        return sum(durations) / len(durations) if durations else None


# Global performance monitor instance
PERFORMANCE_MONITOR = PerformanceMonitor()


def monitor_performance(operation: str):
    """
    Decorator to monitor function performance.

    Args:
        operation: Operation name for monitoring

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            operation_id = PERFORMANCE_MONITOR.start_operation(operation)
            try:
                result = func(*args, **kwargs)
                PERFORMANCE_MONITOR.end_operation(operation_id, success=True)
                return result
            except Exception as e:
                PERFORMANCE_MONITOR.end_operation(
                    operation_id, success=False, error=str(e))
                raise
        return wrapper
    return decorator


def monitor_async_performance(operation: str):
    """
    Decorator to monitor async function performance.

    Args:
        operation: Operation name for monitoring

    Returns:
        Decorated async function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            operation_id = PERFORMANCE_MONITOR.start_operation(operation)
            try:
                result = await func(*args, **kwargs)
                PERFORMANCE_MONITOR.end_operation(operation_id, success=True)
                return result
            except Exception as e:
                PERFORMANCE_MONITOR.end_operation(
                    operation_id, success=False, error=str(e))
                raise
        return wrapper
    return decorator


@contextmanager
def performance_context(operation: str, **metadata: Any):
    """
    Context manager for performance monitoring.

    Args:
        operation: Operation name
        **metadata: Additional metadata

    Yields:
        None
    """
    operation_id = PERFORMANCE_MONITOR.start_operation(operation, **metadata)
    try:
        yield
        PERFORMANCE_MONITOR.end_operation(operation_id, success=True)
    except Exception as e:
        PERFORMANCE_MONITOR.end_operation(operation_id, success=False, error=str(e))
        raise


def log_performance_summary() -> None:
    """Log a summary of performance metrics."""
    metrics = PERFORMANCE_MONITOR.get_metrics()
    if not metrics:
        LOGGER.info("No performance metrics available")
        return

    # Group by operation
    operation_stats: Dict[str, list] = {}
    for metric in metrics.values():
        if metric.operation not in operation_stats:
            operation_stats[metric.operation] = []
        operation_stats[metric.operation].append(metric)

    LOGGER.info("Performance Summary:")
    for operation, stats in operation_stats.items():
        durations = [s.duration for s in stats if s.duration is not None]
        if durations:
            avg_duration = sum(durations) / len(durations)
            min_duration = min(durations)
            max_duration = max(durations)
            success_count = sum(1 for s in stats if s.success)
            total_count = len(stats)

            LOGGER.info(
                "  %s: avg=%.3fs, min=%.3fs, max=%.3fs, success=%s/%s",
                operation,
                avg_duration,
                min_duration,
                max_duration,
                success_count,
                total_count
            )
