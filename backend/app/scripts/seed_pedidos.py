"""Demo pedidos (called from app.scripts.seed): open, due today, urgent, expired and closed ones.

Clients and phones are fictitious. Everything goes through the service so the history reads
like real use; deadlines and timestamps are then moved relative to now.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Lead, Pedido, PedidoEvento
from app.models.enums import MotivoPerdidaPedido as MP
from app.models.enums import TipoInmueble as T
from app.models.enums import TipoNegocio as N
from app.models.enums import UrgenciaPedido as U
from app.services import fechas
from app.services import pedidos as svc
from app.services.users import get_user_by_email

NOW = fechas.now()


def at(days: int, hour: int = 18, minute: int = 0) -> datetime:
    d = fechas.local_date(NOW) + timedelta(days=days)
    return datetime.combine(d, time(hour, minute), tzinfo=fechas.BOGOTA)


def seed_pedidos(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(Pedido)):
        return 0
    u = {
        k: get_user_by_email(db, f"{k}@example.com")
        for k in ("asesor", "diego", "carla", "atencion", "preventas", "coordinacion")
    }
    if any(v is None for v in u.values()):
        raise RuntimeError("Seed the demo users first.")
    lead = db.scalar(select(Lead).where(Lead.full_name == "Daniela Torres"))

    def nuevo(who, creado_dias, **data) -> Pedido:
        responsable = data.pop("responsable", who)
        fecha = data.pop("fecha_limite")
        data["fecha_limite"] = max(fecha, NOW + timedelta(minutes=5))  # service needs a future date
        p = svc.create_pedido(
            db, data, actor=u[who], responsable_id=u[responsable].id, otra_necesidad=True
        )
        p.fecha_limite = fecha
        p.created_at = NOW - timedelta(days=creado_dias)
        for ev in p.eventos or db.scalars(
            select(PedidoEvento).where(PedidoEvento.pedido_id == p.id)
        ):
            ev.created_at = p.created_at
        db.flush()
        return p

    # ---- Abiertos
    nuevo(
        "asesor",
        1,
        cliente_nombre="Ricardo Montoya",
        cliente_telefono="300 555 0211",
        negocio=N.ARRIENDO,
        tipo_inmueble=T.APARTAMENTO,
        zona="Laureles",
        presupuesto=2_000_000,
        fecha_limite=at(0, 17),
        urgencia=U.URGENTE,
        observaciones="2 habitaciones, con parqueadero. Se muda la próxima semana.",
    )
    nuevo(
        "diego",
        1,
        cliente_nombre="Juliana Ochoa",
        cliente_telefono="301 555 0218",
        negocio=N.VENTA,
        tipo_inmueble=T.APARTAMENTO,
        zona="El Poblado",
        presupuesto=700_000_000,
        fecha_limite=at(0, 18),
        observaciones="Vista y balcón, piso alto.",
    )
    nuevo(
        "asesor",
        2,
        cliente_nombre="Martín Valencia",
        cliente_telefono="310 555 0225",
        negocio=N.VENTA,
        tipo_inmueble=T.CASA,
        zona="Sabaneta",
        presupuesto=600_000_000,
        fecha_limite=at(5),
        observaciones="Con patio para dos perros.",
    )
    nuevo(
        "diego",
        2,
        cliente_nombre="Lucía Herrera",
        cliente_telefono="312 555 0232",
        negocio=N.VENTA,
        tipo_inmueble=T.CASA,
        zona="Envigado",
        presupuesto=500_000_000,
        fecha_limite=at(2),
        urgencia=U.ALTA,
        observaciones="Con patio, cerca de colegios.",
    )
    nuevo(
        "carla",
        0,
        cliente_nombre="Ferretería El Tornillo",
        cliente_telefono="604 555 0240",
        negocio=N.ARRIENDO,
        tipo_inmueble=T.LOCAL,
        zona="Guayabal",
        presupuesto=4_000_000,
        fecha_limite=at(12),
        observaciones="Local sobre vía principal, mínimo 60 m².",
    )
    if lead:
        nuevo(
            "atencion",
            1,
            cliente_nombre=lead.full_name,
            cliente_telefono=lead.phone,
            lead_id=lead.id,
            negocio=N.ARRIENDO,
            tipo_inmueble=T.CASA,
            zona="Sabaneta",
            presupuesto=3_200_000,
            fecha_limite=at(7),
            responsable="carla",
            observaciones="Casa con patio: tiene 2 perros. Registrado desde el lead.",
        )
    nuevo(
        "preventas",
        0,
        cliente_nombre="Andrés Cardona",
        cliente_telefono="301 555 0188",
        negocio=N.VENTA,
        tipo_inmueble=T.CASA,
        zona="Envigado",
        presupuesto=750_000_000,
        fecha_limite=at(9),
        responsable="diego",
        observaciones="Pide 4 habitaciones.",
    )

    # ---- Vencido sin decidir (shows in the alert and «Vencidos»)
    nuevo(
        "asesor",
        6,
        cliente_nombre="Gloria Patiño",
        cliente_telefono="320 555 0247",
        negocio=N.VENTA,
        tipo_inmueble=T.CASA,
        zona="Envigado",
        presupuesto=500_000_000,
        fecha_limite=at(0, 9),
        observaciones="Sin opciones enviadas todavía.",
    )

    # ---- Cerrados: recuperado, perdido después de vencer, atendido a tiempo
    rec = nuevo(
        "asesor",
        12,
        cliente_nombre="Óscar Giraldo",
        cliente_telefono="321 555 0254",
        negocio=N.ARRIENDO,
        tipo_inmueble=T.LOCAL,
        zona="Guayabal",
        presupuesto=3_500_000,
        fecha_limite=at(-6),
    )
    svc.extender(
        db, rec, at(3), motivo="El cliente pidió más tiempo para decidir.", actor=u["asesor"]
    )
    svc.atender(db, rec, nota="Se recuperó: arrendó el local de la calle 10.", actor=u["asesor"])

    per = nuevo(
        "carla",
        14,
        cliente_nombre="Natalia Ríos",
        cliente_telefono="322 555 0261",
        negocio=N.ARRIENDO,
        tipo_inmueble=T.APARTAMENTO,
        zona="Belén",
        presupuesto=2_200_000,
        fecha_limite=at(-9),
    )
    svc.marcar_perdido(
        db, per, motivo=MP.COMPRO_CON_OTRO, nota="Arrendó con otra inmobiliaria.", actor=u["carla"]
    )

    ok = nuevo(
        "diego",
        8,
        cliente_nombre="Felipe Arango",
        cliente_telefono="323 555 0193",
        negocio=N.ARRIENDO,
        tipo_inmueble=T.APARTAMENTO,
        zona="Envigado",
        presupuesto=2_800_000,
        fecha_limite=at(4),
    )
    svc.proponer(
        db,
        ok,
        inmueble="INM-0333 · Apto Laureles",
        nota="El propietario acepta mascotas.",
        actor=u["carla"],
    )
    svc.atender(db, ok, nota="Se enviaron 4 opciones · cita agendada.", actor=u["diego"])

    db.flush()
    return db.scalar(select(func.count()).select_from(Pedido)) or 0
