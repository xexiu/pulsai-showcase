"""SQLAlchemy declarative base for all ORM mappings.

Lives in ``infrastructure/persistence`` (per DDD_PATTERNS.md §"Infrastructure
Layer"). Each ORM model in ``infrastructure/persistence/*_model.py`` inherits
from :class:`Base` here.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
