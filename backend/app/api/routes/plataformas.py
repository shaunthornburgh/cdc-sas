import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, Response, status

from app.api.deps import CurrentUser, DbSession
from app.models import Plataforma, PlataformaActualizacion, PlataformaEvento, User
from app.schemas.plataformas import (
    ActivaIn,
    ActualizacionIn,
    ActualizacionRead,
    Evento,
    Historico,
    Opciones,
    PlanIn,
    PlataformaRead,
    ReglaIn,
    ResponsableIn,
    Resultados,
    Tablero,
)
from app.services import plataformas as svc

# K15 «Actualización de plataformas» / K15-ger «Plataformas tradicionales».
router = APIRouter(prefix="/plataformas", tags=["plataformas"])


def _persona(u: User | None) -> dict[str, Any] | None:
    return {"id": u.id, "full_name": u.full_name, "cargo": u.cargo} if u else None


def _plataforma(
    p: Plataforma, last: PlataformaActualizacion | None, regla: int, user: User
) -> dict:
    d = svc.hoy()
    plan = svc.plan_en(p, d)
    pc, pt, pcls = svc.estado_plan(p, d)
    ec, et, ecls = svc.estado(last, regla, d)
    return {
        "id": p.id,
        "fuente": p.fuente,
        "nombre": p.nombre,
        "color": p.color,
        "activa": p.activa,
        "responsable": _persona(p.responsable),
        "plan": plan,
        "plan_estado": pc,
        "plan_txt": pt,
        "plan_cls": pcls,
        "cupo_total": last.cupo_total if last else (plan.cupo_total if plan else None),
        "cupo_usado": last.cupo_usado if last else None,
        "destacados_total": last.destacados_total
        if last
        else (plan.destacados_total if plan else None),
        "destacados_usados": last.destacados_usados if last else None,
        "ultima_at": last.realizada_at if last else None,
        "ultima_txt": svc.hace_txt(last, d),
        "ultima_por": last.actualizado_por.full_name if last and last.actualizado_por else None,
        "estado": ec,
        "estado_txt": et,
        "estado_cls": ecls,
        "puede_registrar": svc.can_register(user, p),
    }


def _act(a: PlataformaActualizacion) -> dict[str, Any]:
    return {
        "id": a.id,
        "plataforma_id": a.plataforma_id,
        "plataforma": a.plataforma.nombre,
        "realizada_at": a.realizada_at,
        "actualizado_por": a.actualizado_por.full_name if a.actualizado_por else None,
        "actualizado_por_id": a.actualizado_por_id,
        "responsable": a.responsable.full_name if a.responsable else None,
        "es_responsable": a.responsable_id is not None and a.responsable_id == a.actualizado_por_id,
        "cupo_total": a.cupo_total,
        "cupo_usado": a.cupo_usado,
        "destacados_total": a.destacados_total,
        "destacados_usados": a.destacados_usados,
        "observacion": a.observacion,
        "dias_desde_anterior": a.dias_desde_anterior,
        "regla_dias": a.regla_dias,
        "a_tiempo": a.a_tiempo,
    }


def _filtros(
    desde: date | None,
    hasta: date | None,
    plataforma_id: uuid.UUID | None,
    quien_id: uuid.UUID | None,
) -> svc.Filtros:
    d1, d2 = svc.rango_defecto()
    return svc.Filtros(desde or d1, hasta or d2, plataforma_id, quien_id)


