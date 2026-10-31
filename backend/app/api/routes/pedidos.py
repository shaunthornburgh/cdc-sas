import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import Pedido, User
from app.models.enums import TipoNegocio
from app.schemas.pedidos import (
    AtenderIn,
    ComentarioIn,
    ExtenderIn,
    Opciones,
    PedidoCreate,
    PedidoList,
    PedidoRead,
    PedidoUpdate,
    PerdidoIn,
    PropuestaIn,
    ReasignarIn,
)
from app.services import fechas
from app.services import pedidos as service
from app.services.policies import can_use_pedidos

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


def require_pedidos(user: CurrentUser) -> User:
    if not can_use_pedidos(user):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Pedidos es para asesores, Atención y Preventa, Coordinación y Gerencia.",
        )
    return user


Member = Annotated[User, Depends(require_pedidos)]

RANGO_LABELS = {
    "arr_2m": "Arriendo · hasta $2.000.000",
    "arr_2_5m": "Arriendo · $2M a $5M",
    "ven_500m": "Venta · hasta $500M",
    "ven_mas_500m": "Venta · más de $500M",
}


def _read(p: Pedido, user: User, *, eventos: bool = True) -> PedidoRead:
    now = fechas.now()
    out = PedidoRead.model_validate(p).model_copy(
        update={
            "estado_visible": service.estado_visible(p, now),
            "vencido": service.vencido(p, now),
            "proximo_a_vencer": service.proximo_a_vencer(p, now),
            "can_edit": service.can_edit(user, p),
        }
    )
    return out if eventos else out.model_copy(update={"eventos": []})


def _fresh(db, p: Pedido, user: User) -> PedidoRead:
    db.refresh(p)
    return _read(p, user)


@router.get("/opciones", response_model=Opciones)
def opciones(db: DbSession, _: Member) -> dict:
    """Single lists for the tool: zonas, budget ranges, loss reasons, possible responsables."""
    return {
        "zonas": list(service.ZONAS),
        "rangos": RANGO_LABELS,
        "motivos": service.MOTIVO_LABELS,
        "responsables": service.responsables(db),
    }


@router.get("", response_model=PedidoList)
def list_pedidos(
    db: DbSession,
    user: Member,
    vista: Annotated[str, Query(pattern="^(mis|equipo|todos|vencidos)$")] = "mis",
    negocio: TipoNegocio | None = None,
    zona: str | None = None,
    rango: str | None = None,
    proximos: bool = False,
    responsable_id: uuid.UUID | None = None,
    cerrados: bool = False,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> PedidoList:
    rows = service.list_pedidos(
        db,
        user,
        service.PedidoFilters(
            vista=vista,
            negocio=negocio,
            zona=zona,
            rango=rango,
            proximos=proximos,
            responsable_id=responsable_id,
            cerrados=cerrados,
            q=q,
        ),
    )
    return PedidoList(items=[_read(p, user) for p in rows], kpis=service.kpis(db, user))


@router.post("", response_model=PedidoRead, status_code=status.HTTP_201_CREATED)
def create_pedido(body: PedidoCreate, db: DbSession, user: Member) -> PedidoRead:
    """409 if the client already has an open pedido (`otra_necesidad: true` creates anyway)."""
    p = service.create_pedido(
        db,
        body.model_dump(exclude={"responsable_id", "otra_necesidad"}),
        actor=user,
        responsable_id=body.responsable_id,
        otra_necesidad=body.otra_necesidad,
    )
    db.commit()
    return _fresh(db, p, user)


@router.get("/{pedido_id}", response_model=PedidoRead)
def get_pedido(pedido_id: uuid.UUID, db: DbSession, user: Member) -> PedidoRead:
    return _read(service.get_pedido(db, pedido_id), user)


@router.patch("/{pedido_id}", response_model=PedidoRead)
def actualizar(pedido_id: uuid.UUID, body: PedidoUpdate, db: DbSession, user: Member) -> PedidoRead:
    p = service.get_pedido(db, pedido_id)
    service.actualizar(
        db,
        p,
        body.model_dump(exclude_unset=True, exclude={"que_cambio"}),
        que_cambio=body.que_cambio,
        actor=user,
    )
    db.commit()
    return _fresh(db, p, user)


@router.post("/{pedido_id}/extender", response_model=PedidoRead)
def extender(pedido_id: uuid.UUID, body: ExtenderIn, db: DbSession, user: Member) -> PedidoRead:
    p = service.get_pedido(db, pedido_id)
    service.extender(db, p, body.fecha_limite, motivo=body.motivo, actor=user)
    db.commit()
    return _fresh(db, p, user)


@router.post("/{pedido_id}/atendido", response_model=PedidoRead)
def atendido(pedido_id: uuid.UUID, body: AtenderIn, db: DbSession, user: Member) -> PedidoRead:
    p = service.get_pedido(db, pedido_id)
    service.atender(db, p, nota=body.nota, actor=user)
    db.commit()
    return _fresh(db, p, user)


@router.post("/{pedido_id}/perdido", response_model=PedidoRead)
def perdido(pedido_id: uuid.UUID, body: PerdidoIn, db: DbSession, user: Member) -> PedidoRead:
    p = service.get_pedido(db, pedido_id)
    service.marcar_perdido(db, p, motivo=body.motivo, nota=body.nota, actor=user)
    db.commit()
    return _fresh(db, p, user)


@router.post("/{pedido_id}/proponer", response_model=PedidoRead)
def proponer(pedido_id: uuid.UUID, body: PropuestaIn, db: DbSession, user: Member) -> PedidoRead:
    p = service.get_pedido(db, pedido_id)
    service.proponer(db, p, inmueble=body.inmueble, nota=body.nota, actor=user)
    db.commit()
    return _fresh(db, p, user)


@router.post("/{pedido_id}/comentar", response_model=PedidoRead)
def comentar(pedido_id: uuid.UUID, body: ComentarioIn, db: DbSession, user: Member) -> PedidoRead:
    p = service.get_pedido(db, pedido_id)
    service.comentar(db, p, texto=body.texto, actor=user)
    db.commit()
    return _fresh(db, p, user)


@router.post("/{pedido_id}/reasignar", response_model=PedidoRead)
def reasignar(pedido_id: uuid.UUID, body: ReasignarIn, db: DbSession, user: Member) -> PedidoRead:
    p = service.get_pedido(db, pedido_id)
    service.reasignar(db, p, body.responsable_id, actor=user)
    db.commit()
    return _fresh(db, p, user)
