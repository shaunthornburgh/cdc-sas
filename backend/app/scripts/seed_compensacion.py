"""Demo compensation (called from app.scripts.seed, after the rendimiento seed).

Goes through the services like real use: salaries set by Gerencia, the ganancia of each closed deal
registered by the Auxiliar (which generates the commissions), the visto bueno → approval → payment
flow, last month's bonuses and group commission, and the salary periods. Payment dates are then
moved to the day they would have been paid. Amounts are example values.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Bono, Cierre, Comision, Pago, SalarioConfig
from app.models.enums import EstadoCompensacion as E
from app.models.enums import EstadoPago, TipoNegocio
from app.services import compensacion as svc
from app.services import fechas
from app.services import rendimiento as rend
from app.services.users import get_user_by_email

SALARIOS = {
    "asesor": 1_800_000,
    "bruno": 1_800_000,
    "carla": 1_800_000,
    "diego": 1_800_000,
    "atencion": 2_400_000,
    "preventas": 1_500_000,
    "coordinacion": 4_000_000,
    "auxiliar": 2_000_000,
}
GANANCIA = {
    TipoNegocio.VENTA: (7_500_000, 6_300_000, 8_400_000),
    TipoNegocio.ARRIENDO: (2_700_000, 1_900_000, 3_200_000),
}


def _at(d, hour=10) -> datetime:
    return datetime.combine(d, time(hour), tzinfo=fechas.BOGOTA)


def seed_compensacion(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(SalarioConfig)):
        return 0
    u = {k: get_user_by_email(db, f"{k}@example.com") for k in [*SALARIOS, "gerencia"]}
    if any(v is None for v in u.values()):
        raise RuntimeError("Seed the demo users first.")
    ger, aux = u["gerencia"], u["auxiliar"]
    hoy = fechas.local_date(fechas.now())
    cur, prev = rend.periodo(), rend.periodo().anterior()

    for k, v in SALARIOS.items():
        svc.set_salario(db, u[k], v, actor=ger)

    # ---- closed deals: the Auxiliar registers the ganancia (the newest two are left for the demo)
    deals = svc.cierres(db, aux)
    recientes = [c.id for c in sorted(deals, key=lambda c: c.cerrado_at, reverse=True)[:2]]
    for i, c in enumerate(sorted(deals, key=lambda c: c.cerrado_at)):
        if c.id in recientes:
            continue
        opciones = GANANCIA[c.negocio or TipoNegocio.ARRIENDO]
        captador = None
        if c.negocio == TipoNegocio.VENTA:
            captador = u["bruno"] if i % 2 == 0 else u["asesor"]
        svc.registrar_ganancia(
            db,
            c,
            ganancia=opciones[i % len(opciones)],
            captador_id=captador.id if captador else None,
            actor=aux,
        )

    def flujo(clase: str, item, hasta: str) -> None:
        if item.estado != E.GENERADA:
            return
        svc.accion(db, clase, item, "visto_bueno", actor=aux)
        if hasta == "visto_bueno":
            return
        svc.accion(db, clase, item, "aprobar", actor=ger)
        if hasta == "aprobar" or item.pago.fecha_programada > hoy:
            return
        svc.accion(db, clase, item, "pagar", actor=ger)

    # ---- last month: everything approved, paid on day 5 (if that day has come)
    for c in db.scalars(select(Comision).where(Comision.periodo == prev.first)).unique():
        flujo("comision", c, "pagar")
    # Month-end of last month: performance bonuses and the Coordinador's group commission.
    svc.calcular_mes(db, prev.key, actor=aux)
    for b in db.scalars(select(Bono).where(Bono.periodo == prev.first)).unique():
        flujo("bono", b, "pagar")
    for c in db.scalars(select(Comision).where(Comision.periodo == prev.first)).unique():
        flujo("comision", c, "pagar")

    # ---- this month: a mix of states for the demo
    for i, c in enumerate(
        db.scalars(
            select(Comision).where(Comision.periodo == cur.first).order_by(Comision.fecha)
        ).unique()
    ):
        if i % 3 == 0:
            flujo("comision", c, "aprobar")
        elif i % 3 == 1:
            flujo("comision", c, "visto_bueno")
    svc.crear_manual(
        db,
        "bono",
        {
            "beneficiario_id": u["carla"].id,
            "concepto": "Bono por referido · propietario en Belén",
            "valor": 150_000,
            "fecha": _at(cur.first + timedelta(days=min(3, hoy.day - 1))),
            "detalle": "Refirió un propietario que firmó administración",
        },
        actor=ger,
    )

    # ---- salaries: last month paid; this month's 1st period paid once its day passed
    cfg = svc.get_config(db)
    for periodo, corte in ((prev.first, 1), (prev.first, 2), (cur.first, 1), (cur.first, 2)):
        fecha = svc.corte_fecha(periodo, corte, cfg)
        for liq in svc.liquidaciones(db, aux, periodo, corte):
            if fecha <= hoy:
                svc.accion_salario(db, liq, "confirmar", actor=aux)
                svc.accion_salario(db, liq, "pagar", actor=ger)
            elif fecha - hoy <= timedelta(days=3) and liq.user.full_name < "D":
                svc.accion_salario(db, liq, "confirmar", actor=aux)

    # Payments happened on their scheduled day, not today.
    for pago in db.scalars(select(Pago).where(Pago.estado == EstadoPago.PAGADO)).unique():
        pago.pagado_at = _at(pago.fecha_programada)
    db.flush()
    return db.scalar(select(func.count()).select_from(Cierre)) or 0
