"""
Watch Tower CLI Package

This package provides a command-line interface for managing the Watch Tower
video surveillance system, including business logic management, system status
monitoring, and visitor log management.
"""

from .main import cli

__version__ = "3.0.0"
__all__ = ["cli"]
