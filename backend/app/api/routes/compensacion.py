import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Cierre, LiquidacionSalario, Pago, SalarioConfig, User
from app.models.enums import Cargo
from app.schemas.compensacion import (
    AccionIn,
    CalculoOut,
    CierreRead,
    ConfigIn,
    Evento,
    GananciaIn,
    ItemRead,
    ManualIn,
    Mio,
    PagoRead,
    SalarioAccionIn,
    SalarioIn,
    Salarios,
    Tablero,
)
from app.services import compensacion as service
from app.services import rendimiento as rend
from app.services.errors import NotFoundError

# Everyone sees their own; the Auxiliar (visto bueno) and Gerencia (approve, pay) see everything.
router = APIRouter(prefix="/compensacion", tags=["compensacion"])
Mes = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$")]


def _p(u: User | None) -> dict[str, Any] | None:
    return {"id": u.id, "full_name": u.full_name} if u else None


def _item(clase: str, it, cfg) -> dict[str, Any]:
    return {
        "id": it.id,
        "clase": clase,
        "tipo": it.tipo.value,
        "beneficiario": _p(it.beneficiario),
        "concepto": it.concepto,
        "detalle": it.detalle,
        "fecha": it.fecha,
        "periodo": it.periodo,
        "valor": it.valor,
        "base": getattr(it, "base", None),
        "porcentaje": getattr(it, "porcentaje", None),
        "cierre_code": it.cierre.code if getattr(it, "cierre", None) else None,
        "estado": it.estado.value,
        "estado_txt": service.ESTADO_LABELS[clase][it.estado],
        "se_paga": service.se_paga(it, cfg),
    }


def _pago(p: Pago) -> dict[str, Any]:
    return {
        "id": p.id,
        "beneficiario": _p(p.beneficiario),
        "tipo": p.tipo.value,
        "concepto": p.concepto,
        "valor": p.valor,
        "fecha_programada": p.fecha_programada,
        "estado": p.estado.value,
        "estado_txt": service.PAGO_LABELS[p.estado],
        "pagado_at": p.pagado_at,
    }


def _cierre(c: Cierre) -> dict[str, Any]:
    return {
        "id": c.id,
        "code": c.code,
        "lead_code": c.lead.code,
        "cliente": c.lead.full_name,
        "negocio": c.negocio.value if c.negocio else None,
        "cerrado_at": c.cerrado_at,
        "estado": c.estado.value,
        "ganancia": c.ganancia,
        "cerrador": _p(c.cerrador),
        "filtro": _p(c.filtro),
        "captador": _p(c.captador),
    }