@router.get("/opciones", response_model=Opciones)
def opciones(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.ensure_view(user)
    d1, d2 = svc.rango_defecto()
    quienes = {
        a.actualizado_por.id: a.actualizado_por
        for a in db.query(PlataformaActualizacion).all()
        if a.actualizado_por
    }
    return {
        "gerencia": svc.can_manage(user),
        "puede_descargar": svc.can_download(user),
        "plataformas": [
            {"id": p.id, "nombre": p.nombre, "activa": p.activa}
            for p in svc.plataformas(db, todas=True)
        ],
        "responsables": [_persona(u) for u in svc.responsables(db)],
        "quienes": [_persona(u) for u in sorted(quienes.values(), key=lambda u: u.full_name)],
        "desde": d1,
        "hasta": d2,
    }


@router.get("", response_model=Tablero)
def tablero(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    plataforma_id: uuid.UUID | None = None,
    quien_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """The portals with their status, plus the updates in the range (filters as K15-ger)."""
    f = _filtros(desde, hasta, plataforma_id, quien_id)
    rows = svc.actualizaciones(db, user, f)
    cfg = svc.get_config(db)
    todas = svc.plataformas(db, todas=svc.can_manage(user))
    plats = [p for p in todas if not plataforma_id or p.id == plataforma_id]
    last = svc.ultimas(db, [p.id for p in todas])
    lista = [_plataforma(p, last.get(p.id), cfg.dias_regla, user) for p in plats]
    activas = [x for x in lista if x["activa"]]
    d = svc.hoy()
    return {
        "plataformas": lista,
        "dias_regla": cfg.dias_regla,
        "regla_confirmada": cfg.confirmada,
        "mes_txt": svc.fechas._MESES[d.month - 1],
        "cupo_disponible": sum(
            (x["cupo_total"] or 0) - (x["cupo_usado"] or 0)
            for x in activas
            if x["cupo_usado"] is not None
        ),
        "destacados_disponibles": sum(
            (x["destacados_total"] or 0) - (x["destacados_usados"] or 0)
            for x in activas
            if x["destacados_usados"] is not None
        ),
        "desde": f.desde,
        "hasta": f.hasta,
        "kpis": svc.kpis_actualizaciones(
            [p for p in plats if p.activa], last, rows, cfg.dias_regla, d
        ),
        "actualizaciones": [_act(a) for a in rows],
    }


@router.get("/resultados", response_model=Resultados)
def resultados(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    plataforma_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    f = _filtros(desde, hasta, plataforma_id, None)
    plats = [p for p in svc.plataformas(db) if not plataforma_id or p.id == plataforma_id]
    r = svc.resultados(db, user, plats, f.desde, f.hasta)
    return {
        "desde": f.desde,
        "hasta": f.hasta,
        "filas": [
            {k: v for k, v in x.items() if k != "plataforma"}
            | {
                "plataforma_id": x["plataforma"].id,
                "nombre": x["plataforma"].nombre,
                "color": x["plataforma"].color,
            }
            for x in r["filas"]
        ],
        "kpis": r["kpis"],
        "barras": r["barras"],
    }


@router.get("/historico", response_model=Historico)
def historico(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    plataforma_id: uuid.UUID | None = None,
    quien_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Preview of the download: the first 5 rows."""
    rows = svc.actualizaciones(db, user, _filtros(desde, hasta, plataforma_id, quien_id))
    return {"columnas": svc.HIST_COLS, "filas": svc.historico(db, rows[:5]), "total": len(rows)}


@router.get("/historico.csv")
def historico_csv(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    plataforma_id: uuid.UUID | None = None,
    quien_id: uuid.UUID | None = None,
) -> Response:
    f = _filtros(desde, hasta, plataforma_id, quien_id)
    content, _ = svc.export_csv(db, user, f)
    db.commit()
    name = f"CDC_Historico_Plataformas_{f.desde.isoformat()}_a_{f.hasta.isoformat()}.csv"
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/cambios", response_model=list[Evento])
def cambios(db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    """Registro de cambios: responsable, plans, rule and downloads."""
    svc.ensure_view(user)
    nombres = {p.id: p.nombre for p in svc.plataformas(db, todas=True)}
    return [_ev(e, nombres) for e in svc.cambios(db)]


def _ev(e: PlataformaEvento, nombres: dict) -> dict[str, Any]:
    return {
        "id": e.id,
        "plataforma": nombres.get(e.plataforma_id),
        "tipo": e.tipo,
        "actor_name": e.actor.full_name if e.actor else None,
        "antes": e.antes,
        "despues": e.despues,
        "detalle": e.detalle,
        "created_at": e.created_at,
    }


@router.put("/regla", response_model=dict)
def regla(body: ReglaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    cfg = svc.guardar_regla(db, body.dias_regla, actor=user)
    db.commit()
    return {"dias_regla": cfg.dias_regla, "regla_confirmada": cfg.confirmada}


def _uno(db: DbSession, user: User, p: Plataforma) -> dict[str, Any]:
    db.commit()
    db.refresh(p)
    cfg = svc.get_config(db)
    return _plataforma(p, svc.ultimas(db, [p.id]).get(p.id), cfg.dias_regla, user)


@router.post(
    "/{id_}/actualizaciones", response_model=ActualizacionRead, status_code=status.HTTP_201_CREATED
)
def registrar(
    id_: uuid.UUID, body: ActualizacionIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    p = svc.get_plataforma(db, user, id_)
    a = svc.registrar(db, p, body.model_dump(), actor=user)
    db.commit()
    db.refresh(a)
    return _act(a)


@router.put("/{id_}/responsable", response_model=PlataformaRead)
def responsable(
    id_: uuid.UUID, body: ResponsableIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    p = svc.get_plataforma(db, user, id_)
    svc.asignar_responsable(db, p, body.responsable_id, actor=user)
    return _uno(db, user, p)


@router.post("/{id_}/planes", response_model=PlataformaRead, status_code=status.HTTP_201_CREATED)
def plan(id_: uuid.UUID, body: PlanIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.get_plataforma(db, user, id_)
    svc.guardar_plan(db, p, body.model_dump(), actor=user)
    return _uno(db, user, p)


@router.put("/{id_}/activa", response_model=PlataformaRead)
def activa(id_: uuid.UUID, body: ActivaIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    p = svc.get_plataforma(db, user, id_)
    svc.activar(db, p, body.activa, actor=user)
    return _uno(db, user, p)
