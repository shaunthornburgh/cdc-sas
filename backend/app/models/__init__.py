"""ORM models. Import every model here so Alembic autogenerate can see it."""

from app.db.base import Base
from app.models.administracion import (
    AdminEvento,
    Inventario,
    InventarioAmbiente,
    Reparacion,
    Solicitud,
)
from app.models.asistencia import AsistenciaEvento, Marcacion, Sede, UbicacionAsignada
from app.models.avisos import AgendaItem, Aviso, AvisoNota, Comunicado
from app.models.capacitaciones import (
    Capacitacion,
    CapacitacionEvento,
    CapacitacionParticipante,
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
from app.models.configuracion import ConfigEvento, ConfigSeccion
from app.models.inmuebles import Inmueble, InmuebleEvento
from app.models.integraciones import Integracion, IntegracionEvento
from app.models.leads import Cita, Lead, LeadEvento, Seguimiento
from app.models.movimientos import Movimiento, MovimientoEvento, MovimientosConfig
from app.models.negocios import NegocioAbono
from app.models.novedades import Novedad
from app.models.pausas import PausaActiva, PausaConfig
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
from app.models.rutas import Ruta, RutaEvento, RutaLlegada, RutaZona
from app.models.user import ActividadEvento, User, UserActividad, UserCambio

__all__ = [
    "ActividadEvento",
    "AdminEvento",
    "AgendaItem",
    "Aseguradora",
    "AsistenciaEvento",
    "Aviso",
    "AvisoNota",
    "Base",
    "Bono",
    "Calificacion",
    "Capacitacion",
    "CapacitacionEvento",
    "CapacitacionParticipante",
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
    "Marcacion",
    "Inventario",
    "InventarioAmbiente",
    "Lead",
    "LeadEvento",
    "LiquidacionSalario",
    "Movimiento",
    "MovimientoEvento",
    "MovimientosConfig",
    "NegocioAbono",
    "Novedad",
    "Pago",
    "PausaActiva",
    "PausaConfig",
    "Pedido",
    "Plataforma",
    "Poliza",
    "PolizaEvento",
    "PolizaTipo",
    "Ruta",
    "RutaEvento",
    "RutaLlegada",
    "RutaZona",
    "Sede",
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
    "UbicacionAsignada",
    "User",
    "UserActividad",
    "UserCambio",
]
