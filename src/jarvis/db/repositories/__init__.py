"""Repositories: one storage class per table, built on AsyncSession + the ORM models.

Repos contain only data-access (queries/mutations) — no embedding or business logic.
Services own a session factory and wrap repo calls in ``async with sessionmaker()``.
"""
