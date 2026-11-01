"""Plataformas tradicionales (prototypes K15 «Actualización de plataformas» and K15-ger, G-079).

* **What it tracks**: for each traditional portal (Ciencuadras, Espacio Urbano, Proppi…) its
  paid plan (price, dates, quota, featured listings, expiry alarm) and the periodic «actualización»:
  someone checks the portal and records active listings, the plan's total quota and featured
  listings used. The system stores the date, time and who did it.
* **Rule**: each portal must be updated at least every N days (7, an example value «PENDIENTE DE
  CONFIGURACIÓN» until Gerencia confirms it). Past that, the portal is «Atrasada». An update made
  more than N days after the previous one is «Tarde».
* **Who**: Coordinación registers updates (K15). Gerencia assigns the responsable of each portal,
  registers plans, sets the rule and sees results and history (K15-ger), but doesn't register
  updates. The Auxiliar sees the page and registers the portals assigned to her (she appears in
  K15-ger's log). The responsable can be someone from Coordinación or the Auxiliar.
* **Results**: leads, citas and cierres come from the leads whose `fuente` is the portal. The cost
  is each plan's price spread over its days, counted for the days of the range (up to today).
* **Rendimiento**: «Actualización de plataformas» of the Coordinador = share of days of the month
  that the portals assigned to them were «al día».
"""

from __future__ import annotations

import calendar
import csv
import io
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Cita,
    Lead,
    Plataforma,
    PlataformaActualizacion,
    PlataformaEvento,
    PlataformaPlan,
    PlataformasConfig,
    User,
)
from app.models.enums import Cargo, EstadoCita, EtapaLead, FuenteLead, TipoEventoPlataforma
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

EV = TipoEventoPlataforma
VEN = (Cargo.GERENCIA, Cargo.COORDINACION, Cargo.AUXILIAR_ADMINISTRATIVA)
RESPONSABLES = (Cargo.COORDINACION, Cargo.AUXILIAR_ADMINISTRATIVA)
MESES = fechas._MESES


# ---------------------------------------------------------------- access


def can_view(user: User) -> bool:
    return user.is_active and user.cargo in VEN


def can_manage(user: User) -> bool:
    return user.is_active and user.cargo == Cargo.GERENCIA


def can_register(user: User, p: Plataforma) -> bool:
    if not user.is_active or not p.activa:
        return False
    return user.cargo == Cargo.COORDINACION or p.responsable_id == user.id


def can_download(user: User) -> bool:
    return user.is_active and user.cargo in (Cargo.GERENCIA, Cargo.COORDINACION)


def ensure_view(user: User) -> None:
    if not can_view(user):
        raise PermissionDeniedError(
            "La actualización de plataformas la ven Coordinación, Gerencia y la Auxiliar."
        )


def ensure_manage(user: User) -> None:
    if not can_manage(user):
        raise PermissionDeniedError("Esto lo define Gerencia.")


def get_plataforma(db: Session, user: User, id_: uuid.UUID) -> Plataforma:
    ensure_view(user)
    p = db.get(Plataforma, id_)
    if p is None:
        raise NotFoundError("Esa plataforma no existe.")
    return p


def plataformas(db: Session, *, todas: bool = False) -> list[Plataforma]:
    q = select(Plataforma).order_by(Plataforma.orden, Plataforma.nombre)
    if not todas:
        q = q.where(Plataforma.activa.is_(True))
    return list(db.scalars(q).unique())


def responsables(db: Session) -> list[User]:
    """K15-ger's «Responsable asignado» options: Coordinación and the Auxiliar."""
    return list(
        db.scalars(
            select(User)
            .where(User.is_active.is_(True), User.cargo.in_(RESPONSABLES))
            .order_by(User.full_name)
        ).unique()
    )


# ---------------------------------------------------------------- config and helpers


def hoy() -> date:
    return fechas.local_date(fechas.now())


def get_config(db: Session) -> PlataformasConfig:
    cfg = db.get(PlataformasConfig, 1)
    if cfg is None:
        cfg = PlataformasConfig(id=1, dias_regla=7, confirmada=False)
        db.add(cfg)
        db.flush()
    return cfg


