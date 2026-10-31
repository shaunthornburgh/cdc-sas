import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint, func, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import Cargo, MedioTransporte
from app.models.user import User


class Preoperacional(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One per person per day (Bogotá date). Carro / Moto: plate + 8 SÍ/NO answers."""

    __tablename__ = "preoperacionales"
    __table_args__ = (UniqueConstraint("user_id", "fecha", name="uq_preoperacionales_user_fecha"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date, index=True)
    realizado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    medio: Mapped[MedioTransporte] = mapped_column(pg_enum(MedioTransporte, "medio_transporte"))
    placa: Mapped[str | None] = mapped_column(String(10))
    # [{"pregunta": "...", "si": true}, …] — the question text is stored so history survives
    # changes to the list.
    respuestas: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    observaciones: Mapped[str | None] = mapped_column(Text)
    tiene_novedad: Mapped[bool] = mapped_column(default=False, server_default="false")
    revisado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    revisado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision_nota: Mapped[str | None] = mapped_column(Text)

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")
    revisado_por: Mapped[User | None] = relationship(foreign_keys=[revisado_por_id], lazy="joined")

    @property
    def respuestas_no(self) -> list[int]:
        """1-based numbers of the questions answered NO."""
        return [i + 1 for i, r in enumerate(self.respuestas or []) if not r.get("si")]

    @property
    def revisado_por_name(self) -> str | None:
        return self.revisado_por.full_name if self.revisado_por else None


class PreoperacionalConfig(Base):
    """Gerencia turns the preoperacional on or off per cargo (G-012)."""

    __tablename__ = "preoperacional_config"

    cargo: Mapped[Cargo] = mapped_column(
        pg_enum(Cargo, "cargo", create_type=False), primary_key=True
    )
    activo: Mapped[bool] = mapped_column(default=True, server_default=true())
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
