import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.models import Novedad, Preoperacional, User
from app.models.enums import NOVEDADES_DESCONTABLES, EstadoNovedad, TipoNovedad
from app.schemas.novedades import (
    AnularIn,
    NovedadCreate,
    NovedadCreated,
    NovedadList,
    NovedadRead,
    NovedadUpdate,
    Opciones,
    PreopNovedad,
)
from app.services import novedades as svc
from app.services import preoperacional as preop

# K13 «Ausencias y permisos»: absences and permits of the staff, and preoperacional novedades.
router = APIRouter(prefix="/novedades", tags=["novedades"])


def _emp(u: User) -> dict[str, Any]:
    return {"id": u.id, "full_name": u.full_name, "cargo": u.cargo}


def _read(n: Novedad, user: User) -> dict[str, Any]:
    return {
        "id": n.id,
        "code": n.code,
        "empleado": _emp(n.empleado),
        "tipo": n.tipo,
        "tipo_txt": svc.TIPO_LABELS[n.tipo],
        "descuenta": n.tipo in NOVEDADES_DESCONTABLES,
        "desde": n.desde,
        "hasta": n.hasta,
        "fechas_txt": svc.fmt_rango(n.desde, n.hasta),
        "dias": n.dias,
        "observacion": n.observacion,
        "soportes": n.soportes,
        "estado": n.estado,
        "estado_txt": svc.ESTADO_LABELS[n.estado],
        "registrada_por_name": n.registrada_por.full_name if n.registrada_por else None,
        "created_at": n.created_at,
        "anulada_por_name": n.anulada_por.full_name if n.anulada_por else None,
        "anulada_at": n.anulada_at,
        "motivo_anulacion": n.motivo_anulacion,
        "puede_editar": svc.can_register(user) and n.estado == EstadoNovedad.REGISTRADA,
    }


def _rango(desde: date | None, hasta: date | None) -> tuple[date, date]:
    d1, d2 = svc.mes_actual()
    return desde or d1, hasta or d2


@router.get("/opciones", response_model=Opciones)
def opciones(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    svc.ensure_view(user)
    d1, d2 = svc.mes_actual()
    return {
        "tipos": {k.value: v for k, v in svc.TIPO_LABELS.items()},
        "ayudas": {k.value: v for k, v in svc.TIPO_AYUDA.items()},
        "descontables": [t.value for t in NOVEDADES_DESCONTABLES],
        "empleados": [_emp(u) for u in svc.empleados(db)] if svc.can_register(user) else [],
        "puede_registrar": svc.can_register(user),
        "desde": d1,
        "hasta": d2,
    }


@router.get("", response_model=NovedadList)
def listar(
    db: DbSession,
    user: CurrentUser,
    desde: date | None = None,
    hasta: date | None = None,
    tipo: TipoNovedad | None = None,
    empleado_id: uuid.UUID | None = None,
    anuladas: bool = False,
) -> dict[str, Any]:
    d1, d2 = _rango(desde, hasta)
    rows = svc.listar(
        db,
        user,
        svc.Filtros(desde=d1, hasta=d2, tipo=tipo, empleado_id=empleado_id, anuladas=anuladas),
    )
    return {
        "items": [_read(n, user) for n in rows],
        "desde": d1,
        "hasta": d2,
        "dias": svc.resumen(rows, d1, d2),
        "preop_sin_revisar": svc.sin_revisar(db, user, d1, d2),
    }


@router.post("", response_model=NovedadCreated, status_code=status.HTTP_201_CREATED)
def crear(body: NovedadCreate, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    n, avisos = svc.crear(db, body.model_dump(), actor=user)
    db.commit()
    db.refresh(n)
    return {"novedad": _read(n, user), "avisos": avisos}


@router.get("/preoperacional", response_model=list[PreopNovedad])
def del_preoperacional(
    db: DbSession, user: CurrentUser, desde: date | None = None, hasta: date | None = None
) -> list[dict[str, Any]]:
    """K13 «Del preoperacional»: reviewed with POST /preoperacional/{id}/revisar."""
    d1, d2 = _rango(desde, hasta)
    out = []
    for p in svc.preoperacionales(db, user, d1, d2):
        medio = preop.MEDIO_LABELS[p.medio] + (f" · {p.placa}" if p.placa else "")
        out.append(_preop(p, user, medio))
    return out


def _preop(p: Preoperacional, user: User, medio: str) -> dict[str, Any]:
    return {
        "id": p.id,
        "empleado": _emp(p.user),
        "fecha": p.fecha,
        "realizado_at": p.realizado_at,
        "medio": medio,
        "texto": svc.texto_preop(p),
        "revisado": p.revisado_at is not None,
        "revisado_por_name": p.revisado_por_name,
        "revisado_at": p.revisado_at,
        "revision_nota": p.revision_nota,
        "puede_revisar": svc.puede_revisar(user, p),
    }


@router.get("/{id_}", response_model=NovedadRead)
def detalle(id_: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    return _read(svc.get_novedad(db, user, id_), user)


@router.patch("/{id_}", response_model=NovedadRead)
def actualizar(
    id_: uuid.UUID, body: NovedadUpdate, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    n = svc.get_novedad(db, user, id_)
    svc.actualizar(db, n, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    db.refresh(n)
    return _read(n, user)


@router.post("/{id_}/anular", response_model=NovedadCreated)
def anular(id_: uuid.UUID, body: AnularIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    n = svc.get_novedad(db, user, id_)
    n, avisos = svc.anular(db, n, body.motivo, actor=user)
    db.commit()
    db.refresh(n)
    return {"novedad": _read(n, user), "avisos": avisos}