def guardar_regla(db: Session, dias: int, *, actor: User) -> PlataformasConfig:
    ensure_manage(actor)
    if not 1 <= dias <= 60:
        raise DomainError("La regla va de 1 a 60 días.")
    cfg = get_config(db)
    antes = cfg.dias_regla
    cfg.dias_regla, cfg.confirmada = dias, True
    cfg.updated_by_id, cfg.updated_by = actor.id, actor
    _evento(db, None, EV.REGLA, actor, antes=f"{antes} días", despues=f"{dias} días")
    db.flush()
    return cfg


def _evento(
    db: Session,
    p: Plataforma | None,
    tipo: TipoEventoPlataforma,
    actor: User | None,
    *,
    antes: str | None = None,
    despues: str | None = None,
    detalle: str | None = None,
) -> PlataformaEvento:
    ev = PlataformaEvento(
        plataforma_id=p.id if p else None,
        tipo=tipo,
        actor_id=actor.id if actor else None,
        antes=antes,
        despues=despues,
        detalle=detalle,
    )
    ev.actor = actor
    db.add(ev)
    return ev


def fmt_dia(d: date, year: bool = False) -> str:
    return f"{d.day} {MESES[d.month - 1]}" + (f" {d.year}" if year else "")


def fmt_cop(v: float | int | None) -> str:
    return "—" if v is None else "$" + f"{round(v):,}".replace(",", ".")


def local_day(dt: datetime) -> date:
    return fechas.local_date(dt)


# ---------------------------------------------------------------- plans


def plan_en(p: Plataforma, d: date) -> PlataformaPlan | None:
    """The plan in force on day `d` (the latest activated by then, even if it already expired)."""
    vig = [x for x in p.planes if x.activacion <= d]
    return vig[-1] if vig else None


def plan_estado(plan: PlataformaPlan | None, d: date) -> tuple[str, str, str]:
    """(code, text, chip) as K15-ger's «Plan» column."""
    if plan is None:
        return "sin_plan", "Sin plan registrado", "gray"
    if plan.vencimiento < d:
        return "vencido", "Vencido · inactivo", "bad"
    n = (plan.vencimiento - d).days
    if n <= plan.alarma_dias:
        return (
            "por_vencer",
            "⚠ Vence hoy" if n == 0 else f"⚠ Vence en {n} día{'s' if n != 1 else ''}",
            "warn",
        )
    return "activo", f"Activo · vence {fmt_dia(plan.vencimiento)}", "ok"


def estado_plan(p: Plataforma, d: date) -> tuple[str, str, str]:
    """Like `plan_estado`, but an expiring or expired plan with the next one already registered
    shows «Renovado»."""
    actual = plan_en(p, d)
    code, txt, cls = plan_estado(actual, d)
    if code in ("por_vencer", "vencido"):
        sig = next((x for x in p.planes if x.activacion > d), None)
        if sig is not None:
            return "renovado", f"Renovado · sigue desde {fmt_dia(sig.activacion)}", "ok"
    return code, txt, cls


def guardar_plan(
    db: Session, p: Plataforma, data: dict[str, Any], *, actor: User
) -> PlataformaPlan:
    """A new plan (renewal), or a correction of the plan with the same activation date."""
    ensure_manage(actor)
    act, venc = data.get("activacion"), data.get("vencimiento")
    if act is None or venc is None or venc < act:
        raise DomainError("Revisa las fechas: el vencimiento no puede ser antes de la activación.")
    if (venc - act).days > 400:
        raise DomainError("Un plan no puede durar más de 13 meses.")
    for k, msg in (
        ("precio", "el precio"),
        ("cupo_total", "el cupo"),
        ("destacados_total", "los destacados"),
    ):
        if data.get(k) is None or data[k] < 0:
            raise DomainError(f"Revisa {msg}.")
    plan = next((x for x in p.planes if x.activacion == act), None)
    nuevo = plan is None
    if nuevo:
        plan = PlataformaPlan(plataforma_id=p.id, activacion=act, creado_por_id=actor.id)
        p.planes.append(plan)
    plan.vencimiento = venc
    plan.precio = int(data["precio"])
    plan.cupo_total = int(data["cupo_total"])
    plan.destacados_total = int(data["destacados_total"])
    plan.alarma_dias = int(data.get("alarma_dias") or 10)
    _evento(
        db,
        p,
        EV.PLAN,
        actor,
        detalle=(
            f"{'Nuevo plan' if nuevo else 'Plan corregido'}: {fmt_cop(plan.precio)} · "
            f"{fmt_dia(act, True)} a {fmt_dia(venc, True)} · cupo {plan.cupo_total} · "
            f"{plan.destacados_total} destacados · alarma {plan.alarma_dias} días antes"
        ),
    )
    db.flush()
    return plan


