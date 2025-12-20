"""
Helper functions for working with Prometheus metrics.
"""

from typing import Dict

from utils.metrics import MetricDataPointName

def inc_counter_metric(
        metric_name: MetricDataPointName,
        increment: int = 1,
        labels: Dict[str, str] = None
    ) -> None:
    """Increments a counter metric by a specified value.
    Args:
        metric_name (MetricDataPointName): The name of the metric to increment.
        labels (Dict[str, str]): A dictionary of labels associated with the metric.
        increment (int, optional): The value to increment the counter by. Defaults to 1
    """
    if labels:
        metric_name.value.labels(**labels).inc(increment)
    else:
        metric_name.value.inc(increment)


def add_histogram_metric(
        metric_name: MetricDataPointName,
        value: float,
        labels: Dict[str, str] = None
    ) -> None:
    """Adds a value to a histogram metric.
    Args:
        metric_name (MetricDataPointName): The name of the histogram metric.
        labels (Dict[str, str]): A dictionary of labels associated with the metric.
        value (float): The value to add to the histogram.
    """
    if labels:
        metric_name.value.labels(**labels).observe(value)
    else:
        metric_name.value.observe(value)

def set_gauge_metric(metric_name: MetricDataPointName, value: float, labels: Dict[str, str] = None) -> None:
    """Sets the value of a gauge metric.
    Args:
        metric_name (MetricDataPointName): The name of the gauge metric.
        labels (Dict[str, str]): A dictionary of labels associated with the metric.
        value (float): The value to set the gauge to.
    """
    if labels:
        metric_name.value.labels(**labels).set(value)
    else:
        metric_name.value.set(value)
