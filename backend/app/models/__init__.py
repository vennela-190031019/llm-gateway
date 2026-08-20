"""ORM models.

All models are imported here so a single `import app.models` registers
the full schema on `Base.metadata` — required for Alembic autogenerate.
"""

from __future__ import annotations

from app.models.llm_model import LLMModel
from app.models.provider import Provider
from app.models.user import User, UserRole

__all__ = ["LLMModel", "Provider", "User", "UserRole"]
