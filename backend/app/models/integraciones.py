"""Integraciones (G07): external platforms and services, their connection data and history.

There are no real connectors yet: an integration stores what Gerencia typed to connect it
(non-secret values as they are, secrets only as a masked hint, never the secret itself) and its
state. Lead sources are tied to the leads' `fuente`, so their results are real.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, SmallInteger, String, func, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import FuenteLead
from app.models.user import User


class Integracion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "integraciones"

    clave: Mapped[str] = mapped_column(String(40), unique=True)  # «facebook», «whatsapp», «n-3»…
    nombre: Mapped[str] = mapped_column(String(80))
    grupo: Mapped[str] = mapped_column(String(10))  # trad · red · otro
    fuente: Mapped[FuenteLead | None] = mapped_column(
        pg_enum(FuenteLead, "fuente_lead", create_type=False), unique=True
    )  # leads that came from here
    orden: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    # sin_conectar · por_confirmar (data saved, connection not confirmed) · conectado
    estado: Mapped[str] = mapped_column(
        String(15), default="sin_conectar", server_default="sin_conectar"
    )
    como: Mapped[str] = mapped_column(
        String(15), default="por_confirmar", server_default="por_confirmar"
    )
    costo_mensual: Mapped[int | None] = mapped_column(BigInteger)  # COP; portals use their plans
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    secretos: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )  # masked
    avisar_falla: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    conectado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prueba_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prueba_txt: Mapped[str | None] = mapped_column(String(300))
    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )


class IntegracionEvento(UUIDPrimaryKeyMixin, Base):
    """Every connection, test, disconnection and change (G07: «queda en el registro de cambios»)."""

    __tablename__ = "integracion_eventos"

    integracion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("integraciones.id", ondelete="CASCADE"), index=True
    )
    accion: Mapped[str] = mapped_column(String(200))
    antes: Mapped[str | None] = mapped_column(String(300))
    despues: Mapped[str | None] = mapped_column(String(300))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False, index=True
    )

    integracion: Mapped[Integracion] = relationship(lazy="joined")
    actor: Mapped[User | None] = relationship(lazy="joined")
