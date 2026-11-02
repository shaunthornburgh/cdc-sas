"""Rutas (G-083, M04, X08, G-051): field routes Coordinación assigns to asesores with Captación.

A route covers a period (one day to a range), the weekdays it applies and 1 to 3 zones, each
with its hours and its own weekdays. The asesor accepts or rejects it (reason + explanation). Each
day, on «Mi ruta», the asesor marks arrival at each zone; Gerencia rates the routes 1 to 5.
"""

import uuid
from datetime import date, datetime, time

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class Ruta(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "rutas"

    asesor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    desde: Mapped[date] = mapped_column(Date, index=True)
    hasta: Mapped[date] = mapped_column(Date, index=True)
    dias: Mapped[list[int]] = mapped_column(JSONB)  # 1 = lunes … 6 = sábado
    observacion: Mapped[str | None] = mapped_column(String(300))
    origen: Mapped[str] = mapped_column(String(10), default="manual")  # manual · excel
    # por_aceptar · aceptada · rechazada · cancelada
    estado: Mapped[str] = mapped_column(String(15), default="por_aceptar", index=True)
    motivo: Mapped[str | None] = mapped_column(String(60))
    motivo_texto: Mapped[str | None] = mapped_column(String(500))
    respondida_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reemplaza_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("rutas.id", ondelete="SET NULL")
    )
    creado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # G-051: Gerencia rates the routes Coordinación creates
    calificacion: Mapped[int | None] = mapped_column(SmallInteger)
    calificada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calificada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    asesor: Mapped[User] = relationship(foreign_keys=[asesor_id], lazy="joined")
    creado_por: Mapped[User | None] = relationship(foreign_keys=[creado_por_id], lazy="joined")
    zonas: Mapped[list["RutaZona"]] = relationship(
        back_populates="ruta",
        order_by="RutaZona.orden",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class RutaZona(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ruta_zonas"

    ruta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rutas.id", ondelete="CASCADE"), index=True
    )
    orden: Mapped[int] = mapped_column(SmallInteger)
    zona: Mapped[str] = mapped_column(String(60))
    hora_inicio: Mapped[time] = mapped_column(Time)
    hora_fin: Mapped[time] = mapped_column(Time)
    dias: Mapped[list[int]] = mapped_column(JSONB)

    ruta: Mapped[Ruta] = relationship(back_populates="zonas")


class RutaLlegada(UUIDPrimaryKeyMixin, Base):
    """M04 «Marcar llegada»: the asesor got to a zone of the route that day."""

    __tablename__ = "ruta_llegadas"
    __table_args__ = (UniqueConstraint("zona_id", "fecha"),)

    zona_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ruta_zonas.id", ondelete="CASCADE"), index=True
    )
    fecha: Mapped[date] = mapped_column(Date)
    llegada_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    nota: Mapped[str | None] = mapped_column(String(300))


class RutaEvento(UUIDPrimaryKeyMixin, Base):
    """Every assignment, answer, cancellation and rating («registro de cambios»)."""

    __tablename__ = "ruta_eventos"

    ruta_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("rutas.id", ondelete="CASCADE"), index=True
    )
    accion: Mapped[str] = mapped_column(String(200))
    antes: Mapped[str | None] = mapped_column(String(300))
    despues: Mapped[str | None] = mapped_column(String(500))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False, index=True
    )

    ruta: Mapped[Ruta] = relationship(lazy="joined")
    actor: Mapped[User | None] = relationship(lazy="joined")
