"""Administración de inmuebles (X14): inventories, repairs, and owner / tenant requests."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import (
    CanalSolicitud,
    CategoriaReparacion,
    EstadoAmbiente,
    EstadoInventario,
    EstadoReparacion,
    EstadoSolicitud,
    PagaReparacion,
    Prioridad,
    Solicitante,
    TipoInventario,
    TipoSolicitud,
)
from app.models.inmuebles import Inmueble
from app.models.user import User


class Inventario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Move-in (entrega) or move-out (recepción) inventory, done room by room by an asesor."""

    __tablename__ = "inventarios"

    numero: Mapped[int] = mapped_column(Identity(start=19), unique=True)
    inmueble_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inmuebles.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[TipoInventario] = mapped_column(pg_enum(TipoInventario, "tipo_inventario"))
    fecha: Mapped[date] = mapped_column(Date, index=True)
    referencia: Mapped[str] = mapped_column(String(300))  # contract or deal, and the client
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    estado: Mapped[EstadoInventario] = mapped_column(
        pg_enum(EstadoInventario, "estado_inventario"),
        default=EstadoInventario.PROGRAMADO,
        server_default="programado",
        index=True,
    )
    firmado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    inmueble: Mapped[Inmueble] = relationship(lazy="joined")
    responsable: Mapped[User | None] = relationship(foreign_keys=[responsable_id], lazy="joined")
    ambientes: Mapped[list["InventarioAmbiente"]] = relationship(
        back_populates="inventario",
        order_by="InventarioAmbiente.orden",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    eventos: Mapped[list["AdminEvento"]] = relationship(
        primaryjoin="Inventario.id == AdminEvento.inventario_id",
        order_by="AdminEvento.created_at",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def code(self) -> str:
        return f"INV-{self.numero:03d}"


class InventarioAmbiente(UUIDPrimaryKeyMixin, Base):
    """One room / item of the inventory checklist."""

    __tablename__ = "inventario_ambientes"

    inventario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventarios.id", ondelete="CASCADE"), index=True
    )
    orden: Mapped[int] = mapped_column(SmallInteger)
    nombre: Mapped[str] = mapped_column(String(120))
    estado: Mapped[EstadoAmbiente | None] = mapped_column(
        pg_enum(EstadoAmbiente, "estado_ambiente")
    )  # None = not checked yet
    observacion: Mapped[str | None] = mapped_column(String(500))
    fotos: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")  # placeholder

    inventario: Mapped[Inventario] = relationship(back_populates="ambientes")


class Reparacion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Maintenance or repair: recibida → cotizada → aprobada → en ejecución → terminada."""

    __tablename__ = "reparaciones"

    numero: Mapped[int] = mapped_column(Identity(start=29), unique=True)
    inmueble_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inmuebles.id", ondelete="RESTRICT"), index=True
    )
    titulo: Mapped[str] = mapped_column(String(500))  # what needs fixing
    categoria: Mapped[CategoriaReparacion] = mapped_column(
        pg_enum(CategoriaReparacion, "categoria_reparacion")
    )
    prioridad: Mapped[Prioridad] = mapped_column(
        pg_enum(Prioridad, "prioridad_admin"), default=Prioridad.NORMAL, server_default="normal"
    )
    solicitante: Mapped[str] = mapped_column(String(200))  # «Inquilino · Cliente 12», «INV-019»
    fecha: Mapped[date] = mapped_column(Date, index=True)  # reported
    estado: Mapped[EstadoReparacion] = mapped_column(
        pg_enum(EstadoReparacion, "estado_reparacion"),
        default=EstadoReparacion.RECIBIDA,
        server_default="recibida",
        index=True,
    )
    proveedor: Mapped[str | None] = mapped_column(String(200))
    valor: Mapped[int | None] = mapped_column(BigInteger)  # COP, the quote
    paga: Mapped[PagaReparacion] = mapped_column(
        pg_enum(PagaReparacion, "paga_reparacion"),
        default=PagaReparacion.POR_DEFINIR,
        server_default="por_definir",
    )
    fecha_fin: Mapped[date | None] = mapped_column(Date)
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )  # who follows it up inside the company
    inventario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventarios.id", ondelete="SET NULL"), unique=True
    )  # created from an inventory's findings
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    inmueble: Mapped[Inmueble] = relationship(lazy="joined")
    responsable: Mapped[User | None] = relationship(foreign_keys=[responsable_id], lazy="joined")
    inventario: Mapped[Inventario | None] = relationship(lazy="joined")
    eventos: Mapped[list["AdminEvento"]] = relationship(
        primaryjoin="Reparacion.id == AdminEvento.reparacion_id",
        order_by="AdminEvento.created_at",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def code(self) -> str:
        return f"MAN-{self.numero:03d}"


class Solicitud(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Petición, queja, reclamo or sugerencia from an owner or tenant (PQR)."""

    __tablename__ = "solicitudes"

    numero: Mapped[int] = mapped_column(Identity(start=12), unique=True)
    inmueble_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inmuebles.id", ondelete="RESTRICT"), index=True
    )
    tipo: Mapped[TipoSolicitud] = mapped_column(pg_enum(TipoSolicitud, "tipo_solicitud"))
    de: Mapped[Solicitante] = mapped_column(pg_enum(Solicitante, "solicitante"))
    nombre: Mapped[str | None] = mapped_column(String(200))  # who made it
    canal: Mapped[CanalSolicitud] = mapped_column(pg_enum(CanalSolicitud, "canal_solicitud"))
    descripcion: Mapped[str] = mapped_column(String(1000))
    prioridad: Mapped[Prioridad] = mapped_column(
        pg_enum(Prioridad, "prioridad_admin", create_type=False),
        default=Prioridad.NORMAL,
        server_default="normal",
    )
    fecha: Mapped[date] = mapped_column(Date, index=True)  # received
    estado: Mapped[EstadoSolicitud] = mapped_column(
        pg_enum(EstadoSolicitud, "estado_solicitud"),
        default=EstadoSolicitud.ABIERTA,
        server_default="abierta",
        index=True,
    )
    responsable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    respuesta: Mapped[str | None] = mapped_column(Text)
    fecha_respuesta: Mapped[date | None] = mapped_column(Date)
    respondida_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    inmueble: Mapped[Inmueble] = relationship(lazy="joined")
    responsable: Mapped[User | None] = relationship(foreign_keys=[responsable_id], lazy="joined")
    eventos: Mapped[list["AdminEvento"]] = relationship(
        primaryjoin="Solicitud.id == AdminEvento.solicitud_id",
        order_by="AdminEvento.created_at",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    @property
    def code(self) -> str:
        return f"PQR-{self.numero:03d}"


class AdminEvento(UUIDPrimaryKeyMixin, Base):
    """History line of an inventory, repair or request (exactly one of them)."""

    __tablename__ = "admin_eventos"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(inventario_id, reparacion_id, solicitud_id) = 1", name="un_registro"
        ),
    )

    inventario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inventarios.id", ondelete="CASCADE"), index=True
    )
    reparacion_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reparaciones.id", ondelete="CASCADE"), index=True
    )
    solicitud_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("solicitudes.id", ondelete="CASCADE"), index=True
    )
    titulo: Mapped[str] = mapped_column(String(300))
    detalle: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
