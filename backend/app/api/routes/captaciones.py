import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.api.deps import CurrentUser, DbSession
from app.api.permissions import USER_MANAGERS, require_cargo
from app.models import Captacion, User
from app.models.enums import EstadoCaptacion, TipoNegocio
from app.schemas.captaciones import (
    CaptacionCreate,
    CaptacionList,
    CaptacionRead,
    CaptacionUpdate,
    ReasignarIn,
    ReenviarIn,
    VerificarIn,
)
from app.schemas.leads import UserRef
from app.services import captaciones as service
from app.services.policies import can_use_captaciones

router = APIRouter(prefix="/captaciones", tags=["captaciones"])


def require_captaciones_module(user: CurrentUser) -> User:
    """People with the Captación activity, plus Coordinación and Gerencia."""
    if not can_use_captaciones(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Este módulo es para quien tiene Captación activa."
        )
    return user


Captador = Annotated[User, Depends(require_captaciones_module)]
Manager = Annotated[User, Depends(require_cargo(*USER_MANAGERS))]


def _read(cap: Captacion, user: User) -> CaptacionRead:
    return CaptacionRead.model_validate(cap).model_copy(
        update={"can_edit": service.can_edit(user, cap)}
    )


def _fresh(db, cap: Captacion, user: User) -> CaptacionRead:
    db.refresh(cap)
    return _read(cap, user)


@router.get("", response_model=CaptacionList)
def list_captaciones(
    db: DbSession,
    user: Captador,
    estado: Annotated[list[EstadoCaptacion] | None, Query()] = None,
    asesor_id: uuid.UUID | None = None,
    negocio: TipoNegocio | None = None,
    publicada: bool | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> CaptacionList:
    """Captadores get their own; managers get everyone's. `counts` ignores the estado filter."""
    rows, counts = service.list_captaciones(
        db,
        user,
        service.CaptacionFilters(
            estados=tuple(estado or ()),
            asesor_id=asesor_id,
            negocio=negocio,
            publicada=publicada,
            desde=desde,
            hasta=hasta,
            q=q,
        ),
    )
    return CaptacionList(
        items=[_read(c, user) for c in rows],
        counts=counts,
        aprobacion_pct=service.aprobacion_pct(counts),
    )


@router.get("/captadores", response_model=list[UserRef])
def captadores(db: DbSession, _: Manager) -> list[User]:
    """Who a captación can belong to (active people with Captación)."""
    return service.captadores(db)


@router.post("", response_model=CaptacionRead, status_code=status.HTTP_201_CREATED)
def create_captacion(body: CaptacionCreate, db: DbSession, user: Captador) -> CaptacionRead:
    cap = service.create_captacion(
        db,
        body.model_dump(exclude={"asesor_id", "gps"}),
        actor=user,
        asesor_id=body.asesor_id,
        gps=body.gps.model_dump() if body.gps else None,
    )
    db.commit()
    return _fresh(db, cap, user)


@router.get("/{captacion_id}", response_model=CaptacionRead)
def get_captacion(captacion_id: uuid.UUID, db: DbSession, user: Captador) -> CaptacionRead:
    return _read(service.get_captacion(db, user, captacion_id), user)


@router.patch("/{captacion_id}", response_model=CaptacionRead)
def update_captacion(
    captacion_id: uuid.UUID, body: CaptacionUpdate, db: DbSession, user: Captador
) -> CaptacionRead:
    cap = service.get_captacion(db, user, captacion_id)
    service.update_captacion(db, cap, body.model_dump(exclude_unset=True), actor=user)
    db.commit()
    return _fresh(db, cap, user)


@router.delete("/{captacion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_captacion(captacion_id: uuid.UUID, db: DbSession, user: Captador) -> Response:
    service.delete_captacion(db, service.get_captacion(db, user, captacion_id), actor=user)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{captacion_id}/status", response_model=CaptacionRead)
def verificar(
    captacion_id: uuid.UUID, body: VerificarIn, db: DbSession, user: Captador
) -> CaptacionRead:
    """Approve or reject (Coordinación / Gerencia). Rejecting needs a reason."""
    cap = service.get_captacion(db, user, captacion_id)
    service.verificar(
        db, cap, body.estado, motivo=body.motivo, observacion=body.observacion, actor=user
    )
    db.commit()
    return _fresh(db, cap, user)


@router.post("/{captacion_id}/resubmit", response_model=CaptacionRead)
def reenviar(
    captacion_id: uuid.UUID, body: ReenviarIn, db: DbSession, user: Captador
) -> CaptacionRead:
    """«Corregir y volver a enviar» a rejected captación (code or address must change)."""
    cap = service.get_captacion(db, user, captacion_id)
    service.reenviar(
        db, cap, codigo_inmueble=body.codigo_inmueble, direccion=body.direccion, actor=user
    )
    db.commit()
    return _fresh(db, cap, user)


@router.post("/{captacion_id}/publish", response_model=CaptacionRead)
def publicar(captacion_id: uuid.UUID, db: DbSession, user: Captador) -> CaptacionRead:
    cap = service.get_captacion(db, user, captacion_id)
    service.publicar(db, cap, actor=user)
    db.commit()
    return _fresh(db, cap, user)


@router.post("/{captacion_id}/reassign", response_model=CaptacionRead)
def reasignar(
    captacion_id: uuid.UUID, body: ReasignarIn, db: DbSession, user: Captador
) -> CaptacionRead:
    cap = service.get_captacion(db, user, captacion_id)
    service.reasignar(db, cap, body.asesor_id, actor=user)
    db.commit()
    return _fresh(db, cap, user)
