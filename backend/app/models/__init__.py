"""ORM models. Import every model here so Alembic autogenerate can see it."""

from app.db.base import Base
from app.models.administracion import (
    AdminEvento,
    Inventario,
    InventarioAmbiente,
    Reparacion,
    Solicitud,
)
from app.models.avisos import AgendaItem, Aviso, AvisoNota, Comunicado
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
from app.models.configuracion import ConfigEvento, ConfigSeccion
from app.models.inmuebles import Inmueble, InmuebleEvento
from app.models.integraciones import Integracion, IntegracionEvento
from app.models.leads import Cita, Lead, LeadEvento, Seguimiento
from app.models.movimientos import Movimiento, MovimientoEvento, MovimientosConfig
from app.models.novedades import Novedad
from app.models.pedidos import Pedido, PedidoEvento
from app.models.plataformas import (
    Plataforma,
    PlataformaActualizacion,
    PlataformaEvento,
    PlataformaPlan,
    PlataformasConfig,
)
from app.models.polizas import Aseguradora, Poliza, PolizaEvento, PolizaTipo
from app.models.preoperacional import Preoperacional, PreoperacionalConfig
from app.models.rendimiento import Calificacion, RendimientoCambio, RendimientoConfig
from app.models.user import ActividadEvento, User, UserActividad, UserCambio

__all__ = [
    "ActividadEvento",
    "AdminEvento",
    "AgendaItem",
    "Aseguradora",
    "Aviso",
    "AvisoNota",
    "Base",
    "Bono",
    "Calificacion",
    "Captacion",
    "CaptacionEvento",
    "Cierre",
    "Comision",
    "Comunicado",
    "ConfigEvento",
    "ConfigSeccion",
    "CompensacionConfig",
    "CompensacionEvento",
    "Cita",
    "Inmueble",
    "InmuebleEvento",
    "Integracion",
    "IntegracionEvento",
    "Inventario",
    "InventarioAmbiente",
    "Lead",
    "LeadEvento",
    "LiquidacionSalario",
    "Movimiento",
    "MovimientoEvento",
    "MovimientosConfig",
    "Novedad",
    "Pago",
    "Pedido",
    "Plataforma",
    "Poliza",
    "PolizaEvento",
    "PolizaTipo",
    "PlataformaActualizacion",
    "PlataformaEvento",
    "PlataformaPlan",
    "PlataformasConfig",
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
    "UserCambio",
]
