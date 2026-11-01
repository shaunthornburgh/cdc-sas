"""Configuración (Z02): settings Gerencia defines for the whole tool, one row per section."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.user import User


class ConfigSeccion(Base):
    """`valores` holds only what was changed; defaults live in app.services.configuracion."""

    __tablename__ = "configuracion"

    seccion: Mapped[str] = mapped_column(String(40), primary_key=True)
    valores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    updated_by: Mapped[User | None] = relationship(lazy="joined")


class ConfigEvento(UUIDPrimaryKeyMixin, Base):
    """Registro de cambios: who changed which section, when, and the values before and after."""

    __tablename__ = "configuracion_eventos"

    seccion: Mapped[str] = mapped_column(String(40), index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    antes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    despues: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    detalle: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    actor: Mapped[User | None] = relationship(lazy="joined")
