"""
Watch Tower Core Package

This package contains the core application components including business logic
management, bootstrap functionality, events loop, and management API.
"""

from .business_logic_manager import BUSINESS_LOGIC_MANAGER as business_logic_manager
from .bootstrap import bootstrap
from .management_api import create_management_app

__all__ = [
    "business_logic_manager",
    "bootstrap",
    "create_management_app",
]
