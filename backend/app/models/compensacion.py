"""Compensación: closed deals, commissions, bonuses, payments and salary periods (G05, X04, Z05)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import pg_enum
from app.models.enums import (
    EstadoCierre,
    EstadoCompensacion,
    EstadoPago,
    EstadoSalario,
    TipoBono,
    TipoComision,
    TipoNegocio,
    TipoPago,
)
from app.models.leads import Lead
from app.models.user import User


class CompensacionConfig(Base):
    """One row (id = 1) with the percentages, amounts and pay days Gerencia configures."""

    __tablename__ = "compensacion_config"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    valores: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class Cierre(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A closed deal for compensation: one per lead marked «Ganado» (NEG-0140…)."""

    __tablename__ = "cierres"

    numero: Mapped[int] = mapped_column(Identity(start=140), unique=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), unique=True
    )
    negocio: Mapped[TipoNegocio | None] = mapped_column(
        pg_enum(TipoNegocio, "tipo_negocio", create_type=False)
    )
    cerrado_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    cerrador_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    filtro_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    captador_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    # What the company actually keeps (after colleagues and referrals, without IVA), in COP.
    ganancia: Mapped[int | None] = mapped_column(BigInteger)
    estado: Mapped[EstadoCierre] = mapped_column(
        pg_enum(EstadoCierre, "estado_cierre"), default=EstadoCierre.CERRADO
    )

    # ---- «Negocios» (X02 · M16): the deal's own data and its signature flow.
    inmueble_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("inmuebles.id", ondelete="SET NULL")
    )
    valor: Mapped[int | None] = mapped_column(BigInteger)  # monthly rent or sale price, COP
    etapa: Mapped[str | None] = mapped_column(String(40))  # example stages (services.negocios)
    oferta: Mapped[str | None] = mapped_column(String(300))  # «Última oferta»
    pct_venta: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # None = Configuración's
    uso_comercial: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    arrendatario_juridica: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    referido: Mapped[str | None] = mapped_column(String(200))
    docs_ubicacion: Mapped[str | None] = mapped_column(String(300))
    contrato_adjunto: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    notaria: Mapped[str | None] = mapped_column(String(200))
    notaria_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # «Solicitar cierre» by the asesor: 'promesa' (sale, first signature) or 'cierre'.
    solicitud: Mapped[str | None] = mapped_column(String(10))
    solicitud_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    solicitud_nota: Mapped[str | None] = mapped_column(String(300))
    devuelto_motivo: Mapped[str | None] = mapped_column(String(300))
    devuelto_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Signatures confirmed by the Auxiliar: promesa (sales only) and the closing one.
    promesa_fecha: Mapped[date | None] = mapped_column(Date)
    firma_fecha: Mapped[date | None] = mapped_column(Date, index=True)  # = «negocio cerrado»
    confirmado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    caida_motivo: Mapped[str | None] = mapped_column(String(100))
    caida_obs: Mapped[str | None] = mapped_column(String(300))
    caida_reportada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    caida_reportada_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    caida_confirmada_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lead: Mapped[Lead] = relationship(lazy="joined")
    cerrador: Mapped[User | None] = relationship(foreign_keys=[cerrador_id], lazy="joined")
    filtro: Mapped[User | None] = relationship(foreign_keys=[filtro_id], lazy="joined")
    captador: Mapped[User | None] = relationship(foreign_keys=[captador_id], lazy="joined")

    @property
    def code(self) -> str:
        return f"NEG-{self.numero:04d}"


