"""
Watch Tower Core Package

This package contains the core application components including business logic
management, bootstrap functionality, and events loop.
"""

from .business_logic_manager import BUSINESS_LOGIC_MANAGER as business_logic_manager
from .bootstrap import bootstrap

__all__ = [
    "business_logic_manager",
    "bootstrap",
]
