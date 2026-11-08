"""Negocios (prototypes X02 «Negocios» and M16 «Detalle del negocio»; decisions G-029, G-030,
G-031, G-033, G-034, G-055, G-059, G-060, G-087 and G-091).

* **The record**: a negocio is the `Cierre` (NEG-0140…) that Compensación already creates for each
  lead marked «Ganado». This module adds the deal's data (property, canon or price, last offer,
  documents, contract) and its signature flow; it doesn't create deals of its own.
* **Stages** (example ones, PENDIENTE DE CONFIGURACIÓN): arriendo «Estudio del arrendatario» →
  «Contrato en firma» → «Contrato firmado»; venta «Oferta presentada» → «Promesa firmada» →
  «Escrituración» (with the notary appointment, G-031) → «Escriturada». The asesor moves the deal
  forward («Pasar etapa», with the offer or negotiated condition, G-059); the last stage is only
  reached when the Auxiliar confirms the signature.
* **Signatures** (G-029, G-033, G-034): the asesor «Solicitar cierre» when the client signed. The
  Auxiliar administrativa confirms it (date, optional contract) or returns it with a reason.
  Rentals have one signature (the contract). Sales have two: the promesa de compraventa and the
  escritura; the escritura gives «negocio cerrado». Confirming the closing signature registers the
  ganancia efectiva in Compensación, which generates the commissions (G-029: only then). For a
  rental with an approved policy, it also records the contract signature in «Pólizas», which
  starts the insurer's deadline to activate it.
* **Negocio caído** (G-055, G-060): the asesor reports it with a reason; the Auxiliar confirms it
  (or confirms one directly). It leaves «En proceso», its unpaid commissions are cancelled and it
  no longer counts in Rendimiento. «Póliza negada» is a reason only for rentals.
* **Ganancia** (G-087): from Gerencia's «Tarifas de intermediación» (Configuración).
  Arriendo: charged once = canon × % + IVA + papelería (IVA included). Minus the IVA collected,
  the team's commissions, one month of the policy (the company pays it; months PENDIENTE) and the
  referral payment (% of the canon). Venta: % of the price (per deal, default from Configuración)
  + IVA, minus the IVA and the commissions. The *ganancia efectiva* Compensación uses as the base
  for commissions is the charge without IVA, minus referrals. Until commissions exist, they're
  estimated with Compensación's percentages. A deal that loses money shows a red alert.
* **Who**: the Auxiliar manages everything. Gerencia sees everything and can edit the deal's data
  (value, % of the sale, documents) but doesn't confirm signatures (that's the Auxiliar's, G-029).
  Coordinación sees its team's deals read-only and without money. Asesores see and move their own
  deals (the ones they close). Everyone else gets 403.
* Every change is a `CompensacionEvento` (entidad «cierre»), shown in the deal's history and in
  «Registro de cambios».
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cierre, Comision, CompensacionEvento, Inmueble, NegocioAbono, Poliza, User
from app.models.enums import (
    Cargo,
    EstadoCierre,
    EstadoCompensacion,
    TipoNegocio,
)
from app.services import compensacion as comp
from app.services import configuracion, fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError
from app.services.leads import FUENTE_LABELS
from app.services.policies import has_commercial_activity

E = EstadoCompensacion
MOTIVOS_CAIDA = [
    "El cliente desistió",
    "Póliza negada",  # rentals only (G-060)
    "Problema con los documentos",
    "El propietario retiró el inmueble",
    "Otro",
]
MOTIVOS_DEVOLVER = [
    "El cliente aún no ha firmado",
    "Falta un documento",
    "La póliza no está aprobada",
    "Otro",
]
MOMENTOS = {"promesa": "En la promesa", "escritura": "En la escritura", "otro": "Otro abono"}
SITUACION = {
    "en_proceso": ("En proceso", "info"),
    "por_confirmar": ("Cierre solicitado", "warn"),
    "cerrado": ("✓ Negocio cerrado", "ok"),
    "caido": ("✕ Negocio caído", "bad"),
}
CATEGORIA = {
    "neg": ("En negociación", "info"),
    "pc": ("Por cerrar", "warn"),
    "cer": ("Cerrado", "ok"),
    "cai": ("Caído", "bad"),
}
POLIZA_TXT = {
    "en_estudio": ("En estudio", "warn"),
    "aprobada": ("Aprobada", "ok"),
    "negada": ("Negada", "bad"),
    "activa": ("Activa", "ok"),
    "terminada": ("Terminada", "gray"),
}
MESES_POLIZA = 1  # months of the policy the company pays · PENDIENTE DE CONFIGURACIÓN


def hoy() -> date:
    return fechas.local_date(fechas.now())


def _cop(v: float | int | None) -> str:
    return "—" if v is None else ("−$" if v < 0 else "$") + f"{abs(round(v)):,}".replace(",", ".")


def _pct(v: float | Decimal) -> str:
    f = float(v)
    return (str(int(f)) if f == int(f) else f"{f:g}").replace(".", ",") + " %"


def _fd(d: date | None) -> str:
    return "—" if d is None else f"{d.day} {fechas._MESES[d.month - 1]} {d.year}"


# ---------------------------------------------------------------- access


def modo(user: User) -> str | None:
    """auxiliar · gerencia · coordinacion · asesor, or None (no access)."""
    if not user.is_active:
        return None
    if user.cargo == Cargo.AUXILIAR_ADMINISTRATIVA:
        return "auxiliar"
    if user.cargo == Cargo.GERENCIA:
        return "gerencia"
    if user.cargo == Cargo.COORDINACION:
        return "coordinacion"
    if has_commercial_activity(user):
        return "asesor"
    return None


def ensure_ver(user: User) -> str:
    m = modo(user)
    if m is None:
        raise PermissionDeniedError(
            "Los negocios los ven la Auxiliar administrativa, Gerencia, Coordinación y los "
            "asesores que los cierran."
        )
    return m


def ve_dinero(m: str) -> bool:
    return m in ("auxiliar", "gerencia")


def _ensure_aux(user: User, que: str) -> None:
    if modo(user) != "auxiliar":
        raise PermissionDeniedError(f"{que} lo hace la Auxiliar administrativa.")


def _ensure_datos(user: User) -> None:
    if modo(user) not in ("auxiliar", "gerencia"):
        raise PermissionDeniedError(
            "Los datos del negocio los editan la Auxiliar administrativa y Gerencia."
        )


def _es_suyo(c: Cierre, user: User) -> bool:
    return c.cerrador_id == user.id


def get(db: Session, user: User, id_: uuid.UUID) -> Cierre:
    m = ensure_ver(user)
    c = db.get(Cierre, id_)
    if c is None or (m == "asesor" and not _es_suyo(c, user)):
        raise NotFoundError("Ese negocio no existe.")
    return c


# ---------------------------------------------------------------- state


def situacion(c: Cierre) -> str:
    if c.estado == EstadoCierre.CAIDO:
        return "caido"
    if c.firma_fecha is not None:
        return "cerrado"
    if c.solicitud:
        return "por_confirmar"
    return "en_proceso"


def categoria(c: Cierre) -> str:
    """G-091: «En negociación» = no signature yet; «Por cerrar» = signature to confirm or promesa
    signed; «Cerrado»; «Caído»."""
    s = situacion(c)
    if s == "caido":
        return "cai"
    if s == "cerrado":
        return "cer"
    if c.solicitud or c.promesa_fecha:
        return "pc"
    return "neg"


def fecha_ref(c: Cierre) -> date:
    """Closing date for closed deals, start date (lead ganado) for the rest."""
    return c.firma_fecha or fechas.local_date(c.cerrado_at)


def _abierto(c: Cierre) -> bool:
    return situacion(c) in ("en_proceso", "por_confirmar")


def _ensure_abierto(c: Cierre) -> None:
    s = situacion(c)
    if s == "caido":
        raise ConflictError(f"{c.code} es un negocio caído.")
    if s == "cerrado":
        raise ConflictError(f"{c.code} ya es un negocio cerrado.")


def _es_venta(c: Cierre) -> bool:
    return c.negocio == TipoNegocio.VENTA


def _paso_promesa(c: Cierre) -> bool:
    """A sale whose next signature to confirm is the promesa."""
    return _es_venta(c) and c.promesa_fecha is None


def _ev(db: Session, c: Cierre, accion: str, actor: User | None, antes=None, despues=None):
    comp._ev(db, "cierre", c.id, accion, actor, antes, despues)


# ---------------------------------------------------------------- related data


def _polizas(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, Poliza]:
    if not ids:
        return {}
    rows = db.scalars(
        select(Poliza)
        .where(Poliza.cierre_id.in_(ids), Poliza.eliminada_at.is_(None))
        .order_by(Poliza.created_at)
    ).unique()
    return {p.cierre_id: p for p in rows}  # the newest live one wins


def _comisiones(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Comision]]:
    out: dict[uuid.UUID, list[Comision]] = {i: [] for i in ids}
    if ids:
        for c in db.scalars(
            select(Comision).where(Comision.cierre_id.in_(ids), Comision.estado != E.ANULADA)
        ).unique():
            out[c.cierre_id].append(c)
    return out


def _abonos(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, list[NegocioAbono]]:
    out: dict[uuid.UUID, list[NegocioAbono]] = {i: [] for i in ids}
    if ids:
        for a in db.scalars(
            select(NegocioAbono)
            .where(NegocioAbono.cierre_id.in_(ids))
            .order_by(NegocioAbono.fecha, NegocioAbono.created_at)
        ).unique():
            out[a.cierre_id].append(a)
    return out


def _inmuebles(db: Session, ids: list[uuid.UUID | None]) -> dict[uuid.UUID, Inmueble]:
    real = [i for i in ids if i]
    if not real:
        return {}
    return {i.id: i for i in db.scalars(select(Inmueble).where(Inmueble.id.in_(real))).unique()}


class Ctx:
    """What the ganancia of several deals needs, loaded once."""

    def __init__(self, db: Session, cierres: list[Cierre]):
        ids = [c.id for c in cierres]
        self.tarifas = configuracion.get(db, "tarifas")
        self.cfg = comp.get_config(db)
        self.polizas = _polizas(db, ids)
        self.comisiones = _comisiones(db, ids)
        self.abonos = _abonos(db, ids)
        self.inmuebles = _inmuebles(db, [c.inmueble_id for c in cierres])


def pct_venta(c: Cierre, t: dict[str, Any]) -> float:
    return float(c.pct_venta) if c.pct_venta is not None else float(t["venta_pct"])


def ganancia(c: Cierre, x: Ctx) -> dict[str, Any]:
    """G-087's breakdown. ``efectiva`` is Compensación's base for commissions."""
    t = x.tarifas
    iva = float(t["iva_pct"]) / 100
    val = c.valor or 0
    cer = situacion(c) == "cerrado"
    coms = x.comisiones.get(c.id, [])
    com_total = sum(m.valor for m in coms)
    venta = _es_venta(c)
    pol = x.polizas.get(c.id) if not venta else None
    if venta:
        pct = pct_venta(c, t)
        hon = val * pct / 100
        hon_iva = hon * iva
        cobrado = hon + hon_iva
        iva_total = hon_iva
        referido = 0.0
        efectiva = hon
        poliza = 0.0
        cobro_d = f"{_pct(pct)} del valor {_cop(val)} = {_cop(hon)} + IVA {_cop(hon_iva)}"
    else:
        pct = float(t["arriendo_pct"])
        hon = val * pct / 100
        hon_iva = hon * iva
        pap = float(t["papeleria"]) if val else 0.0
        pap_base = pap / (1 + iva)
        pap_iva = pap - pap_base
        cobrado = hon + hon_iva + pap
        iva_total = hon_iva + pap_iva
        referido = val * float(t["referidos_pct"]) / 100 if c.referido else 0.0
        efectiva = hon + pap_base - referido
        poliza = val * float(pol.tipo.precio_pct) / 100 * MESES_POLIZA if pol else 0.0
        cobro_d = (
            f"{_pct(pct)} del canon {_cop(hon)} + IVA {_cop(hon_iva)} + papelería {_cop(pap)} "
            "(IVA incluido)"
        )
    estimadas = not coms and not cer and situacion(c) != "caido"
    if estimadas:
        cfg = x.cfg
        personal = float(cfg["pct_personal"])
        p = 0.0
        if c.cerrador_id:
            p += personal * float(cfg["reparto_cerrador"]) / 100
        if c.captador_id:
            p += personal * float(cfg["reparto_captador"]) / 100
        if c.filtro_id:
            p += float(cfg["pct_filtro"])
        com_total = round(efectiva * p / 100)
        com_d = "Estimadas con los porcentajes de Compensación · se generan al cerrar el negocio"
    elif coms:
        com_d = " · ".join(
            f"{m.beneficiario.full_name} · {m.concepto} {_cop(m.valor)}" for m in coms
        )
    else:
        com_d = "No hay comisiones registradas"
    neta = cobrado - iva_total - com_total - poliza - referido
    caido = situacion(c) == "caido"
    lineas = [
        {
            "t": "Cobrado al cliente" if venta else "Cobrado al arrendatario (una sola vez)",
            "d": cobro_d,
            "v": round(cobrado),
            "fuerte": True,
        },
        {
            "t": "− IVA recaudado",
            "d": "Se paga a la DIAN",
            "v": -round(iva_total),
        },
        {"t": "− Comisiones al equipo", "d": com_d, "v": -round(com_total)},
        {
            "t": "− Póliza (la asume la empresa)",
            "d": (
                "No aplica · venta"
                if venta
                else (
                    f"{pol.aseguradora.nombre} · {_pct(pol.tipo.precio_pct)} del canon · "
                    f"{MESES_POLIZA} mes (meses que asume la empresa: PENDIENTE DE CONFIGURACIÓN)"
                    if pol
                    else "Sin póliza registrada en «Pólizas»"
                )
            ),
            "v": -round(poliza),
        },
        {
            "t": "− Pago a referido",
            "d": (
                f"{c.referido} · {_pct(t['referidos_pct'])} del canon"
                if c.referido and not venta
                else "No hubo referido"
            ),
            "v": -round(referido),
        },
        {
            "t": "= Ganancia que dejó el negocio" if cer else "= Ganancia proyectada",
            "d": "Lo que le queda a la empresa",
            "v": round(neta),
            "total": True,
        },
    ]
    no_gan = []
    if venta:
        recibido = sum(a.valor for a in x.abonos.get(c.id, []))
        no_gan.append(
            {
                "t": "Dinero recibido del negocio",
                "d": "Lo que ha pagado el cliente hasta hoy",
                "v": _cop(recibido) if recibido else "—",
            }
        )
    else:
        no_gan.append(
            {
                "t": "IVA del canon",
                "d": (
                    "Inmueble comercial · lo paga el arrendatario cada mes y va al propietario"
                    if c.uso_comercial
                    else "No aplica · inmueble de vivienda"
                ),
                "v": f"{_cop(val * iva)} / mes" if c.uso_comercial else "—",
            }
        )
        ret = t.get("retencion_pct")
        no_gan.append(
            {
                "t": "Retención en la fuente",
                "d": (
                    "El arrendatario es persona jurídica: retiene "
                    + ("un % (PENDIENTE DE CONFIGURACIÓN)" if ret is None else _pct(ret))
                    + " del canon al propietario · no cambia nuestra ganancia"
                    if c.arrendatario_juridica
                    else "No aplica · arrendatario persona natural"
                ),
                "v": (
                    f"{_cop(val * float(ret) / 100)} / mes"
                    if c.arrendatario_juridica and ret is not None
                    else "—"
                ),
            }
        )
    no_gan.append(
        {
            "t": "IVA recaudado de este negocio",
            "d": "Se cobra con la comisión"
            + ("" if venta else " y la papelería")
            + " y se paga a la DIAN",
            "v": _cop(iva_total),
        }
    )
    return {
        "con_valor": bool(c.valor),
        "pct": pct,
        "efectiva": round(efectiva),
        "neta": 0 if caido else round(neta),
        "perdida": bool(c.valor) and not caido and neta < 0,
        "estimadas": estimadas,
        "lineas": lineas,
        "no_ganancia": no_gan,
    }


# ---------------------------------------------------------------- views


def _p(u: User | None) -> dict[str, Any] | None:
    return {"id": u.id, "full_name": u.full_name} if u else None


def _nombre(db: Session, uid: uuid.UUID | None) -> str | None:
    if uid is None:
        return None
    u = db.get(User, uid)
    return u.full_name if u else None


def _inmueble_txt(c: Cierre, x: Ctx) -> str:
    inm = x.inmuebles.get(c.inmueble_id) if c.inmueble_id else None
    if inm is not None:
        return f"{inm.codigo} · {inm.barrio or inm.direccion}"
    return c.lead.busca or "Inmueble sin registrar"


def _estado_txt(c: Cierre) -> tuple[str, str]:
    s = situacion(c)
    if s in ("en_proceso", "por_confirmar") and c.caida_reportada_at:
        return "Caída reportada por el asesor", "bad"
    if s == "por_confirmar" and c.solicitud == "promesa":
        return "Firma de promesa por confirmar", "warn"
    if s == "en_proceso" and c.devuelto_motivo:
        return "Devuelto al asesor", "warn"
    return SITUACION[s]


def fila(db: Session, c: Cierre, x: Ctx, m: str) -> dict[str, Any]:
    s = situacion(c)
    venta = _es_venta(c)
    pol = x.polizas.get(c.id) if not venta else None
    estado_t, estado_c = _estado_txt(c)
    etapas = comp.etapas_de(c.negocio)
    out: dict[str, Any] = {
        "id": c.id,
        "code": c.code,
        "negocio": c.negocio.value if c.negocio else None,
        "tipo": "Venta" if venta else "Arriendo",
        "lead_id": c.lead_id,
        "lead_code": c.lead.code,
        "cliente": c.lead.full_name,
        "origen": f"Lead {c.lead.code} · {FUENTE_LABELS.get(c.lead.fuente, c.lead.fuente.value)}",
        "inmueble": _inmueble_txt(c, x),
        "inmueble_id": c.inmueble_id,
        "valor": c.valor,
        "asesor": _p(c.cerrador),
        "captador": _p(c.captador),
        "filtro": _p(c.filtro),
        "situacion": s,
        "categoria": categoria(c),
        "estado_txt": estado_t,
        "estado_cls": estado_c,
        "fecha": fecha_ref(c),
        "inicio": fechas.local_date(c.cerrado_at),
        "etapa": c.etapa or etapas[0],
        "etapas": etapas,
        "oferta": c.oferta,
        "solicitud": c.solicitud,
        "solicitud_at": c.solicitud_at,
        "solicitud_nota": c.solicitud_nota,
        "devuelto_motivo": c.devuelto_motivo,
        "promesa_fecha": c.promesa_fecha,
        "firma_fecha": c.firma_fecha,
        "paso_promesa": _paso_promesa(c),
        "notaria": c.notaria,
        "notaria_at": c.notaria_at,
        "caida": (
            {
                "motivo": c.caida_motivo,
                "obs": c.caida_obs,
                "reportada_at": c.caida_reportada_at,
                "por": _nombre(db, c.caida_reportada_por_id),
                "confirmada_at": c.caida_confirmada_at,
            }
            if c.caida_motivo or c.caida_confirmada_at
            else None
        ),
        "docs_ubicacion": c.docs_ubicacion,
        "contrato_adjunto": c.contrato_adjunto,
        "poliza": (
            {
                "id": pol.id,
                "estado": pol.estado,
                "estado_txt": POLIZA_TXT.get(pol.estado, (pol.estado, "gray"))[0],
                "estado_cls": POLIZA_TXT.get(pol.estado, (pol.estado, "gray"))[1],
                "tipo": pol.tipo.nombre,
                "aseguradora": pol.aseguradora.nombre,
                "radicado": pol.radicado,
                "firma_fecha": pol.firma_fecha,
                "activada_fecha": pol.activada_fecha,
                "numero": pol.numero_poliza,
            }
            if pol
            else None
        ),
        "abierto": _abierto(c),
    }
    if ve_dinero(m):
        g = ganancia(c, x)
        abonos = x.abonos.get(c.id, [])
        out |= {
            "ganancia": g,
            "ganancia_efectiva": c.ganancia,
            "pct_venta": pct_venta(c, x.tarifas) if venta else None,
            "pct_venta_propio": c.pct_venta is not None,
            "uso_comercial": c.uso_comercial,
            "arrendatario_juridica": c.arrendatario_juridica,
            "referido": c.referido,
            "recibido": sum(a.valor for a in abonos),
            "abonos": [
                {
                    "id": a.id,
                    "valor": a.valor,
                    "fecha": a.fecha,
                    "momento": a.momento,
                    "momento_txt": MOMENTOS.get(a.momento, a.momento),
                    "soporte": a.soporte,
                    "por": a.created_by.full_name if a.created_by else None,
                }
                for a in abonos
            ],
        }
    return out


def _visibles(db: Session, user: User, m: str) -> list[Cierre]:
    q = select(Cierre).order_by(Cierre.numero.desc())
    if m == "asesor":
        q = q.where(Cierre.cerrador_id == user.id)
    return list(db.scalars(q).unique())


def tablero(
    db: Session, user: User, desde: date, hasta: date, tipo: TipoNegocio | None
) -> dict[str, Any]:
    """X02 (Auxiliar, Gerencia, Coordinación) or M16 «Mis negocios» (asesor)."""
    m = ensure_ver(user)
    comp.sincronizar_cierres(db, user)
    todos = _visibles(db, user, m)
    if m == "asesor":
        x = Ctx(db, todos)
        items = [fila(db, c, x, m) for c in todos]
        return {"modo": m, "items": items, "motivos_caida": MOTIVOS_CAIDA}
    if desde > hasta:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    sel = [
        c for c in todos if (tipo is None or c.negocio == tipo) and desde <= fecha_ref(c) <= hasta
    ]
    x = Ctx(db, sel)
    items = [fila(db, c, x, m) for c in sel]
    dinero = ve_dinero(m)

    def cnt(cat: str) -> int:
        return sum(1 for i in items if i["categoria"] == cat)

    def gan(i: dict[str, Any]) -> int:
        return i["ganancia"]["neta"] if dinero and i["ganancia"]["con_valor"] else 0

    kpis = {
        "total": len(items),
        "neg": cnt("neg"),
        "pc": cnt("pc"),
        "cer": cnt("cer"),
        "cai": cnt("cai"),
        "cai_reportadas": sum(
            1 for i in items if i["abierto"] and i["caida"] and i["caida"]["reportada_at"]
        ),
    }
    if dinero:
        kpis["ganancia"] = sum(gan(i) for i in items if i["categoria"] == "cer")
        kpis["proyectada"] = sum(gan(i) for i in items if i["categoria"] in ("neg", "pc"))
    por_tipo = []
    for tp, nombre in ((TipoNegocio.ARRIENDO, "Arriendos"), (TipoNegocio.VENTA, "Ventas")):
        lst = [i for i in items if (i["negocio"] or "arriendo") == tp.value]
        r: dict[str, Any] = {"tipo": tp.value, "t": nombre, "n": len(lst)}
        if dinero:
            r["ganancia"] = sum(gan(i) for i in lst if i["categoria"] == "cer")
        por_tipo.append(r)
    out: dict[str, Any] = {
        "modo": m,
        "desde": desde,
        "hasta": hasta,
        "kpis": kpis,
        "por_tipo": por_tipo,
        "items": items,
        "counts": {
            "sol": sum(1 for i in items if i["situacion"] == "por_confirmar"),
            "proc": sum(1 for i in items if i["abierto"]),
            "cer": cnt("cer"),
            "cai": cnt("cai"),
        },
        "motivos_caida": MOTIVOS_CAIDA,
        "motivos_devolver": MOTIVOS_DEVOLVER,
        "momentos": MOMENTOS,
        "puede": {
            "gestionar": m == "auxiliar",
            "datos": m in ("auxiliar", "gerencia"),
        },
    }
    if dinero:
        t = x.tarifas
        out["ganancias"] = sorted(
            (
                {
                    "id": i["id"],
                    "code": i["code"],
                    "tipo": i["tipo"],
                    "categoria": i["categoria"],
                    "con_valor": i["ganancia"]["con_valor"],
                    "neta": gan(i),
                }
                for i in items
            ),
            key=lambda g: -g["neta"],
        )
        out["tarifas"] = {
            "arriendo_pct": t["arriendo_pct"],
            "papeleria": t["papeleria"],
            "iva_pct": t["iva_pct"],
            "venta_pct": t["venta_pct"],
            "referidos_pct": t["referidos_pct"],
            "retencion_pct": t["retencion_pct"],
        }
        out["inmuebles"] = [
            {
                "id": i.id,
                "negocio": i.negocio.value,
                "t": f"{i.codigo} · {i.barrio or i.direccion}",
                "precio": i.precio,
            }
            for i in db.scalars(select(Inmueble).order_by(Inmueble.codigo)).unique()
        ]
    return out


def detalle(db: Session, user: User, c: Cierre) -> dict[str, Any]:
    m = ensure_ver(user)
    x = Ctx(db, [c])
    evs = db.scalars(
        select(CompensacionEvento)
        .where(CompensacionEvento.entidad == "cierre", CompensacionEvento.entidad_id == str(c.id))
        .order_by(CompensacionEvento.created_at.desc())
    ).unique()
    return fila(db, c, x, m) | {
        "historial": [
            {
                "at": e.created_at,
                "accion": e.accion,
                "por": e.created_by.full_name if e.created_by else "Sistema",
                "detalle": _detalle_ev(e.despues, dinero=ve_dinero(m)),
            }
            for e in evs
        ],
    }


_DINERO = {"valor", "ganancia", "pct_venta", "referido"}


def _detalle_ev(d: dict[str, Any] | None, *, dinero: bool) -> str | None:
    if not d:
        return None
    parts = [f"{v}" for k, v in d.items() if v not in (None, "") and (dinero or k not in _DINERO)]
    return " · ".join(parts) or None


# ---------------------------------------------------------------- actions


def _txt(v: Any, n: int = 300) -> str | None:
    s = (str(v).strip() if v is not None else "") or None
    if s and len(s) > n:
        raise DomainError(f"El texto puede tener hasta {n} caracteres.")
    return s


def _fecha_pasada(f: date, que: str) -> None:
    if f > hoy():
        raise DomainError(f"La {que} no puede ser futura.")


def enviar_ganancia(db: Session, c: Cierre, actor: User) -> bool:
    """Closed deal with a value → Compensación gets the ganancia efectiva (and commissions)."""
    if situacion(c) != "cerrado" or not c.valor:
        return False
    g = ganancia(c, Ctx(db, [c]))["efectiva"]
    if g <= 0 or g == c.ganancia:
        return False
    comp.registrar_ganancia(db, c, ganancia=g, captador_id=c.captador_id, actor=actor)
    return True


def editar(db: Session, c: Cierre, data: dict[str, Any], *, actor: User) -> Cierre:
    """Deal data: property, value, % of the sale, rental use and tenant, referral, documents."""
    _ensure_datos(actor)
    if c.estado == EstadoCierre.CAIDO:
        raise ConflictError(f"{c.code} es un negocio caído.")
    antes: dict[str, Any] = {}
    despues: dict[str, Any] = {}

    def put(k: str, v: Any, txt: Any = None) -> None:
        if getattr(c, k) != v:
            antes[k] = _show(k, getattr(c, k))
            setattr(c, k, v)
            despues[k] = txt if txt is not None else _show(k, v)

    if "negocio" in data and data["negocio"] is not None:
        nuevo = TipoNegocio(data["negocio"])
        if nuevo != c.negocio:
            if c.negocio is not None:
                raise DomainError("El tipo de negocio sale del lead; no se cambia aquí.")
            put("negocio", nuevo, "Venta" if nuevo == TipoNegocio.VENTA else "Arriendo")
            c.etapa = comp.etapas_de(nuevo)[0]
    if "inmueble_id" in data:
        iid = data["inmueble_id"]
        inm = None
        if iid:
            inm = db.get(Inmueble, iid)
            if inm is None:
                raise NotFoundError("Ese inmueble no existe.")
            if c.negocio and inm.negocio != c.negocio:
                raise DomainError(
                    f"El inmueble {inm.codigo} es para "
                    f"{'venta' if inm.negocio == TipoNegocio.VENTA else 'arriendo'}."
                )
        put("inmueble_id", inm.id if inm else None, inm.codigo if inm else "Sin inmueble")
        if inm and inm.precio and not c.valor and "valor" not in data:
            put("valor", inm.precio)
    if "valor" in data:
        v = data["valor"]
        if v is not None and (int(v) <= 0 or int(v) > 100_000_000_000):
            raise DomainError("Escribe un valor válido en pesos.")
        put("valor", int(v) if v is not None else None)
    if "pct_venta" in data:
        p = data["pct_venta"]
        if not _es_venta(c):
            raise DomainError(
                "El % de comisión es solo para ventas; en arriendos sale de las tarifas."
            )
        if p is not None and not 0 < float(p) <= 20:
            raise DomainError("Escribe un porcentaje válido (mayor que 0 y hasta 20).")
        put("pct_venta", Decimal(str(round(float(p), 2))) if p is not None else None)
    for k in ("uso_comercial", "arrendatario_juridica"):
        if k in data and data[k] is not None:
            if _es_venta(c):
                raise DomainError("El uso del inmueble y el arrendatario aplican solo a arriendos.")
            put(k, bool(data[k]))
    if "referido" in data:
        if _es_venta(c) and data["referido"]:
            raise DomainError("El pago a referidos aplica solo a arriendos.")
        put("referido", _txt(data["referido"], 200))
    if "docs_ubicacion" in data:
        d = _txt(data["docs_ubicacion"])
        if not d:
            raise DomainError("Escribe dónde quedan los documentos.")
        put("docs_ubicacion", d)
    if "contrato_adjunto" in data and data["contrato_adjunto"] is not None:
        put("contrato_adjunto", bool(data["contrato_adjunto"]))
    if not despues:
        return c
    _ev(db, c, f"Datos de {c.code} actualizados", actor, antes, despues)
    db.flush()
    enviar_ganancia(db, c, actor)
    db.flush()
    return c


def _show(k: str, v: Any) -> Any:
    if v is None:
        return None
    if k in ("valor",):
        return _cop(v)
    if k == "pct_venta":
        return _pct(v)
    if k == "uso_comercial":
        return "Comercial" if v else "Vivienda"
    if k == "arrendatario_juridica":
        return "Persona jurídica" if v else "Persona natural"
    if k == "contrato_adjunto":
        return "Contrato adjunto" if v else "Sin contrato"
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, TipoNegocio):
        return v.value
    return v


def _ensure_mueve(c: Cierre, actor: User) -> None:
    m = ensure_ver(actor)
    if m == "auxiliar" or (m == "asesor" and _es_suyo(c, actor)):
        return
    raise PermissionDeniedError(
        "La etapa la pasa el asesor del negocio o la Auxiliar administrativa."
    )


def pasar_etapa(db: Session, c: Cierre, data: dict[str, Any], *, actor: User) -> Cierre:
    """M16 «Pasar etapa»: the next stage (not the last one, which comes with the signature) or
    the same one to record a new offer. A sale moving to «Escrituración» needs the notary
    appointment."""
    _ensure_mueve(c, actor)
    _ensure_abierto(c)
    etapas = comp.etapas_de(c.negocio)
    actual = c.etapa if c.etapa in etapas else etapas[0]
    i = etapas.index(actual)
    nueva = data.get("etapa") or actual
    if nueva not in etapas:
        raise DomainError("Esa etapa no existe para este tipo de negocio.")
    j = etapas.index(nueva)
    if j == len(etapas) - 1:
        raise DomainError(
            f"«{nueva}» queda cuando la Auxiliar confirma la firma: usa «Solicitar cierre»."
        )
    if j not in (i, i + 1):
        raise DomainError(f"Desde «{actual}» solo se pasa a «{etapas[i + 1]}».")
    obs = _txt(data.get("observacion"))
    if not obs:
        raise DomainError("Escribe qué pasó.")
    oferta = _txt(data.get("oferta"))
    if j == i and not oferta:
        raise DomainError("Elige la siguiente etapa o escribe la nueva oferta.")
    despues: dict[str, Any] = {"etapa": nueva, "observacion": obs}
    if nueva == "Escrituración" and j != i:
        notaria = _txt(data.get("notaria"), 200)
        at = data.get("notaria_at")
        if not notaria or not at:
            raise DomainError("Programa la cita en notaría: fecha, hora y notaría.")
        if isinstance(at, str):
            at = datetime.fromisoformat(at)
        if at.tzinfo is None:
            at = at.replace(tzinfo=fechas.BOGOTA)
        c.notaria, c.notaria_at = notaria, at
        despues["notaria"] = f"Cita en notaría {fechas.fmt(at)} · {notaria}"
    if oferta:
        c.oferta = f"{oferta} · {_fd(hoy())}"
        despues["oferta"] = oferta
    antes = {"etapa": actual}
    c.etapa = nueva
    _ev(
        db,
        c,
        f"Etapa: {nueva}" if j != i else "Nueva oferta registrada",
        actor,
        antes,
        despues,
    )
    db.flush()
    return c


def solicitar(db: Session, c: Cierre, nota: str | None, *, actor: User) -> Cierre:
    """M16 «Solicitar cierre»: «¿El cliente ya firmó?» → the Auxiliar confirms the signature."""
    if not (ensure_ver(actor) == "asesor" and _es_suyo(c, actor)):
        raise PermissionDeniedError("El cierre lo solicita el asesor del negocio.")
    _ensure_abierto(c)
    if c.solicitud:
        raise ConflictError(
            "Ya solicitaste el cierre: la Auxiliar administrativa lo está revisando."
        )
    if c.caida_reportada_at:
        raise ConflictError("Reportaste este negocio como caído: espera la confirmación.")
    c.solicitud = "promesa" if _paso_promesa(c) else "cierre"
    c.solicitud_at = fechas.now()
    c.solicitud_nota = _txt(nota)
    c.devuelto_motivo = c.devuelto_at = None
    que = "la firma de la promesa" if c.solicitud == "promesa" else "el cierre"
    _ev(
        db,
        c,
        f"{actor.full_name} solicitó confirmar {que}",
        actor,
        None,
        {"nota": c.solicitud_nota},
    )
    db.flush()
    return c


def confirmar(
    db: Session,
    c: Cierre,
    *,
    fecha: date,
    contrato_adjunto: bool,
    observacion: str | None,
    actor: User,
) -> dict[str, Any]:
    """The Auxiliar confirms the signature: the promesa (sales) or the closing one → «negocio
    cerrado», ganancia efectiva to Compensación and, for a rental, the contract in «Pólizas»."""
    _ensure_aux(actor, "Confirmar la firma")
    _ensure_abierto(c)
    if c.caida_reportada_at:
        raise ConflictError(
            "El asesor reportó la caída de este negocio: confírmala o descártala primero."
        )
    _fecha_pasada(fecha, "fecha de firma")
    if fecha < fechas.local_date(c.cerrado_at) - timedelta(days=365):
        raise DomainError("La fecha de firma es demasiado antigua para este negocio.")
    obs = _txt(observacion)
    etapas = comp.etapas_de(c.negocio)
    c.solicitud = c.solicitud_at = c.solicitud_nota = None
    c.devuelto_motivo = c.devuelto_at = None
    c.confirmado_por_id = actor.id
    if contrato_adjunto:
        c.contrato_adjunto = True
    if _paso_promesa(c):
        c.promesa_fecha = fecha
        if c.etapa not in etapas or etapas.index(c.etapa) < etapas.index("Promesa firmada"):
            c.etapa = "Promesa firmada"
        _ev(
            db,
            c,
            "Firma de la promesa confirmada",
            actor,
            None,
            {"fecha": _fd(fecha), "observacion": obs},
        )
        db.flush()
        return {"cerrado": False, "comisiones": False, "poliza": False}
    if c.promesa_fecha and fecha < c.promesa_fecha:
        raise DomainError("La escritura no puede ser anterior a la promesa.")
    c.firma_fecha = fecha
    c.etapa = etapas[-1]
    _ev(
        db,
        c,
        "Firma confirmada · negocio cerrado"
        if not _es_venta(c)
        else "Firma de la escritura confirmada · negocio cerrado",
        actor,
        None,
        {"fecha": _fd(fecha), "observacion": obs},
    )
    db.flush()
    comisiones = enviar_ganancia(db, c, actor)
    poliza = False
    if not _es_venta(c):
        from app.services import polizas

        p = _polizas(db, [c.id]).get(c.id)
        if p is not None and p.estado == "aprobada" and p.firma_fecha is None:
            if fecha >= p.estudio_fecha:
                polizas.firmar(db, p, fecha, actor=actor)
                poliza = True
    db.flush()
    return {"cerrado": True, "comisiones": comisiones, "poliza": poliza}


def devolver(db: Session, c: Cierre, motivo: str, *, actor: User) -> Cierre:
    """«Devolver al asesor» with a reason: the signature isn't confirmed."""
    _ensure_aux(actor, "Devolver el cierre")
    _ensure_abierto(c)
    if not c.solicitud:
        raise ConflictError("Este negocio no tiene un cierre por confirmar.")
    m = _txt(motivo)
    if not m:
        raise DomainError("Elige el motivo.")
    c.solicitud = c.solicitud_at = c.solicitud_nota = None
    c.devuelto_motivo = m
    c.devuelto_at = fechas.now()
    _ev(db, c, "Cierre devuelto al asesor", actor, None, {"motivo": m})
    db.flush()
    return c


