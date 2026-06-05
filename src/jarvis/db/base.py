"""SQLAlchemy declarative base + shared column helpers.

ORM models are the query layer; Alembic migrations remain the source of truth for
the schema (these models are not auto-created). Keep column definitions in sync
with ``db/migrations/versions``.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase

# Embedding dimensionality — must match the VECTOR(768) column in 001_baseline.
EMBED_DIM = 768


class Base(DeclarativeBase):
    pass
