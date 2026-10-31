"""Novedades del personal (K13 «Ausencias y permisos»): incapacidades and permisos."""

import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Identity, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import EstadoNovedad, TipoNovedad
from app.models.user import User


class Novedad(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An absence or permit of one employee, from `desde` to `hasta` (both included)."""

    __tablename__ = "novedades"
    __table_args__ = (CheckConstraint("hasta >= desde", name="fechas"),)

    numero: Mapped[int] = mapped_column(Identity(start=1), unique=True)
    empleado_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoNovedad] = mapped_column(pg_enum(TipoNovedad, "tipo_novedad"))
    desde: Mapped[date] = mapped_column(Date, index=True)
    hasta: Mapped[date] = mapped_column(Date, index=True)
    observacion: Mapped[str | None] = mapped_column(String(500))
    soportes: Mapped[int] = mapped_column(
        SmallInteger, default=0, server_default="0"
    )  # placeholder
    estado: Mapped[EstadoNovedad] = mapped_column(
        pg_enum(EstadoNovedad, "estado_novedad"),
        default=EstadoNovedad.REGISTRADA,
        server_default="registrada",
        index=True,
    )
    registrada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    anulada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    anulada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    motivo_anulacion: Mapped[str | None] = mapped_column(String(300))

    empleado: Mapped[User] = relationship(foreign_keys=[empleado_id], lazy="joined")
    registrada_por: Mapped[User | None] = relationship(
        foreign_keys=[registrada_por_id], lazy="joined"
    )
    anulada_por: Mapped[User | None] = relationship(foreign_keys=[anulada_por_id], lazy="joined")

    @property
    def code(self) -> str:
        return f"NOV-{self.numero:03d}"

    @property
    def dias(self) -> int:
        return (self.hasta - self.desde).days + 1