def caida(db: Session, c: Cierre, motivo: str, obs: str, *, actor: User) -> str:
    """The asesor reports it («por confirmar»); the Auxiliar confirms it (reported or not)."""
    m = ensure_ver(actor)
    if not (m == "auxiliar" or (m == "asesor" and _es_suyo(c, actor))):
        raise PermissionDeniedError(
            "La caída la reporta el asesor del negocio y la confirma la Auxiliar administrativa."
        )
    _ensure_abierto(c)
    mot = _txt(motivo, 100)
    texto = _txt(obs)
    if not mot or mot not in MOTIVOS_CAIDA:
        raise DomainError("Elige el motivo.")
    if mot == "Póliza negada" and _es_venta(c):
        raise DomainError("«Póliza negada» aplica solo a arriendos: las ventas no llevan póliza.")
    if not texto:
        raise DomainError("Escribe qué pasó.")
    if m == "asesor":
        if c.caida_reportada_at:
            raise ConflictError("Ya reportaste la caída: la Auxiliar administrativa la confirma.")
        c.caida_motivo, c.caida_obs = mot, texto
        c.caida_reportada_at = fechas.now()
        c.caida_reportada_por_id = actor.id
        _ev(
            db,
            c,
            "Negocio caído (por confirmar)",
            actor,
            None,
            {"motivo": mot, "observacion": texto},
        )
        db.flush()
        return "reportada"
    c.caida_motivo, c.caida_obs = mot, texto
    c.caida_confirmada_at = fechas.now()
    c.estado = EstadoCierre.CAIDO
    c.solicitud = c.solicitud_at = c.solicitud_nota = None
    _ev(db, c, "Negocio caído confirmado", actor, None, {"motivo": mot, "observacion": texto})
    for com in db.scalars(select(Comision).where(Comision.cierre_id == c.id)).unique():
        if com.estado not in (E.PAGADA, E.ANULADA):
            comp._anular(db, "comision", com, "Negocio caído: no genera comisión.", actor)
    db.flush()
    return "confirmada"