def asignar_responsable(
    db: Session, p: Plataforma, user_id: uuid.UUID | None, *, actor: User
) -> Plataforma:
    ensure_manage(actor)
    nuevo = None
    if user_id is not None:
        nuevo = db.get(User, user_id)
        if nuevo is None or not nuevo.is_active or nuevo.cargo not in RESPONSABLES:
            raise DomainError("El responsable debe ser de Coordinación o la Auxiliar.")
    antes = p.responsable.full_name if p.responsable else "Sin asignar"
    p.responsable_id = nuevo.id if nuevo else None
    p.responsable = nuevo
    _evento(
        db,
        p,
        EV.RESPONSABLE,
        actor,
        antes=antes,
        despues=nuevo.full_name if nuevo else "Sin asignar",
    )
    db.flush()
    return p


def activar(db: Session, p: Plataforma, activa: bool, *, actor: User) -> Plataforma:
    ensure_manage(actor)
    if p.activa != activa:
        p.activa = activa
        _evento(
            db,
            p,
            EV.ACTIVA,
            actor,
            antes=str(not activa),
            despues=str(activa),
            detalle="Activada" if activa else "Desactivada: ya no se actualiza ni cuenta",
        )
    db.flush()
    return p


# ---------------------------------------------------------------- updates


def ultimas(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, PlataformaActualizacion]:
    out: dict[uuid.UUID, PlataformaActualizacion] = {}
    if not ids:
        return out
    rows = db.scalars(
        select(PlataformaActualizacion)
        .where(PlataformaActualizacion.plataforma_id.in_(ids))
        .order_by(PlataformaActualizacion.realizada_at.desc())
    ).unique()
    for a in rows:
        out.setdefault(a.plataforma_id, a)
    return out


def estado(last: PlataformaActualizacion | None, regla: int, d: date) -> tuple[str, str, str]:
    if last is None:
        return "sin_actualizar", "Sin actualizar", "bad"
    if (d - local_day(last.realizada_at)).days > regla:
        return "atrasada", "Atrasada", "bad"
    return "al_dia", "Al día", "ok"


def hace_txt(last: PlataformaActualizacion | None, d: date) -> str:
    """«Hace 2 días · 1 oct» (K15)."""
    if last is None:
        return "Nunca"
    ld = local_day(last.realizada_at)
    n = (d - ld).days
    rel = "Hoy" if n == 0 else "Ayer" if n == 1 else f"Hace {n} días"
    return f"{rel} · {fmt_dia(ld)}"


