"""ORM models. Import every model here so Alembic autogenerate can see it."""

from app.db.base import Base
from app.models.administracion import (
    AdminEvento,
    Inventario,
    InventarioAmbiente,
    Reparacion,
    Solicitud,
)
from app.models.captaciones import Captacion, CaptacionEvento
from app.models.compensacion import (
    Bono,
    Cierre,
    Comision,
    CompensacionConfig,
    CompensacionEvento,
    LiquidacionSalario,
    Pago,
    SalarioConfig,
)
from app.models.inmuebles import Inmueble, InmuebleEvento
from app.models.leads import Cita, Lead, LeadEvento, Seguimiento
from app.models.novedades import Novedad
from app.models.pedidos import Pedido, PedidoEvento
from app.models.preoperacional import Preoperacional, PreoperacionalConfig
from app.models.rendimiento import Calificacion, RendimientoCambio, RendimientoConfig
from app.models.user import ActividadEvento, User, UserActividad

__all__ = [
    "ActividadEvento",
    "AdminEvento",
    "Base",
    "Bono",
    "Calificacion",
    "Captacion",
    "CaptacionEvento",
    "Cierre",
    "Comision",
    "CompensacionConfig",
    "CompensacionEvento",
    "Cita",
    "Inmueble",
    "InmuebleEvento",
    "Inventario",
    "InventarioAmbiente",
    "Lead",
    "LeadEvento",
    "LiquidacionSalario",
    "Novedad",
    "Pago",
    "Pedido",
    "PedidoEvento",
    "Preoperacional",
    "PreoperacionalConfig",
    "RendimientoCambio",
    "Reparacion",
    "RendimientoConfig",
    "SalarioConfig",
    "Seguimiento",
    "Solicitud",
    "User",
    "UserActividad",
]