@router.get("/mio", response_model=Mio)
def mio(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """«Mis pagos y bonos» · «Mis comisiones» · «Mis bonos» · «Pagos» (read-only)."""
    data = service.mio(db, user)
    db.commit()  # salary periods created on first look
    return data


@router.get("", response_model=Tablero)
def tablero(db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """G05: commissions, bonuses, payments and closed deals (Auxiliar and Gerencia)."""
    cfg = service.get_config(db)
    cierres = service.cierres(db, user)
    data = {
        "comisiones": [_item("comision", c, cfg) for c in service.comisiones(db, user)],
        "bonos": [_item("bono", b, cfg) for b in service.bonos(db, user)],
        "pagos": [_pago(p) for p in service.pagos(db, user)],
        "cierres": [_cierre(c) for c in cierres],
        "totales": service.resumen(db, user),
        "config": cfg,
        "config_labels": service.CONFIG_LABELS,
        "personas": [
            _p(u)
            for u in db.scalars(
                select(User)
                .where(User.is_active, User.cargo != Cargo.GERENCIA)
                .order_by(User.full_name)
            ).unique()
        ],
        "captadores": [
            _p(u)
            for u in db.scalars(
                select(User).where(User.is_active).order_by(User.full_name)
            ).unique()
            if rend.perfil(u) == "asesor"
        ],
        "es_gerencia": service.is_gerencia(user),
        "es_auxiliar": service.is_auxiliar(user),
    }
    db.commit()  # closed deals synced from «Ganado» leads
    return data


@router.get("/export.csv")
def export_csv(
    db: DbSession,
    user: CurrentUser,
    tab: Annotated[str, Query(pattern="^(comisiones|bonos|pagos)$")] = "comisiones",
) -> Response:
    return Response(
        content=service.export_csv(db, user, tab),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{tab}.csv"'},
    )


@router.post("/calcular", response_model=CalculoOut)
def calcular(
    db: DbSession, user: CurrentUser, periodo: Annotated[str, Query(pattern=r"^\d{4}-\d{2}$")]
) -> dict[str, int]:
    """Month-end: performance bonuses and the Coordinador's group commission."""
    out = service.calcular_mes(db, periodo, actor=user)
    db.commit()
    return out


@router.put("/config", response_model=dict[str, Any])
def config(body: ConfigIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    out = service.set_config(db, body.valores, actor=user)
    db.commit()
    return out


@router.post("/{clase}", response_model=ItemRead, status_code=201)
def crear(clase: str, body: ManualIn, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    """«+ Registrar comisión / bono» (manual)."""
    clase = _clase(clase)
    it = service.crear_manual(db, clase, body.model_dump(), actor=user)
    db.commit()
    return _item(clase, it, service.get_config(db))


@router.post("/{clase}/{item_id}/accion", response_model=ItemRead)
def accion(
    clase: str, item_id: uuid.UUID, body: AccionIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    clase = _clase(clase)
    service.ensure_manage(user)
    it = service.get_item(db, clase, item_id)
    service.accion(db, clase, it, body.accion, actor=user, valor=body.valor, motivo=body.motivo)
    db.commit()
    return _item(clase, it, service.get_config(db))


@router.post("/pagos/{pago_id}/pagar", response_model=PagoRead)
def pagar(pago_id: uuid.UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    service.ensure_manage(user)
    pago = db.get(Pago, pago_id)
    if pago is None:
        raise NotFoundError("Ese pago no existe.")
    service.registrar_pago(db, pago, actor=user)
    db.commit()
    return _pago(pago)


@router.put("/cierres/{cierre_id}", response_model=CierreRead)
def ganancia(
    cierre_id: uuid.UUID, body: GananciaIn, db: DbSession, user: CurrentUser
) -> dict[str, Any]:
    """Enter the deal's ganancia efectiva (and captador) → its commissions are generated."""
    service.ensure_manage(user)
    c = db.get(Cierre, cierre_id)
    if c is None:
        raise NotFoundError("Ese negocio no existe.")
    service.registrar_ganancia(
        db, c, ganancia=body.ganancia, captador_id=body.captador_id, actor=user
    )
    db.commit()
    return _cierre(c)


@router.get("/historial/{entidad}/{entidad_id}", response_model=list[Evento])
def historial(
    entidad: str, entidad_id: str, db: DbSession, user: CurrentUser
) -> list[dict[str, Any]]:
    return [
        {
            "accion": e.accion,
            "antes": e.antes,
            "despues": e.despues,
            "created_by_name": e.created_by.full_name if e.created_by else None,
            "created_at": e.created_at,
        }
        for e in service.historial(db, user, entidad, entidad_id)
    ]


# ---------------------------------------------------------------- salaries (X04)


@router.get("/salarios", response_model=Salarios)
def salarios(
    db: DbSession, user: CurrentUser, periodo: Mes = None, corte: int = 1
) -> dict[str, Any]:
    p = rend.periodo(periodo)
    liqs = service.liquidaciones(db, user, p.first, corte)
    cfg = service.get_config(db)
    con = {x.user_id for x in liqs}
    data = {
        "periodo": p.key,
        "label": p.label,
        "corte": corte,
        "fecha_pago": service.corte_fecha(p.first, corte, cfg),
        "filas": [
            {
                "id": x.id,
                "user": _p(x.user),
                "cargo_txt": rend.cargo_txt(x.user)
                if rend.perfil(x.user)
                else _CARGO.get(x.user.cargo, x.user.cargo.value),
                "salario_mensual": db.get(SalarioConfig, x.user_id).salario_mensual,
                "salario_corte": x.salario_corte,
                "descuento": x.descuento,
                "a_pagar": x.a_pagar,
                "novedades": x.novedades or "Ninguna",
                "estado": x.estado.value,
                "estado_txt": service.SALARIO_LABELS[x.estado],
            }
            for x in liqs
        ],
        "sin_salario": [
            _p(u)
            for u in db.scalars(
                select(User)
                .where(User.is_active, User.cargo != Cargo.GERENCIA)
                .order_by(User.full_name)
            ).unique()
            if u.id not in con
        ],
        "es_gerencia": service.is_gerencia(user),
        "es_auxiliar": service.is_auxiliar(user),
    }
    db.commit()
    return data


_CARGO = {Cargo.AUXILIAR_ADMINISTRATIVA: "Auxiliar administrativa", Cargo.GERENCIA: "Gerencia"}


@router.post("/salarios/accion", response_model=dict[str, int])
def accion_salarios(body: SalarioAccionIn, db: DbSession, user: CurrentUser) -> dict[str, int]:
    """«Confirmar a pagar» (Auxiliar) / «Aprobar y pagar» (Gerencia), one or many."""
    service.ensure_manage(user)
    n = 0
    for liq_id in body.ids:
        liq = db.get(LiquidacionSalario, liq_id)
        if liq is None:
            raise NotFoundError("Esa liquidación no existe.")
        service.accion_salario(db, liq, body.accion, actor=user)
        n += 1
    db.commit()
    return {"actualizados": n}


@router.put("/salarios/config/{user_id}", response_model=dict[str, int])
def salario(
    user_id: uuid.UUID, body: SalarioIn, db: DbSession, user: CurrentUser
) -> dict[str, int]:
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("Esa persona no existe.")
    row = service.set_salario(db, target, body.salario_mensual, actor=user)
    db.commit()
    return {"salario_mensual": row.salario_mensual}


def _clase(c: str) -> str:
    m = {"comisiones": "comision", "bonos": "bono"}
    if c not in m:
        raise NotFoundError("No existe.")
    return m[c]