def registrar(
    db: Session, p: Plataforma, data: dict[str, Any], *, actor: User, now: datetime | None = None
) -> PlataformaActualizacion:
    now = now or fechas.now()
    if not can_register(actor, p):
        if not p.activa:
            raise ConflictError("Esta plataforma está desactivada.")
        raise PermissionDeniedError(
            "Las actualizaciones las registra Coordinación o el responsable de la plataforma."
        )
    d = fechas.local_date(now)
    plan = plan_en(p, d)
    cupo_total = data.get("cupo_total")
    usado = data.get("cupo_usado")
    dest_usados = data.get("destacados_usados")
    dest_total = data.get("destacados_total")
    if dest_total is None:
        if plan is None:
            raise DomainError("Escribe cuántos destacados tiene el plan.")
        dest_total = plan.destacados_total
    if None in (cupo_total, usado, dest_usados):
        raise DomainError("Completa publicaciones activas, cupo total y destacados usados.")
    if min(cupo_total, usado, dest_usados, dest_total) < 0:
        raise DomainError("Los valores no pueden ser negativos.")
    if usado > cupo_total:
        raise DomainError("Las publicaciones activas no pueden pasar del cupo total del plan.")
    if dest_usados > dest_total:
        raise DomainError(f"El plan tiene {dest_total} destacados: revisa los usados.")
    cfg = get_config(db)
    prev = ultimas(db, [p.id]).get(p.id)
    dias = (d - local_day(prev.realizada_at)).days if prev else None
    a = PlataformaActualizacion(
        plataforma_id=p.id,
        realizada_at=now,
        actualizado_por_id=actor.id,
        responsable_id=p.responsable_id,
        cupo_total=cupo_total,
        cupo_usado=usado,
        destacados_total=dest_total,
        destacados_usados=dest_usados,
        observacion=(data.get("observacion") or "").strip()[:300] or None,
        dias_desde_anterior=dias,
        regla_dias=cfg.dias_regla,
        a_tiempo=dias is None or dias <= cfg.dias_regla,
    )
    a.plataforma, a.actualizado_por, a.responsable = p, actor, p.responsable
    db.add(a)
    # «Cupo total del plan» is asked in the form: keep the plan in step with what the portal shows.
    if plan is not None and plan.vencimiento >= d and plan.cupo_total != cupo_total:
        _evento(
            db,
            p,
            EV.PLAN,
            actor,
            antes=str(plan.cupo_total),
            despues=str(cupo_total),
            detalle=f"Cupo total {plan.cupo_total} → {cupo_total} (desde la actualización)",
        )
        plan.cupo_total = cupo_total
    db.flush()
    return a


@dataclass
class Filtros:
    desde: date
    hasta: date
    plataforma_id: uuid.UUID | None = None
    quien_id: uuid.UUID | None = None


def rango_defecto() -> tuple[date, date]:
    """The last three months: from the 1st two months back to today."""
    d = hoy()
    m = d.month - 2
    y = d.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return date(y, m, 1), d


def actualizaciones(db: Session, user: User, f: Filtros) -> list[PlataformaActualizacion]:
    ensure_view(user)
    if f.desde > f.hasta:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    q = select(PlataformaActualizacion).where(
        PlataformaActualizacion.realizada_at >= fechas.start_of_day(f.desde),
        PlataformaActualizacion.realizada_at < fechas.start_of_day(f.hasta + timedelta(days=1)),
    )
    if f.plataforma_id:
        q = q.where(PlataformaActualizacion.plataforma_id == f.plataforma_id)
    if f.quien_id:
        q = q.where(PlataformaActualizacion.actualizado_por_id == f.quien_id)
    return list(db.scalars(q.order_by(PlataformaActualizacion.realizada_at.desc())).unique())


def kpis_actualizaciones(
    plats: list[Plataforma],
    last: dict[uuid.UUID, PlataformaActualizacion],
    rows: list[PlataformaActualizacion],
    regla: int,
    d: date,
) -> dict[str, Any]:
    """K15-ger: al día hoy, updates in range, % on time, % made by the responsable."""
    atrasadas = [p.nombre for p in plats if estado(last.get(p.id), regla, d)[0] != "al_dia"]
    a_tiempo = sum(1 for a in rows if a.a_tiempo)
    del_resp = sum(1 for a in rows if a.responsable_id and a.actualizado_por_id == a.responsable_id)
    return {
        "al_dia": len(plats) - len(atrasadas),
        "total": len(plats),
        "atrasadas": atrasadas,
        "actualizaciones": len(rows),
        "a_tiempo": a_tiempo,
        "a_tiempo_pct": round(100 * a_tiempo / len(rows)) if rows else None,
        "del_responsable": del_resp,
        "del_responsable_pct": round(100 * del_resp / len(rows)) if rows else None,
    }


# ---------------------------------------------------------------- results of each portal


