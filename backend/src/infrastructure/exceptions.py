"""
Backward-compatible re-export facade.

Definitions live in ``src.shared.exceptions`` (source of truth).
This module re-exports everything so existing ``from src.infrastructure.exceptions``
imports continue to work without changes. The star import re-exports exactly
``src.shared.exceptions.__all__``, so the export list has one home, not two copies.
"""

from src.shared.exceptions import *