class Pago(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Money the company pays a person: a commission, a bonus or a salary period."""

    __tablename__ = "pagos"

    beneficiario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    tipo: Mapped[TipoPago] = mapped_column(pg_enum(TipoPago, "tipo_pago"))
    concepto: Mapped[str] = mapped_column(String(300))
    valor: Mapped[int] = mapped_column(BigInteger)
    fecha_programada: Mapped[date] = mapped_column(Date)
    estado: Mapped[EstadoPago] = mapped_column(
        pg_enum(EstadoPago, "estado_pago"), default=EstadoPago.EN_PROCESO
    )
    pagado_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    registrado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    beneficiario: Mapped[User] = relationship(foreign_keys=[beneficiario_id], lazy="joined")


class _Movimiento:
    """Shared columns of commissions and bonuses (same approval flow)."""

    beneficiario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    concepto: Mapped[str] = mapped_column(String(300))
    detalle: Mapped[str | None] = mapped_column(Text)
    valor: Mapped[int] = mapped_column(BigInteger)
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True))  # when it was earned
    periodo: Mapped[date] = mapped_column(Date, index=True)  # month it counts in
    estado: Mapped[EstadoCompensacion] = mapped_column(
        pg_enum(EstadoCompensacion, "estado_compensacion", create_type=False),
        default=EstadoCompensacion.GENERADA,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    pago_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pagos.id", ondelete="SET NULL"))


class Comision(UUIDPrimaryKeyMixin, TimestampMixin, _Movimiento, Base):
    __tablename__ = "comisiones"
    __table_args__ = (
        # One automatic commission per deal and role (manual ones can repeat).
        Index(
            "uq_comision_cierre_tipo",
            "cierre_id",
            "tipo",
            unique=True,
            postgresql_where=text("cierre_id IS NOT NULL AND tipo <> 'manual'"),
        ),
        Index(
            "uq_comision_grupal_periodo",
            "beneficiario_id",
            "periodo",
            unique=True,
            postgresql_where=text("tipo = 'grupal'"),
        ),
    )

    tipo: Mapped[TipoComision] = mapped_column(pg_enum(TipoComision, "tipo_comision"))
    cierre_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("cierres.id", ondelete="SET NULL"), index=True
    )
    base: Mapped[int | None] = mapped_column(BigInteger)  # amount the % applies to
    porcentaje: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))

    beneficiario: Mapped[User] = relationship(
        foreign_keys="Comision.beneficiario_id", lazy="joined"
    )
    cierre: Mapped[Cierre | None] = relationship(lazy="joined")
    pago: Mapped[Pago | None] = relationship(lazy="joined")


class Bono(UUIDPrimaryKeyMixin, TimestampMixin, _Movimiento, Base):
    __tablename__ = "bonos"
    __table_args__ = (
        Index(
            "uq_bono_rendimiento_periodo",
            "beneficiario_id",
            "periodo",
            unique=True,
            postgresql_where=text("tipo = 'rendimiento'"),
        ),
    )

    tipo: Mapped[TipoBono] = mapped_column(pg_enum(TipoBono, "tipo_bono"))
    rendimiento: Mapped[int | None] = mapped_column(SmallInteger)  # the month's result it used

    beneficiario: Mapped[User] = relationship(foreign_keys="Bono.beneficiario_id", lazy="joined")
    pago: Mapped[Pago | None] = relationship(lazy="joined")


class SalarioConfig(Base):
    """Monthly salary of one person (Gerencia sets it)."""

    __tablename__ = "salario_config"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    salario_mensual: Mapped[int] = mapped_column(BigInteger)
    updated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )


class LiquidacionSalario(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Salary of one pay period: 1st (1–15, paid on the 15th) or 2nd (16–end, paid on the 30th)."""

    __tablename__ = "liquidaciones_salario"
    __table_args__ = (UniqueConstraint("user_id", "periodo", "corte", name="uq_liquidacion_corte"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    periodo: Mapped[date] = mapped_column(Date)  # first day of the month
    corte: Mapped[int] = mapped_column(SmallInteger)  # 1 or 2
    salario_corte: Mapped[int] = mapped_column(BigInteger)
    descuento: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    novedades: Mapped[str | None] = mapped_column(String(300))
    estado: Mapped[EstadoSalario] = mapped_column(
        pg_enum(EstadoSalario, "estado_salario"), default=EstadoSalario.POR_CONFIRMAR
    )
    pago_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("pagos.id", ondelete="SET NULL"))

    user: Mapped[User] = relationship(foreign_keys=[user_id], lazy="joined")

    @property
    def a_pagar(self) -> int:
        return self.salario_corte - self.descuento


class CompensacionEvento(UUIDPrimaryKeyMixin, Base):
    """History («Historial»): who created, approved, paid, adjusted or cancelled what."""

    __tablename__ = "compensacion_eventos"
    __table_args__ = (Index("ix_compensacion_eventos_entidad", "entidad", "entidad_id"),)

    entidad: Mapped[str] = mapped_column(String(20))  # comision · bono · salario · cierre · config
    entidad_id: Mapped[str] = mapped_column(String(40))
    accion: Mapped[str] = mapped_column(String(200))
    antes: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    despues: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp(), nullable=False
    )

    created_by: Mapped[User | None] = relationship(foreign_keys=[created_by_id], lazy="joined")
