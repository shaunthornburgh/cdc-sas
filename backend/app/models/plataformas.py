"""Plataformas tradicionales (K15): plans, quota updates and their history."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    func,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import FuenteLead, TipoEventoPlataforma
from app.models.user import User


class Plataforma(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A traditional real-estate portal. Its leads are the ones with the same `fuente`."""

    __tablename__ = "plataformas"

    fuente: Mapped[FuenteLead] = mapped_column(
        pg_enum(FuenteLead, "fuente_lead", create_type=False), unique=True
    )
    nombre: Mapped[str] = mapped_column(String(80))
    color: Mapped[str] = mapped_column(String(7), default="#00843D", server_default="#00843D")
    orden: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    activa: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    responsable: Mapped[User | None] = relationship(lazy="joined")
    planes: Mapped[list["PlataformaPlan"]] = relationship(
        back_populates="plataforma",
        order_by="PlataformaPlan.activacion",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class PlataformaPlan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One paid period of a portal: price, dates, quota and featured listings."""

    __tablename__ = "plataforma_planes"
    __table_args__ = (
        CheckConstraint("vencimiento >= activacion", name="fechas"),
        CheckConstraint(
            "precio >= 0 AND cupo_total >= 0 AND destacados_total >= 0", name="valores"
        ),
    )

    plataforma_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plataformas.id", ondelete="CASCADE"), index=True
    )
    precio: Mapped[int] = mapped_column(BigInteger)  # COP for the whole period
    activacion: Mapped[date] = mapped_column(Date)
    vencimiento: Mapped[date] = mapped_column(Date)
    cupo_total: Mapped[int] = mapped_column(SmallInteger)
    destacados_total: Mapped[int] = mapped_column(SmallInteger)
    alarma_dias: Mapped[int] = mapped_column(SmallInteger, default=10, server_default="10")
    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    plataforma: Mapped[Plataforma] = relationship(back_populates="planes")

    @property
    def dias(self) -> int:
        return (self.vencimiento - self.activacion).days + 1


class PlataformaActualizacion(UUIDPrimaryKeyMixin, Base):
    """«Registrar actualización»: what the portal shows today, and who checked it."""

    __tablename__ = "plataforma_actualizaciones"
    __table_args__ = (
        CheckConstraint(
            "cupo_usado >= 0 AND cupo_usado <= cupo_total "
            "AND destacados_usados >= 0 AND destacados_usados <= destacados_total",
            name="cupos",
        ),
    )

    plataforma_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plataformas.id", ondelete="CASCADE"), index=True
    )
    realizada_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    actualizado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )  # who was assigned at that moment
    cupo_total: Mapped[int] = mapped_column(SmallInteger)
    cupo_usado: Mapped[int] = mapped_column(SmallInteger)  # «publicaciones activas»
    destacados_total: Mapped[int] = mapped_column(SmallInteger)
    destacados_usados: Mapped[int] = mapped_column(SmallInteger)
    observacion: Mapped[str | None] = mapped_column(String(300))
    dias_desde_anterior: Mapped[int | None] = mapped_column(SmallInteger)
    regla_dias: Mapped[int] = mapped_column(SmallInteger)  # rule in force when it was saved
    a_tiempo: Mapped[bool] = mapped_column(Boolean)

    plataforma: Mapped[Plataforma] = relationship(lazy="joined")
    actualizado_por: Mapped[User | None] = relationship(
        foreign_keys=[actualizado_por_id], lazy="joined"
    )
    responsable: Mapped[User | None] = relationship(foreign_keys=[responsable_id], lazy="joined")


class PlataformaEvento(UUIDPrimaryKeyMixin, Base):
    """Registro de cambios: responsable, plans, the update rule and downloads."""

    __tablename__ = "plataforma_eventos"

    plataforma_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plataformas.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoEventoPlataforma] = mapped_column(
        pg_enum(TipoEventoPlataforma, "tipo_evento_plataforma")
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    antes: Mapped[str | None] = mapped_column(String(200))
    despues: Mapped[str | None] = mapped_column(String(200))
    detalle: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    actor: Mapped[User | None] = relationship(lazy="joined")


class PlataformasConfig(Base):
    """Single row (id = 1): every how many days each portal must be updated."""

    __tablename__ = "plataformas_config"
    __table_args__ = (CheckConstraint("id = 1", name="una_fila"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=1)
    dias_regla: Mapped[int] = mapped_column(SmallInteger, default=7, server_default="7")
    confirmada: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    updated_by: Mapped[User | None] = relationship(lazy="joined")