def descartar_caida(db: Session, c: Cierre, *, actor: User) -> Cierre:
    """The asesor reported a caída but the deal goes on."""
    _ensure_aux(actor, "Seguir con el negocio")
    _ensure_abierto(c)
    if not c.caida_reportada_at:
        raise ConflictError("Este negocio no tiene una caída reportada.")
    antes = {"motivo": c.caida_motivo}
    c.caida_motivo = c.caida_obs = c.caida_reportada_at = c.caida_reportada_por_id = None
    _ev(db, c, "Caída descartada · el negocio sigue", actor, antes, None)
    db.flush()
    return c


def abono(db: Session, c: Cierre, data: dict[str, Any], *, actor: User) -> NegocioAbono:
    """G-033 «Registrar dinero recibido» on a sale."""
    _ensure_aux(actor, "Registrar el dinero recibido")
    if not _es_venta(c):
        raise DomainError("El dinero recibido se registra en ventas.")
    if c.estado == EstadoCierre.CAIDO:
        raise ConflictError(f"{c.code} es un negocio caído.")
    v = int(data.get("valor") or 0)
    if v <= 0:
        raise DomainError("Escribe el valor recibido.")
    f = data.get("fecha")
    if not f:
        raise DomainError("Elige la fecha.")
    _fecha_pasada(f, "fecha")
    mom = data.get("momento") or "otro"
    if mom not in MOMENTOS:
        raise DomainError("Elige el momento: en la promesa, en la escritura u otro abono.")
    a = NegocioAbono(
        cierre_id=c.id,
        valor=v,
        fecha=f,
        momento=mom,
        soporte=bool(data.get("soporte")),
        created_by_id=actor.id,
    )
    db.add(a)
    _ev(
        db,
        c,
        "Dinero recibido registrado",
        actor,
        None,
        {"valor": _cop(v), "momento": MOMENTOS[mom], "fecha": _fd(f)},
    )
    db.flush()
    return a


