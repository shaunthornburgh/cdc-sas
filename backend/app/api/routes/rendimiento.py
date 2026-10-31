import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.models import User
from app.schemas.rendimiento import (
    CalificacionesIn,
    CambioRead,
    ConfigRead,
    Empresa,
    Equipo,
    MetasIn,
    PesosIn,
    ResultadoRead,
)
from app.services import rendimiento as service
from app.services.errors import PermissionDeniedError

# Everyone with a result sees their own; Coordinación sees asesores and Atención; Gerencia
# (and the Auxiliar, to consult and rate the Coordinador) see everyone.
router = APIRouter(prefix="/rendimiento", tags=["rendimiento"])
Mes = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")]


def _periodo(p: service.Periodo) -> dict[str, Any]:
    return {"key": p.key, "label": p.label, "en_curso": p.en_curso}


def _resultado(db, viewer: User, target: User, mes: str | None, detalle: bool) -> dict[str, Any]:
    p = service.periodo(mes)
    r = service.Calculo(db, p).resultado(target)
    ant = service.Calculo(db, p.anterior()).resultado(target)
    return {
        "user": target,
        "perfil": service.perfil(target),
        "cargo_txt": service.cargo_txt(target),
        "periodo": _periodo(p),
        "total": r.total,
        "total_exacto": r.total_exacto,
        "semaforo": service.semaforo(r.total),
        "por_areas": r.por_areas,
        "peso_con_datos": r.peso_con_datos,
        "puntos_ajuste": r.puntos_ajuste,
        "puntos_descuento": r.puntos_descuento,
        "anterior": ant.total,
        "areas": [
            {**a.__dict__, "cumple": a.cumple, "semaforo": service.semaforo(a.cumplimiento)}
            for a in r.areas
        ],
        "calificaciones": r.calificaciones,
        "descuentos": r.descuentos,
        "ajustes": r.ajustes,
        "avisos": r.avisos,
        "mejoras": service.mejoras(r, ant),
        "puede": {
            "calificar": p.en_curso and service.can_rate(viewer, target),
            "configurar": service.can_configure(viewer, target),
        },
        "detalle": service.detalle_equipo(db, r) if detalle else None,
    }


@router.get("/mio", response_model=ResultadoRead)
def mio(db: DbSession, user: CurrentUser, periodo: Mes = None) -> dict[str, Any]:
    """«Mis resultados» (M08 · C04 · K14)."""
    if service.perfil(user) is None:
        raise PermissionDeniedError("Tu cargo todavía no tiene indicadores de rendimiento.")
    return _resultado(db, user, user, periodo, detalle=False)


@router.get("/equipo", response_model=Equipo)
def equipo(db: DbSession, user: CurrentUser, periodo: Mes = None) -> dict[str, Any]:
    """«Mi equipo» (Coordinación) / «Rendimiento por empleado» (Gerencia) · K18."""
    data = service.equipo(db, user, service.periodo(periodo))
    return {**data, "periodo": _periodo(data["periodo"])}


@router.get("/equipo.csv")
def equipo_csv(db: DbSession, user: CurrentUser, periodo: Mes = None) -> Response:
    p = service.periodo(periodo)
    return Response(
        content=service.export_csv(db, user, p),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="rendimiento-{p.key}.csv"'},
    )


@router.get("/empresa", response_model=Empresa)
def empresa(db: DbSession, user: CurrentUser, periodo: Mes = None) -> dict[str, Any]:
    """«Rendimiento de la empresa» (G12, Gerencia)."""
    data = service.empresa(db, user, service.periodo(periodo))
    return {**data, "periodo": _periodo(data["periodo"])}


@router.get("/personas/{user_id}", response_model=ResultadoRead)
def persona(
    user_id: uuid.UUID, db: DbSession, user: CurrentUser, periodo: Mes = None
) -> dict[str, Any]:
    target = service.get_target(db, user, user_id)
    return _resultado(db, user, target, periodo, detalle=True)


def _config(db, viewer: User, target: User) -> dict[str, Any]:
    p = service.periodo()
    cur = service.config_de(db, target, p.first)
    nxt_first = p.siguiente_first()
    nxt = service.config_de(db, target, nxt_first)
    keys = service.area_keys(target)
    return {
        "user": target,
        "perfil": service.perfil(target),
        "cargo_txt": service.cargo_txt(target),
        "areas": [
            {
                "key": k,
                "titulo": service.AREAS[k].titulo,
                "descripcion": service.AREAS[k].descripcion,
                "tiene_meta": service.AREAS[k].meta_default is not None,
                "unidad": service.AREAS[k].unidad[1],
            }
            for k in keys
        ],
        "pesos": cur.pesos,
        "pesos_configurados": cur.pesos_configurados,
        "metas": cur.metas,
        "metas_siguiente": nxt.metas,
        "siguiente": f"{service.MESES[nxt_first.month - 1]} {nxt_first.year}",
        "puede_configurar": service.can_configure(viewer, target),
    }


@router.get("/config/{user_id}", response_model=ConfigRead)
def config(user_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """Weights and goals of one person (K07 «Rendimiento e indicadores»)."""
    return _config(db, user, service.get_target(db, user, user_id))


@router.put("/config/{user_id}/pesos", response_model=ConfigRead)
def guardar_pesos(
    user_id: uuid.UUID, body: PesosIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    target = service.get_target(db, user, user_id)
    service.guardar_pesos(db, target, body.pesos, actor=user)
    db.commit()
    return _config(db, user, target)


@router.put("/config/{user_id}/metas", response_model=ConfigRead)
def guardar_metas(
    user_id: uuid.UUID, body: MetasIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    target = service.get_target(db, user, user_id)
    service.guardar_metas(db, target, body.metas, actor=user)
    db.commit()
    return _config(db, user, target)


@router.put("/calificaciones/{user_id}", response_model=ResultadoRead)
def calificar(
    user_id: uuid.UUID, body: CalificacionesIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    target = service.get_target(db, user, user_id)
    service.guardar_calificaciones(db, target, body.valores, actor=user)
    db.commit()
    return _resultado(db, user, target, None, detalle=True)


@router.get("/cambios/{user_id}", response_model=list[CambioRead])
def cambios(user_id: uuid.UUID, db: DbSession, user: CurrentUser) -> list[dict[str, Any]]:
    """«Registro de cambios» of weights, goals and ratings (who, when, before and after)."""
    target = service.get_target(db, user, user_id)
    if not (service.can_configure(user, target) or service.can_rate(user, target)):
        if user.id != target.id:
            raise PermissionDeniedError("No puedes ver el registro de cambios de esta persona.")
    return [
        {
            **{k: getattr(c, k) for k in ("tipo", "periodo", "antes", "despues", "created_at")},
            "created_by_name": c.created_by.full_name if c.created_by else None,
        }
        for c in service.cambios(db, target)
    ]
