"""Demo traditional portals (K15 / K15-ger), called from app.scripts.seed after leads.

* Ciencuadras, Espacio Urbano and Proppi are active, with K15's prices and quotas. Each has its
  current quarterly plan and the previous one, so «Resultados» has costs for the last months.
  Proppi's plan is about to expire, so it shows the alarm.
* About five months of updates by Coordinación (one in six by the Auxiliar), with K15's gaps
  between them: some are late. Proppi's last update is 9 days old, so it is «Atrasada».
* Finca Raíz and Metrocuadrado exist but are inactive (no plan): Gerencia can switch them on.
* Leads from the portals over the last four months (K15-ger's figures), closed so they don't show
  up as work to do: most «Perdido», a few «Ganado» (those appear as deals in Compensación, without
  a closing asesor). Some had a cita realizada.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Cita, Lead, Plataforma, PlataformaActualizacion, PlataformaPlan
from app.models.enums import (
    EstadoCita,
    EtapaLead,
    FuenteLead,
    MotivoPerdida,
    TipoCita,
    TipoNegocio,
)
from app.services import fechas
from app.services import plataformas as svc
from app.services.users import get_user_by_email

F = FuenteLead
# fuente, nombre, color, cupo, usados, destacados, dest. usados, precio trimestral,
# days to expiry, alarm, days since last update, gaps between updates (going back)
PORTALES = [
    (
        F.CIENCUADRAS,
        "Ciencuadras",
        "#00843D",
        40,
        32,
        5,
        3,
        800_000,
        11,
        10,
        2,
        [3, 4, 3, 5, 4, 3, 6],
    ),
    (
        F.ESPACIO_URBANO,
        "Espacio Urbano",
        "#8DC63F",
        25,
        18,
        3,
        2,
        500_000,
        28,
        10,
        4,
        [4, 3, 5, 4, 3, 4, 6],
    ),
    (F.PROPPI, "Proppi", "#1F7FB0", 10, 6, 2, 1, 300_000, 5, 7, 9, [5, 4, 6, 9, 5, 4, 8]),
]
INACTIVOS = [(F.FINCA_RAIZ, "Finca Raíz", "#B7791F"), (F.METROCUADRADO, "Metrocuadrado", "#7A5AA6")]
HORAS = [time(8, 40), time(9, 15), time(10, 5), time(16, 30), time(11, 20)]
# Leads, citas and cierres per month (3 months ago … this month), as K15-ger.
LEADS = {
    F.CIENCUADRAS: ([13, 14, 13, 24], [2, 2, 2, 5], [1, 2, 1, 3]),
    F.ESPACIO_URBANO: ([8, 9, 8, 15], [1, 2, 1, 3], [1, 0, 1, 3]),
    F.PROPPI: ([3, 4, 3, 9], [1, 1, 1, 2], [0, 1, 0, 2]),
}


def _at(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=fechas.BOGOTA)


def _mes_atras(d: date, n: int) -> date:
    m = d.month - n
    return date(d.year + (m - 1) // 12, (m - 1) % 12 + 1, 1)


def seed_plataformas(db: Session) -> int:
    if db.scalar(select(Plataforma.id).limit(1)):
        return 0
    coord = get_user_by_email(db, "coordinacion@example.com")
    aux = get_user_by_email(db, "auxiliar@example.com")
    ger = get_user_by_email(db, "gerencia@example.com")
    if None in (coord, aux, ger):
        raise RuntimeError("Seed the demo users first.")
    cfg = svc.get_config(db)
    hoy = svc.hoy()
    now = fechas.now()

    for orden, (
        fuente,
        nombre,
        color,
        cupo,
        uso,
        dest,
        du,
        precio,
        vence,
        alarma,
        hace,
        pasos,
    ) in enumerate(PORTALES):
        p = Plataforma(
            fuente=fuente, nombre=nombre, color=color, orden=orden, responsable_id=coord.id
        )
        db.add(p)
        db.flush()
        venc = hoy + timedelta(days=vence)
        act = venc - timedelta(days=91)
        for a, b in ((act - timedelta(days=92), act - timedelta(days=1)), (act, venc)):
            db.add(
                PlataformaPlan(
                    plataforma_id=p.id,
                    precio=precio,
                    activacion=a,
                    vencimiento=b,
                    cupo_total=cupo,
                    destacados_total=dest,
                    alarma_dias=alarma,
                    creado_por_id=ger.id,
                )
            )
        # Update dates, from the last one backwards for about five months
        dias, d, i = [], hoy - timedelta(days=hace), 0
        while d >= hoy - timedelta(days=150):
            dias.append(d)
            d -= timedelta(days=pasos[i % len(pasos)])
            i += 1
        dias.reverse()
        prev = None
        for j, d in enumerate(dias):
            at = _at(d, HORAS[j % len(HORAS)])
            if at > now:
                at = now - timedelta(minutes=5)
            gap = (d - prev).days if prev else None
            k = len(dias) - 1 - j  # 0 = the latest
            quien = aux if k % 6 == 4 else coord
            db.add(
                PlataformaActualizacion(
                    plataforma_id=p.id,
                    realizada_at=at,
                    actualizado_por_id=quien.id,
                    responsable_id=coord.id,
                    cupo_total=cupo,
                    cupo_usado=max(0, uso - (k % 4)),
                    destacados_total=dest,
                    destacados_usados=max(0, du - (k % 2)),
                    observacion=None
                    if gap is None or gap <= cfg.dias_regla
                    else "Se actualizó tarde",
                    dias_desde_anterior=gap,
                    regla_dias=cfg.dias_regla,
                    a_tiempo=gap is None or gap <= cfg.dias_regla,
                )
            )
            prev = d
    for orden, (fuente, nombre, color) in enumerate(INACTIVOS, start=len(PORTALES)):
        db.add(Plataforma(fuente=fuente, nombre=nombre, color=color, orden=orden, activa=False))
    db.flush()

    n_leads = 0
    for fuente, (leads, citas, cierres) in LEADS.items():
        for back in range(4):
            m1 = _mes_atras(hoy, 3 - back)
            ultimo = min(
                hoy, (m1.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
            )
            span = (ultimo - m1).days + 1
            for n in range(leads[back]):
                d = m1 + timedelta(days=(n * 7 + 3) % span)
                when = _at(d, time(9 + n % 8, 15))
                if when > now:
                    when = now - timedelta(hours=1)
                ganado = n < cierres[back]
                ld = Lead(
                    full_name=f"Cliente {fuente.value.replace('_', ' ').title()} {back}-{n + 1}",
                    phone=f"300{n_leads:07d}",
                    fuente=fuente,
                    fuente_detalle="Histórico de plataformas (demo)",
                    negocio=TipoNegocio.ARRIENDO if n % 3 else TipoNegocio.VENTA,
                    etapa=EtapaLead.GANADO if ganado else EtapaLead.PERDIDO,
                    motivo_perdida=None if ganado else MotivoPerdida.NO_INTERESADO,
                    perdida_descuenta=None if ganado else False,
                    cerrado_at=min(now, when + timedelta(days=6)),
                )
                db.add(ld)
                db.flush()
                ld.created_at = ld.updated_at = when
                if n < citas[back]:
                    db.add(
                        Cita(
                            lead_id=ld.id,
                            tipo=TipoCita.VISITA_VENTA
                            if ld.negocio == TipoNegocio.VENTA
                            else TipoCita.VISITA_ARRIENDO,
                            scheduled_at=min(now, when + timedelta(days=2)),
                            estado=EstadoCita.REALIZADA,
                        )
                    )
                n_leads += 1
    db.flush()
    return db.scalar(select(func.count()).select_from(PlataformaActualizacion)) or 0