# ---------------------------------------------------------------- avisos


def por_confirmar(db: Session) -> list[Cierre]:
    """Auxiliar: signatures and caídas the asesores asked to confirm."""
    rows = db.scalars(
        select(Cierre)
        .where(
            Cierre.estado == EstadoCierre.CERRADO,
            Cierre.firma_fecha.is_(None),
            (Cierre.solicitud.is_not(None)) | (Cierre.caida_reportada_at.is_not(None)),
        )
        .order_by(Cierre.numero)
    ).unique()
    return list(rows)


def devueltos_de(db: Session, asesor: User) -> list[Cierre]:
    return list(
        db.scalars(
            select(Cierre).where(
                Cierre.cerrador_id == asesor.id,
                Cierre.estado == EstadoCierre.CERRADO,
                Cierre.firma_fecha.is_(None),
                Cierre.solicitud.is_(None),
                Cierre.devuelto_motivo.is_not(None),
            )
        ).unique()
    )


def caidos_desde(db: Session, desde: datetime, asesor: User | None = None) -> list[Cierre]:
    q = select(Cierre).where(Cierre.caida_confirmada_at >= desde)
    if asesor is not None:
        q = q.where(Cierre.cerrador_id == asesor.id)
    return list(db.scalars(q.order_by(Cierre.caida_confirmada_at.desc())).unique())


def cerrados_desde(db: Session, desde: date, asesor: User) -> list[Cierre]:
    return list(
        db.scalars(
            select(Cierre).where(
                Cierre.cerrador_id == asesor.id,
                Cierre.estado == EstadoCierre.CERRADO,
                Cierre.firma_fecha >= desde,
                Cierre.confirmado_por_id.is_not(None),
            )
        ).unique()
    )


def notaria_proxima(db: Session, asesor: User, now: datetime) -> list[Cierre]:
    return list(
        db.scalars(
            select(Cierre).where(
                Cierre.cerrador_id == asesor.id,
                Cierre.estado == EstadoCierre.CERRADO,
                Cierre.firma_fecha.is_(None),
                Cierre.notaria_at >= now,
                Cierre.notaria_at <= now + timedelta(days=2),
            )
        ).unique()
    )
