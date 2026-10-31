import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import (
    EstadoCaptacion,
    ModoCaptacion,
    MotivoRechazoCaptacion,
    TipoEventoCaptacion,
    TipoInmueble,
    TipoNegocio,
)
from app.models.user import User


class Captacion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "captaciones"
    __table_args__ = (
        # «Inmueble ya registrado»: a property code can be in only one live captación.
        # Rejected ones don't block (the code may have been wrong).
        Index(
            "uq_captaciones_codigo_vigente",
            "codigo_inmueble",
            unique=True,
            postgresql_where=text("estado <> 'rechazada'"),
        ),
        Index("ix_captaciones_estado_asesor", "estado", "asesor_id"),
    )

    numero: Mapped[int] = mapped_column(Identity(start=201), unique=True)

    # Registro rápido
    negocio: Mapped[TipoNegocio] = mapped_column(
        pg_enum(TipoNegocio, "tipo_negocio", create_type=False)
    )
    codigo_inmueble: Mapped[str] = mapped_column(String(40), index=True)  # «INM-0360»
    direccion: Mapped[str] = mapped_column(String(300))
    modo: Mapped[ModoCaptacion] = mapped_column(pg_enum(ModoCaptacion, "modo_captacion"))

    # Formulario completo
    tipo_inmueble: Mapped[TipoInmueble | None] = mapped_column(
        pg_enum(TipoInmueble, "tipo_inmueble")
    )
    barrio: Mapped[str | None] = mapped_column(String(120))
    municipio: Mapped[str | None] = mapped_column(String(120))
    precio: Mapped[int | None] = mapped_column(BigInteger)  # COP: venta o canon mensual
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    habitaciones: Mapped[int | None] = mapped_column(SmallInteger)
    banos: Mapped[int | None] = mapped_column(SmallInteger)
    parqueadero: Mapped[bool | None]
    propietario_nombre: Mapped[str | None] = mapped_column(String(200))
    propietario_telefono: Mapped[str | None] = mapped_column(String(40))
    observaciones: Mapped[str | None] = mapped_column(Text)

    # Verificación
    estado: Mapped[EstadoCaptacion] = mapped_column(
        pg_enum(EstadoCaptacion, "estado_captacion"),
        default=EstadoCaptacion.POR_VERIFICAR,
        server_default="por_verificar",
    )
    enviada_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    reenvios: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    motivo_rechazo: Mapped[MotivoRechazoCaptacion | None] = mapped_column(
        pg_enum(MotivoRechazoCaptacion, "motivo_rechazo_captacion")
    )
    observacion_rechazo: Mapped[str | None] = mapped_column(Text)
    verificado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    verificado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    publicada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Ubicación del asesor al enviar (solo quien tiene Captación; GPS del navegador)
    gps_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    gps_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    gps_precision_m: Mapped[int | None]
    gps_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    asesor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    asesor: Mapped[User] = relationship(foreign_keys=[asesor_id], lazy="joined")
    verificado_por: Mapped[User | None] = relationship(
        foreign_keys=[verificado_por_id], lazy="joined"
    )
    eventos: Mapped[list["CaptacionEvento"]] = relationship(
        back_populates="captacion",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CaptacionEvento.created_at",
    )

    @property
    def code(self) -> str:
        return f"CAP-{self.numero:04d}"

    @property
    def verificado_por_name(self) -> str | None:
        return self.verificado_por.full_name if self.verificado_por else None


class CaptacionEvento(UUIDPrimaryKeyMixin, Base):
    """Trazabilidad: each submission, correction, approval, rejection, publication."""

    __tablename__ = "captacion_eventos"

    captacion_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("captaciones.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoEventoCaptacion] = mapped_column(
        pg_enum(TipoEventoCaptacion, "tipo_evento_captacion")
    )
    titulo: Mapped[str] = mapped_column(String(200))
    detalle: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    captacion: Mapped[Captacion] = relationship(back_populates="eventos")
    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")

    @property
    def created_by_name(self) -> str | None:
        return self.created_by.full_name if self.created_by else None