def _mes(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


def conteos(
    db: Session, fuentes: list[FuenteLead], d1: date, d2: date
) -> dict[tuple, dict[str, int]]:
    """{(fuente, 'YYYY-MM'): {leads, citas, cierres}} for leads that came from each portal."""
    out: dict[tuple, dict[str, int]] = defaultdict(lambda: {"leads": 0, "citas": 0, "cierres": 0})
    if not fuentes:
        return out
    t1, t2 = fechas.start_of_day(d1), fechas.start_of_day(d2 + timedelta(days=1))
    for fuente, at in db.execute(
        select(Lead.fuente, Lead.created_at).where(
            Lead.fuente.in_(fuentes), Lead.created_at >= t1, Lead.created_at < t2
        )
    ):
        out[(fuente, _mes(local_day(at)))]["leads"] += 1
    for fuente, at in db.execute(
        select(Lead.fuente, Cita.scheduled_at)
        .join(Cita, Cita.lead_id == Lead.id)
        .where(
            Lead.fuente.in_(fuentes),
            Cita.scheduled_at >= t1,
            Cita.scheduled_at < t2,
            Cita.estado != EstadoCita.CANCELADA,
        )
    ):
        out[(fuente, _mes(local_day(at)))]["citas"] += 1
    for fuente, at in db.execute(
        select(Lead.fuente, Lead.cerrado_at).where(
            Lead.fuente.in_(fuentes),
            Lead.etapa == EtapaLead.GANADO,
            Lead.cerrado_at >= t1,
            Lead.cerrado_at < t2,
        )
    ):
        out[(fuente, _mes(local_day(at)))]["cierres"] += 1
    return out


def costo(p: Plataforma, d1: date, d2: date, d: date) -> float:
    """Each plan's price spread over its days, for the days of [d1, d2] up to today."""
    fin = min(d2, d)
    total = 0.0
    for plan in p.planes:
        a, b = max(d1, plan.activacion), min(fin, plan.vencimiento)
        if b >= a:
            total += plan.precio * ((b - a).days + 1) / plan.dias
    return total


def meses_de(d1: date, d2: date) -> list[date]:
    out, m = [], d1.replace(day=1)
    while m <= d2 and len(out) < 24:
        out.append(m)
        m = (m.replace(day=28) + timedelta(days=4)).replace(day=1)
    return out


def resultados(
    db: Session, user: User, plats: list[Plataforma], d1: date, d2: date
) -> dict[str, Any]:
    ensure_view(user)
    if d1 > d2:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    d = hoy()
    c = conteos(db, [p.fuente for p in plats], d1, d2)
    filas = []
    for p in plats:
        tot = {"leads": 0, "citas": 0, "cierres": 0}
        for (fuente, _), v in c.items():
            if fuente == p.fuente:
                for k in tot:
                    tot[k] += v[k]
        co = costo(p, d1, d2, d)
        code, txt, cls = estado_plan(p, d)
        filas.append(
            {
                "plataforma": p,
                **tot,
                "costo": round(co),
                "costo_lead": round(co / tot["leads"]) if tot["leads"] else None,
                "costo_cierre": round(co / tot["cierres"]) if tot["cierres"] else None,
                "conversion": round(100 * tot["cierres"] / tot["leads"], 1)
                if tot["leads"]
                else None,
                "plan_estado": code,
                "plan_txt": txt,
                "plan_cls": cls,
            }
        )
    filas.sort(key=lambda r: -r["leads"])
    tl = sum(r["leads"] for r in filas)
    tk = sum(r["cierres"] for r in filas)
    tco = sum(r["costo"] for r in filas)
    barras = [
        {
            "mes": _mes(m),
            "label": MESES[m.month - 1],
            "valores": [
                {"plataforma_id": p.id, "leads": c[(p.fuente, _mes(m))]["leads"]} for p in plats
            ],
        }
        for m in meses_de(d1, d2)
    ]
    return {
        "filas": filas,
        "kpis": {
            "leads": tl,
            "cierres": tk,
            "conversion": round(100 * tk / tl, 1) if tl else None,
            "costo": tco,
            "costo_lead": round(tco / tl) if tl else None,
            "costo_cierre": round(tco / tk) if tk else None,
        },
        "barras": barras,
    }


# ---------------------------------------------------------------- history and download

HIST_COLS = [
    "Fecha y hora",
    "Plataforma",
    "Responsable",
    "Quién actualizó",
    "Cupo total",
    "Cupo utilizado",
    "Cupo disponible",
    "Destacados (total)",
    "Destacados usados",
    "Destacados disponibles",
    "Precio del plan",
    "Activación del plan",
    "Vencimiento",
    "Alarma",
    "Activa",
    "Leads del mes",
    "Citas del mes",
    "Cierres del mes",
    "Costo por lead",
    "Costo por cierre",
    "A tiempo",
    "Observación",
]


def historico(db: Session, rows: list[PlataformaActualizacion]) -> list[list[str]]:
    """K15-ger «Histórico y descarga»: one row per update, with the plan and the month's results."""
    if not rows:
        return []
    d = hoy()
    dias = [local_day(a.realizada_at) for a in rows]
    c = conteos(db, list({a.plataforma.fuente for a in rows}), min(dias).replace(day=1), max(dias))
    out = []
    for a, ad in zip(rows, dias, strict=True):
        p = a.plataforma
        plan = plan_en(p, ad)
        m = c[(p.fuente, _mes(ad))]
        m1 = ad.replace(day=1)
        m2 = ad.replace(day=calendar.monthrange(ad.year, ad.month)[1])
        co = costo(p, m1, m2, d)
        local = a.realizada_at.astimezone(fechas.BOGOTA)
        out.append(
            [
                f"{fmt_dia(ad, True)} {local:%H:%M}",
                p.nombre,
                a.responsable.full_name if a.responsable else "Sin asignar",
                a.actualizado_por.full_name if a.actualizado_por else "—",
                str(a.cupo_total),
                str(a.cupo_usado),
                str(a.cupo_total - a.cupo_usado),
                str(a.destacados_total),
                str(a.destacados_usados),
                str(a.destacados_total - a.destacados_usados),
                fmt_cop(plan.precio) if plan else "—",
                fmt_dia(plan.activacion) if plan else "—",
                fmt_dia(plan.vencimiento) if plan else "—",
                f"{plan.alarma_dias} días antes" if plan else "—",
                "Sí" if plan and plan.activacion <= ad <= plan.vencimiento else "No",
                str(m["leads"]),
                str(m["citas"]),
                str(m["cierres"]),
                fmt_cop(co / m["leads"]) if m["leads"] else "—",
                fmt_cop(co / m["cierres"]) if m["cierres"] else "—",
                "Sí" if a.a_tiempo else "Tarde",
                a.observacion
                or (
                    "—"
                    if a.a_tiempo
                    else f"Se pasó de {a.regla_dias} días ({a.dias_desde_anterior})"
                ),
            ]
        )
    return out


def export_csv(db: Session, user: User, f: Filtros) -> tuple[str, int]:
    if not can_download(user):
        raise PermissionDeniedError("La descarga es de Coordinación y Gerencia.")
    rows = actualizaciones(db, user, f)
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf)
    w.writerow(HIST_COLS)
    w.writerows(historico(db, rows))
    _evento(
        db,
        None,
        EV.DESCARGA,
        user,
        detalle=f"{len(rows)} filas · {f.desde.isoformat()} a {f.hasta.isoformat()}",
    )
    db.flush()
    return buf.getvalue(), len(rows)


