"""Inmuebles: the company's property catalog. Approved captaciones feed it."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.captaciones import Captacion
from app.models.enums import EstadoInmueble, TipoInmueble, TipoNegocio
from app.models.user import User


class Inmueble(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inmuebles"

    codigo: Mapped[str] = mapped_column(
        String(40), unique=True
    )  # «INM-0360», same as the captación
    negocio: Mapped[TipoNegocio] = mapped_column(
        pg_enum(TipoNegocio, "tipo_negocio", create_type=False), index=True
    )
    tipo_inmueble: Mapped[TipoInmueble | None] = mapped_column(
        pg_enum(TipoInmueble, "tipo_inmueble", create_type=False)
    )
    direccion: Mapped[str] = mapped_column(String(300))
    zona: Mapped[str | None] = mapped_column(String(60), index=True)  # same list as pedidos
    barrio: Mapped[str | None] = mapped_column(String(120))
    municipio: Mapped[str | None] = mapped_column(String(120))
    precio: Mapped[int | None] = mapped_column(BigInteger)  # COP: sale price or monthly rent
    administracion: Mapped[int | None] = mapped_column(BigInteger)  # monthly building fee
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    habitaciones: Mapped[int | None] = mapped_column(SmallInteger)
    banos: Mapped[int | None] = mapped_column(SmallInteger)
    parqueadero: Mapped[bool | None]
    estrato: Mapped[int | None] = mapped_column(SmallInteger)
    descripcion: Mapped[str | None] = mapped_column(Text)
    propietario_nombre: Mapped[str | None] = mapped_column(String(200))
    propietario_telefono: Mapped[str | None] = mapped_column(String(40))

    estado: Mapped[EstadoInmueble] = mapped_column(
        pg_enum(EstadoInmueble, "estado_inmueble"), default=EstadoInmueble.DISPONIBLE, index=True
    )
    estado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    captacion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("captaciones.id", ondelete="SET NULL"), unique=True
    )
    captador_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    captacion: Mapped[Captacion | None] = relationship(lazy="joined")
    captador: Mapped[User | None] = relationship(foreign_keys=[captador_id], lazy="joined")
    eventos: Mapped[list["InmuebleEvento"]] = relationship(
        back_populates="inmueble",
        order_by="InmuebleEvento.created_at",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class InmuebleEvento(UUIDPrimaryKeyMixin, Base):
    """History: created, edited (before / after), status changes, sent as an option."""

    __tablename__ = "inmueble_eventos"

    inmueble_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inmuebles.id", ondelete="CASCADE"), index=True
    )
    titulo: Mapped[str] = mapped_column(String(200))
    detalle: Mapped[str | None] = mapped_column(Text)
    datos: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    inmueble: Mapped[Inmueble] = relationship(back_populates="eventos")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