def cambios(db: Session, limit: int = 10) -> list[PlataformaEvento]:
    return list(
        db.scalars(
            select(PlataformaEvento).order_by(PlataformaEvento.created_at.desc()).limit(limit)
        ).unique()
    )


# ---------------------------------------------------------------- rendimiento


def cumplimiento(db: Session, user: User, first: date, last: date) -> tuple[int, int, int] | None:
    """(días al día, días contados, plataformas) for the active portals assigned to `user`.

    Each day from the 1st to today (or the end of the month) counts once per portal.
    """
    plats = [p for p in plataformas(db) if p.responsable_id == user.id]
    fin = min(last, hoy())
    if not plats or fin < first:
        return None
    regla = get_config(db).dias_regla
    ok = total = 0
    for p in plats:
        dias = sorted(
            {
                local_day(at)
                for at in db.scalars(
                    select(PlataformaActualizacion.realizada_at).where(
                        PlataformaActualizacion.plataforma_id == p.id,
                        PlataformaActualizacion.realizada_at
                        < fechas.start_of_day(fin + timedelta(days=1)),
                    )
                )
            }
        )
        i, ultima = 0, None
        d = first
        while d <= fin:
            while i < len(dias) and dias[i] <= d:
                ultima = dias[i]
                i += 1
            total += 1
            ok += ultima is not None and (d - ultima).days <= regla
            d += timedelta(days=1)
    return ok, total, len(plats)
