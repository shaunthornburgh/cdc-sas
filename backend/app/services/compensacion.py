"""Compensación: commissions, bonuses, payments and salaries (G05, X04, M12–M14, Z05).

Rules (DECISIONS G-0xx; every amount and percentage is an example value that Gerencia edits in
the configuration, as the prototypes mark them «PENDIENTE DE CONFIGURACIÓN»):

* **Negocio cerrado (NEG-…)**: one per lead marked «Ganado». The system finds who took part:
  *cerrador* = asesor of the lead's last realized visit, *filtro* = the Atención y Preventa
  person the lead is assigned to. The *captador* is chosen by the Auxiliar or Gerencia, because a
  lead isn't linked to a captación yet. If the lead stops being «Ganado», the deal is «caído» and
  its unpaid commissions are cancelled.
* **Ganancia efectiva**: what the company keeps from the deal (after colleagues and referrals,
  without IVA). There are no deal amounts in the system yet, so the Auxiliar or Gerencia enters it.
  Commissions are generated as soon as it is entered.
* **Commissions of internal staff** are a percentage of the ganancia efectiva:
  asesores share ``pct_personal`` (33.3 %), split ``reparto_cerrador`` / ``reparto_captador``
  (70 / 30) between closer and captador; Atención y Preventa gets ``pct_filtro`` (5 %) when the
  cita they scheduled ended in the deal. Without a captador, the captador share isn't paid.
* **Coordinador**: group commission ``pct_grupal`` of the team's ganancia when the month's total
  reaches ``meta_grupal``, and/or an individual bonus (``modalidad_coordinador``).
* **Performance bonus**: ``bono_monto`` for each person whose month result (Rendimiento) is at
  least ``bono_umbral``. Calculated once the month has ended («Calcular bonos del mes»).
* **Approval flow** (comisiones and bonos): Generada → the Auxiliar gives the «visto bueno» →
  Gerencia approves (a payment «en proceso» is scheduled for day ``dia_pago`` of the next month) →
  Gerencia records the payment. Anyone of the two can cancel (with reason) or adjust the amount
  before the visto bueno, with reason. Every step goes to the history.
* **Salaries**: two periods a month, each half the monthly salary (paid on the 15th and the 30th).
  The Auxiliar confirms, Gerencia approves and pays. Absences (incapacidades, permisos) don't exist
  in the system yet, so there are no deductions.
* **Who sees what**: everyone sees their own; the Auxiliar and Gerencia see and manage everything.
  Coordinación sees only its own (DECISIONS: pay data is outside Coordinación's scope).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Bono,
    Cierre,
    Comision,
    CompensacionConfig,
    CompensacionEvento,
    Lead,
    LiquidacionSalario,
    Pago,
    SalarioConfig,
    User,
)
from app.models.enums import (
    Cargo,
    EstadoCierre,
    EstadoCita,
    EstadoCompensacion,
    EstadoPago,
    EstadoSalario,
    EtapaLead,
    TipoBono,
    TipoCita,
    TipoComision,
    TipoNegocio,
    TipoPago,
)
from app.services import fechas, novedades
from app.services import rendimiento as rend
from app.services.errors import DomainError, NotFoundError, PermissionDeniedError

E = EstadoCompensacion
CONFIG_DEFAULT: dict[str, Any] = {
    "pct_personal": 33.3,
    "reparto_cerrador": 70,
    "reparto_captador": 30,
    "pct_filtro": 5,
    "pct_grupal": 2.5,
    "meta_grupal": 20_000_000,
    "bono_umbral": 80,
    "bono_monto": 200_000,
    "modalidad_coordinador": "ambos",  # bono · grupal · ambos
    "dia_pago": 5,
    "dia_corte_1": 15,
    "dia_corte_2": 30,
}
CONFIG_LABELS = {
    "pct_personal": "Porcentaje para el personal interno (asesores) sobre la ganancia efectiva",
    "reparto_cerrador": "Reparto · cerrador (%)",
    "reparto_captador": "Reparto · captador (%)",
    "pct_filtro": "Atención y Preventa · cita que termina en negocio (% de la ganancia)",
    "pct_grupal": "Coordinador · comisión grupal (% de la ganancia del equipo)",
    "meta_grupal": "Coordinador · meta de ganancia del equipo en el mes",
    "bono_umbral": "Bono por rendimiento · resultado mínimo (%)",
    "bono_monto": "Bono por rendimiento · valor",
    "modalidad_coordinador": "Coordinador · modalidad",
    "dia_pago": "Día de pago de comisiones y bonos",
    "dia_corte_1": "Salario · día del 1.er corte",
    "dia_corte_2": "Salario · día del 2.º corte",
}
CITAS_DE_CLIENTE = (TipoCita.VISITA_ARRIENDO, TipoCita.VISITA_VENTA, TipoCita.REUNION_ASESORIA)
ESTADO_LABELS = {
    "comision": {
        E.GENERADA: "Generada",
        E.VISTO_BUENO: "Con visto bueno",
        E.PENDIENTE_PAGO: "Pendiente de pago",
        E.PAGADA: "Pagada",
        E.ANULADA: "Anulada",
    },
    "bono": {
        E.GENERADA: "Generado",
        E.VISTO_BUENO: "Con visto bueno",
        E.PENDIENTE_PAGO: "Pendiente de pago",
        E.PAGADA: "Pagado",
        E.ANULADA: "Anulado",
    },
}
SALARIO_LABELS = {
    EstadoSalario.POR_CONFIRMAR: "Por confirmar",
    EstadoSalario.CONFIRMADO: "Confirmado",
    EstadoSalario.PAGADO: "Pagado",
}
PAGO_LABELS = {EstadoPago.EN_PROCESO: "En proceso", EstadoPago.PAGADO: "Pagado"}
MES_CORTO = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def money(v: float | int | None) -> str:
    return "$" + f"{round(v or 0):,}".replace(",", ".")


def pct_txt(v: float | Decimal) -> str:
    f = float(v)
    return (str(int(f)) if f == int(f) else f"{f:g}").replace(".", ",") + " %"


def dia_mes(d: date) -> str:
    return f"{d.day} {MES_CORTO[d.month - 1]}"


# ---------------------------------------------------------------- access


def is_gerencia(u: User) -> bool:
    return u.cargo == Cargo.GERENCIA


def is_auxiliar(u: User) -> bool:
    return u.cargo == Cargo.AUXILIAR_ADMINISTRATIVA


def can_manage(u: User) -> bool:
    """See everyone's compensation and register / adjust it: the Auxiliar and Gerencia."""
    return is_gerencia(u) or is_auxiliar(u)


def ensure_manage(u: User) -> None:
    if not can_manage(u):
        raise PermissionDeniedError(
            "Comisiones, bonos y salarios los gestionan la Auxiliar administrativa y Gerencia."
        )


def _ev(
    db: Session, entidad: str, eid: Any, accion: str, actor: User | None, antes=None, despues=None
):
    db.add(
        CompensacionEvento(
            entidad=entidad,
            entidad_id=str(eid),
            accion=accion,
            antes=antes or {},
            despues=despues or {},
            created_by_id=actor.id if actor else None,
        )
    )


# ---------------------------------------------------------------- config


def get_config(db: Session) -> dict[str, Any]:
    row = db.get(CompensacionConfig, 1)
    return CONFIG_DEFAULT | ((row.valores if row else {}) or {})


def set_config(db: Session, valores: dict[str, Any], *, actor: User) -> dict[str, Any]:
    if not is_gerencia(actor):
        raise PermissionDeniedError(
            "Los porcentajes, montos y fechas de pago los configura Gerencia."
        )
    unknown = set(valores) - set(CONFIG_DEFAULT)
    if unknown:
        raise DomainError(f"No existe el valor «{sorted(unknown)[0]}».")
    cur = get_config(db)
    new = cur | valores
    for k in ("pct_personal", "pct_filtro", "pct_grupal", "reparto_cerrador", "reparto_captador"):
        if not 0 <= float(new[k]) <= 100:
            raise DomainError(f"«{CONFIG_LABELS[k]}» va de 0 a 100.")
    if float(new["reparto_cerrador"]) + float(new["reparto_captador"]) != 100:
        raise DomainError("El reparto entre cerrador y captador debe sumar 100 %.")
    if not 0 <= int(new["bono_umbral"]) <= 100:
        raise DomainError("El resultado mínimo del bono va de 0 a 100.")
    if int(new["bono_monto"]) < 0 or int(new["meta_grupal"]) < 0:
        raise DomainError("Los valores en pesos no pueden ser negativos.")
    if new["modalidad_coordinador"] not in ("bono", "grupal", "ambos"):
        raise DomainError("La modalidad del Coordinador es bono, grupal o ambos.")
    for k in ("dia_pago", "dia_corte_1", "dia_corte_2"):
        if not 1 <= int(new[k]) <= 31:
            raise DomainError("Los días de pago van del 1 al 31.")
    if int(new["dia_corte_1"]) >= int(new["dia_corte_2"]):
        raise DomainError("El 1.er corte debe ser antes que el 2.º.")
    cambios = {k: v for k, v in new.items() if cur.get(k) != v}
    if not cambios:
        return cur
    row = db.get(CompensacionConfig, 1)
    if row is None:
        row = CompensacionConfig(id=1, valores={})
        db.add(row)
    row.valores = {k: v for k, v in new.items()}
    row.updated_by_id = actor.id
    row.updated_at = fechas.now()
    _ev(db, "config", 1, "Configuración actualizada", actor, {k: cur[k] for k in cambios}, cambios)
    db.flush()
    return new


def fecha_pago_cb(periodo: date, cfg: dict[str, Any]) -> date:
    """Day «dia_pago» of the month after ``periodo``."""
    nxt = (periodo.replace(day=28) + timedelta(days=4)).replace(day=1)
    return _clamp_day(nxt, int(cfg["dia_pago"]))


def _clamp_day(month_first: date, day: int) -> date:
    last = (
        (month_first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    ).day
    return month_first.replace(day=min(day, last))


def _periodo_de(dt: datetime) -> date:
    return fechas.local_date(dt).replace(day=1)


# ---------------------------------------------------------------- closed deals


def _cerrador(lead: Lead) -> uuid.UUID | None:
    hechas = sorted(
        (c for c in lead.citas if c.estado == EstadoCita.REALIZADA and c.tipo in CITAS_DE_CLIENTE),
        key=lambda c: c.scheduled_at,
    )
    return hechas[-1].asesor_id if hechas else None


def sincronizar_cierres(db: Session, actor: User | None = None) -> None:
    """One NEG per lead «Ganado»; a lead that stopped being «Ganado» makes its deal «caído»."""
    con = {c.lead_id: c for c in db.scalars(select(Cierre)).unique()}
    ganados = db.scalars(
        select(Lead).options(selectinload(Lead.citas)).where(Lead.etapa == EtapaLead.GANADO)
    ).unique()
    ids = set()
    for lead in ganados:
        ids.add(lead.id)
        c = con.get(lead.id)
        if c is None:
            filtro = (
                lead.assigned_to
                if lead.assigned_to and rend.perfil(lead.assigned_to) == "atencion"
                else None
            )
            c = Cierre(
                lead_id=lead.id,
                negocio=lead.negocio,
                cerrado_at=lead.cerrado_at or fechas.now(),
                cerrador_id=_cerrador(lead),
                filtro_id=filtro.id if filtro else None,
            )
            db.add(c)
            db.flush()
            _ev(db, "cierre", c.id, f"Negocio {c.code} registrado: lead {lead.code} ganado", actor)
        elif c.estado == EstadoCierre.CAIDO:
            c.estado = EstadoCierre.CERRADO
            _ev(db, "cierre", c.id, f"Negocio {c.code} reabierto: el lead volvió a «Ganado»", actor)
    for lead_id, c in con.items():
        if lead_id not in ids and c.estado == EstadoCierre.CERRADO:
            c.estado = EstadoCierre.CAIDO
            _ev(db, "cierre", c.id, f"Negocio {c.code} caído: el lead ya no está «Ganado»", actor)
            for com in db.scalars(select(Comision).where(Comision.cierre_id == c.id)).unique():
                if com.estado not in (E.PAGADA, E.ANULADA):
                    _anular(db, "comision", com, "Negocio caído: no genera comisión.", actor)
    db.flush()


def cierres(db: Session, actor: User) -> list[Cierre]:
    ensure_manage(actor)
    sincronizar_cierres(db, actor)
    return list(db.scalars(select(Cierre).order_by(Cierre.cerrado_at.desc())).unique())


def registrar_ganancia(
    db: Session,
    cierre: Cierre,
    *,
    ganancia: int,
    captador_id: uuid.UUID | None,
    actor: User,
) -> Cierre:
    """The Auxiliar or Gerencia enters the deal's ganancia efectiva → commissions are generated."""
    ensure_manage(actor)
    if cierre.estado == EstadoCierre.CAIDO:
        raise DomainError("Este negocio está caído: no genera comisiones.")
    if ganancia <= 0:
        raise DomainError("La ganancia efectiva debe ser mayor que $0.")
    captador = None
    if captador_id:
        captador = db.get(User, captador_id)
        if captador is None or rend.perfil(captador) != "asesor":
            raise DomainError("El captador debe ser un asesor activo.")
    existentes = {
        c.tipo: c
        for c in db.scalars(select(Comision).where(Comision.cierre_id == cierre.id)).unique()
        if c.tipo != TipoComision.MANUAL and c.estado != E.ANULADA
    }
    avanzadas = [c for c in existentes.values() if c.estado != E.GENERADA]
    if avanzadas and (ganancia != cierre.ganancia or captador_id != cierre.captador_id):
        raise DomainError(
            "Algunas comisiones de este negocio ya tienen visto bueno: "
            "ajusta cada comisión con motivo."
        )
    antes = {
        "ganancia": cierre.ganancia,
        "captador": cierre.captador.full_name if cierre.captador else None,
    }
    cierre.ganancia = ganancia
    cierre.captador_id = captador_id
    cierre.captador = captador
    _ev(
        db,
        "cierre",
        cierre.id,
        f"Ganancia de {cierre.code} registrada",
        actor,
        antes,
        {"ganancia": ganancia, "captador": captador.full_name if captador else None},
    )
    _generar_comisiones(db, cierre, existentes, actor)
    db.flush()
    return cierre


def _generar_comisiones(db: Session, cierre: Cierre, existentes: dict, actor: User) -> None:
    cfg = get_config(db)
    neg = "venta" if cierre.negocio == TipoNegocio.VENTA else "arriendo"
    cerrado = "cerrada" if cierre.negocio == TipoNegocio.VENTA else "cerrado"
    g = cierre.ganancia or 0
    personal = float(cfg["pct_personal"])
    cliente = cierre.lead.full_name
    plan: list[tuple[TipoComision, uuid.UUID | None, float, str, str]] = [
        (
            TipoComision.CERRADOR,
            cierre.cerrador_id,
            personal * float(cfg["reparto_cerrador"]) / 100,
            f"Comisión · {neg} {cerrado} {cierre.code}",
            f"Cerró el negocio · cliente {cliente}",
        ),
        (
            TipoComision.CAPTADOR,
            cierre.captador_id,
            personal * float(cfg["reparto_captador"]) / 100,
            f"Comisión · captación del inmueble de {cierre.code}",
            f"Captó el inmueble · lo cerró {cierre.cerrador.full_name if cierre.cerrador else '—'}",
        ),
        (
            TipoComision.FILTRO,
            cierre.filtro_id,
            float(cfg["pct_filtro"]),
            f"Comisión · cita que terminó en {neg} {cierre.code}",
            f"{neg.capitalize()} {cerrado} · la cita la atendió "
            f"{cierre.cerrador.full_name if cierre.cerrador else '—'}",
        ),
    ]
    for tipo, quien, pct, concepto, detalle in plan:
        cur = existentes.get(tipo)
        valor = round(g * pct / 100)
        if quien is None or valor <= 0:
            if cur is not None:  # e.g. the captador was removed
                _anular(db, "comision", cur, "Ya no participa en el negocio.", actor)
            continue
        detalle_full = f"{detalle} · ganancia {money(g)} × {pct_txt(round(pct, 3))}"
        if cur is not None and cur.beneficiario_id == quien:
            if cur.valor != valor:
                _ev(
                    db,
                    "comision",
                    cur.id,
                    "Valor recalculado",
                    actor,
                    {"valor": cur.valor},
                    {"valor": valor},
                )
            cur.valor, cur.base, cur.porcentaje, cur.detalle = (
                valor,
                g,
                Decimal(str(round(pct, 3))),
                detalle_full,
            )
            continue
        if cur is not None:
            _anular(db, "comision", cur, "Cambió la persona que participó.", actor)
        com = Comision(
            beneficiario_id=quien,
            tipo=tipo,
            cierre_id=cierre.id,
            concepto=concepto,
            detalle=detalle_full,
            base=g,
            porcentaje=Decimal(str(round(pct, 3))),
            valor=valor,
            fecha=cierre.cerrado_at,
            periodo=_periodo_de(cierre.cerrado_at),
            estado=E.GENERADA,
            created_by_id=actor.id,
        )
        db.add(com)
        db.flush()
        _ev(
            db,
            "comision",
            com.id,
            "Comisión generada",
            actor,
            None,
            {"valor": valor, "estado": "generada"},
        )


# ---------------------------------------------------------------- month-end


def calcular_mes(db: Session, mes: str, *, actor: User) -> dict[str, int]:
    """Performance bonuses and the Coordinador's group commission of a month that has ended."""
    ensure_manage(actor)
    p = rend.periodo(mes)
    if p.en_curso:
        raise DomainError(
            "El mes todavía no termina: se calcula desde el primer día del mes siguiente."
        )
    cfg = get_config(db)
    calc = rend.Calculo(db, p)
    fecha = p.end - timedelta(minutes=1)
    bonos = grupal = 0
    modo = cfg["modalidad_coordinador"]
    sincronizar_cierres(db, actor)
    for u in db.scalars(select(User).where(User.is_active)).unique():
        perf = rend.perfil(u)
        if perf is None:
            continue
        if perf != "coordinacion" or modo in ("bono", "ambos"):
            total = calc.resultado(u).total
            ya = db.scalar(
                select(Bono).where(
                    Bono.beneficiario_id == u.id,
                    Bono.tipo == TipoBono.RENDIMIENTO,
                    Bono.periodo == p.first,
                )
            )
            if (
                ya is None
                and total is not None
                and total >= int(cfg["bono_umbral"])
                and int(cfg["bono_monto"]) > 0
            ):
                b = Bono(
                    beneficiario_id=u.id,
                    tipo=TipoBono.RENDIMIENTO,
                    concepto=f"Bono por rendimiento · {p.label}",
                    detalle=f"Resultado del mes {total} % (mínimo {cfg['bono_umbral']} %)",
                    valor=int(cfg["bono_monto"]),
                    fecha=fecha,
                    periodo=p.first,
                    rendimiento=total,
                    created_by_id=actor.id,
                )
                db.add(b)
                db.flush()
                _ev(
                    db,
                    "bono",
                    b.id,
                    "Bono generado",
                    actor,
                    None,
                    {"valor": b.valor, "rendimiento": total},
                )
                bonos += 1
        if perf == "coordinacion" and modo in ("grupal", "ambos"):
            ganancia = sum(
                c.ganancia or 0
                for c in db.scalars(
                    select(Cierre).where(
                        Cierre.estado == EstadoCierre.CERRADO,
                        Cierre.cerrado_at >= p.start,
                        Cierre.cerrado_at < p.end,
                    )
                ).unique()
            )
            ya = db.scalar(
                select(Comision).where(
                    Comision.beneficiario_id == u.id,
                    Comision.tipo == TipoComision.GRUPAL,
                    Comision.periodo == p.first,
                )
            )
            meta = int(cfg["meta_grupal"])
            if ya is None and ganancia >= meta and ganancia > 0:
                pct = float(cfg["pct_grupal"])
                com = Comision(
                    beneficiario_id=u.id,
                    tipo=TipoComision.GRUPAL,
                    concepto=f"Comisión por meta de facturación grupal · {p.label}",
                    detalle=f"El equipo dejó {money(ganancia)} de ganancia (meta {money(meta)}) × "
                    f"{pct_txt(pct)}",
                    base=ganancia,
                    porcentaje=Decimal(str(pct)),
                    valor=round(ganancia * pct / 100),
                    fecha=fecha,
                    periodo=p.first,
                    created_by_id=actor.id,
                )
                db.add(com)
                db.flush()
                _ev(
                    db,
                    "comision",
                    com.id,
                    "Comisión grupal generada",
                    actor,
                    None,
                    {"valor": com.valor},
                )
                grupal += 1
    db.flush()
    return {"bonos": bonos, "grupal": grupal}


# ---------------------------------------------------------------- approval flow


def _model(clase: str):
    if clase == "comision":
        return Comision
    if clase == "bono":
        return Bono
    raise NotFoundError("No existe.")


def get_item(db: Session, clase: str, item_id: uuid.UUID) -> Comision | Bono:
    item = db.get(_model(clase), item_id)
    if item is None:
        raise NotFoundError("No existe.")
    return item


def crear_manual(db: Session, clase: str, data: dict[str, Any], *, actor: User) -> Comision | Bono:
    ensure_manage(actor)
    u = db.get(User, data["beneficiario_id"])
    if u is None or not u.is_active or u.cargo == Cargo.GERENCIA:
        raise DomainError("Elige una persona activa del equipo.")
    concepto = (data.get("concepto") or "").strip()
    if len(concepto) < 3:
        raise DomainError("Escribe el concepto.")
    if int(data.get("valor") or 0) <= 0:
        raise DomainError("El valor debe ser mayor que $0.")
    fecha = data.get("fecha") or fechas.now()
    if fecha > fechas.now() + timedelta(days=1):
        raise DomainError("La fecha no puede ser futura.")
    common = {
        "beneficiario_id": u.id,
        "concepto": concepto,
        "detalle": (data.get("detalle") or "").strip() or f"Registrado por {actor.full_name}",
        "valor": int(data["valor"]),
        "fecha": fecha,
        "periodo": _periodo_de(fecha),
        "created_by_id": actor.id,
    }
    if clase == "comision":
        cierre_id = data.get("cierre_id")
        if cierre_id and db.get(Cierre, cierre_id) is None:
            raise DomainError("Ese negocio no existe.")
        item: Comision | Bono = Comision(tipo=TipoComision.MANUAL, cierre_id=cierre_id, **common)
    else:
        item = Bono(tipo=TipoBono.MANUAL, **common)
    db.add(item)
    db.flush()
    _ev(
        db,
        clase,
        item.id,
        f"Registrado a mano por {actor.full_name}",
        actor,
        None,
        {"valor": item.valor},
    )
    return item


def _anular(db: Session, clase: str, item, motivo: str, actor: User | None) -> None:
    antes = item.estado
    if item.pago_id and item.pago and item.pago.estado == EstadoPago.EN_PROCESO:
        pago = item.pago
        item.pago_id = None
        item.pago = None
        db.delete(pago)
    item.estado = E.ANULADA
    _ev(db, clase, item.id, f"Anulada · {motivo}", actor, {"estado": antes}, {"estado": "anulada"})


def accion(
    db: Session,
    clase: str,
    item: Comision | Bono,
    accion: str,
    *,
    actor: User,
    valor: int | None = None,
    motivo: str | None = None,
) -> Comision | Bono:
    """visto_bueno (Auxiliar) · aprobar, pagar (Gerencia) · ajustar, anular (both, with reason)."""
    ensure_manage(actor)
    motivo = (motivo or "").strip()
    labels = ESTADO_LABELS[clase]
    if accion == "visto_bueno":
        if not is_auxiliar(actor):
            raise PermissionDeniedError("El primer visto bueno lo da la Auxiliar administrativa.")
        _requiere(item, E.GENERADA, labels)
        item.estado = E.VISTO_BUENO
        _ev(
            db,
            clase,
            item.id,
            "Visto bueno de la Auxiliar",
            actor,
            {"estado": "generada"},
            {"estado": "visto_bueno"},
        )
    elif accion == "aprobar":
        if not is_gerencia(actor):
            raise PermissionDeniedError("Aprueba Gerencia, después del visto bueno de la Auxiliar.")
        _requiere(item, E.VISTO_BUENO, labels)
        cfg = get_config(db)
        pago = Pago(
            beneficiario_id=item.beneficiario_id,
            tipo=TipoPago.COMISION if clase == "comision" else TipoPago.BONO,
            concepto=f"Pago de {item.concepto[0].lower()}{item.concepto[1:]}",
            valor=item.valor,
            fecha_programada=fecha_pago_cb(item.periodo, cfg),
            estado=EstadoPago.EN_PROCESO,
        )
        db.add(pago)
        db.flush()
        item.pago_id = pago.id
        item.pago = pago
        item.estado = E.PENDIENTE_PAGO
        _ev(
            db,
            clase,
            item.id,
            f"Aprobada por Gerencia · se paga el {dia_mes(pago.fecha_programada)}",
            actor,
            {"estado": "visto_bueno"},
            {"estado": "pendiente_pago"},
        )
    elif accion == "pagar":
        if not is_gerencia(actor):
            raise PermissionDeniedError("El pago lo registra Gerencia.")
        _requiere(item, E.PENDIENTE_PAGO, labels)
        registrar_pago(db, item.pago, actor=actor)
    elif accion == "anular":
        if item.estado in (E.PAGADA, E.ANULADA):
            raise DomainError(f"Está {labels[item.estado].lower()}: ya no se puede anular.")
        if len(motivo) < 3:
            raise DomainError("Escribe el motivo para anular.")
        _anular(db, clase, item, motivo, actor)
    elif accion == "ajustar":
        if item.estado not in (E.GENERADA, E.VISTO_BUENO):
            raise DomainError("Solo se ajusta antes de la aprobación de Gerencia.")
        if not valor or valor <= 0:
            raise DomainError("El nuevo valor debe ser mayor que $0.")
        if len(motivo) < 3:
            raise DomainError("Escribe el motivo del ajuste.")
        antes = {"valor": item.valor, "estado": item.estado.value}
        item.valor = valor
        item.estado = E.GENERADA  # needs a new visto bueno
        item.detalle = f"{item.detalle or ''} · ajustado: {motivo}".strip(" ·")
        _ev(
            db,
            clase,
            item.id,
            f"Valor ajustado · {motivo}",
            actor,
            antes,
            {"valor": valor, "estado": "generada"},
        )
    else:
        raise DomainError("Acción no válida.")
    db.flush()
    return item


def _requiere(item, estado: EstadoCompensacion, labels) -> None:
    if item.estado != estado:
        raise DomainError(f"Está «{labels[item.estado]}»: no se puede hacer eso ahora.")


def registrar_pago(db: Session, pago: Pago | None, *, actor: User) -> Pago:
    """Gerencia records the transfer: the payment and what it pays become «Pagado»."""
    if not is_gerencia(actor):
        raise PermissionDeniedError("El pago lo registra Gerencia.")
    if pago is None:
        raise NotFoundError("No hay un pago programado.")
    if pago.estado == EstadoPago.PAGADO:
        raise DomainError("Este pago ya está registrado.")
    pago.estado = EstadoPago.PAGADO
    pago.pagado_at = fechas.now()
    pago.registrado_por_id = actor.id
    for model, clase in ((Comision, "comision"), (Bono, "bono")):
        for item in db.scalars(select(model).where(model.pago_id == pago.id)).unique():
            item.estado = E.PAGADA
            _ev(
                db,
                clase,
                item.id,
                "Pago registrado por Gerencia",
                actor,
                {"estado": "pendiente_pago"},
                {"estado": "pagada"},
            )
    db.flush()
    return pago


# ---------------------------------------------------------------- salaries


def set_salario(db: Session, user: User, mensual: int, *, actor: User) -> SalarioConfig:
    if not is_gerencia(actor):
        raise PermissionDeniedError("El salario de cada persona lo configura Gerencia.")
    if mensual <= 0:
        raise DomainError("El salario debe ser mayor que $0.")
    row = db.get(SalarioConfig, user.id)
    antes = row.salario_mensual if row else None
    if row is None:
        row = SalarioConfig(user_id=user.id, salario_mensual=mensual)
        db.add(row)
    row.salario_mensual = mensual
    row.updated_by_id = actor.id
    row.updated_at = fechas.now()
    _ev(
        db,
        "salario",
        user.id,
        f"Salario de {user.full_name}",
        actor,
        {"salario_mensual": antes},
        {"salario_mensual": mensual},
    )
    # Periods not confirmed yet take the new salary.
    for liq in db.scalars(
        select(LiquidacionSalario).where(
            LiquidacionSalario.user_id == user.id,
            LiquidacionSalario.estado == EstadoSalario.POR_CONFIRMAR,
        )
    ).unique():
        liq.salario_corte = mensual // 2
        novedades.aplicar(db, liq, mensual)
    db.flush()
    return row


def _corte_txt(liq: LiquidacionSalario) -> str:
    n = "1.er" if liq.corte == 1 else "2.º"
    return f"Salario · {n} corte de {rend.MESES[liq.periodo.month - 1]}"


def corte_fecha(periodo: date, corte: int, cfg: dict[str, Any]) -> date:
    return _clamp_day(periodo, int(cfg["dia_corte_1" if corte == 1 else "dia_corte_2"]))


def _ensure_liq(
    db: Session, user: User, mensual: int, periodo: date, corte: int
) -> LiquidacionSalario:
    liq = db.scalar(
        select(LiquidacionSalario).where(
            LiquidacionSalario.user_id == user.id,
            LiquidacionSalario.periodo == periodo,
            LiquidacionSalario.corte == corte,
        )
    )
    if liq is None:
        liq = LiquidacionSalario(
            user_id=user.id,
            periodo=periodo,
            corte=corte,
            salario_corte=mensual // 2,
            descuento=0,
            novedades=None,
            estado=EstadoSalario.POR_CONFIRMAR,
        )
        db.add(liq)
        db.flush()
    return liq


def liquidaciones(db: Session, actor: User, periodo: date, corte: int) -> list[LiquidacionSalario]:
    """X04: the period of every person with a configured salary (created on first look)."""
    ensure_manage(actor)
    if corte not in (1, 2):
        raise DomainError("El corte es 1 o 2.")
    out = []
    for row, u in db.execute(
        select(SalarioConfig, User)
        .join(User, User.id == SalarioConfig.user_id)
        .where(User.is_active)
        .order_by(User.full_name)
    ).all():
        liq = _ensure_liq(db, u, row.salario_mensual, periodo, corte)
        novedades.aplicar(db, liq, row.salario_mensual)  # absences (K13); unconfirmed only
        out.append(liq)
    db.flush()
    return out


def accion_salario(
    db: Session, liq: LiquidacionSalario, accion: str, *, actor: User
) -> LiquidacionSalario:
    ensure_manage(actor)
    if accion == "confirmar":
        if not is_auxiliar(actor):
            raise PermissionDeniedError(
                "El salario a pagar lo confirma la Auxiliar administrativa."
            )
        if liq.estado != EstadoSalario.POR_CONFIRMAR:
            raise DomainError(f"Está «{SALARIO_LABELS[liq.estado]}».")
        liq.estado = EstadoSalario.CONFIRMADO
        _ev(
            db,
            "liquidacion",
            liq.id,
            f"Salario confirmado · {money(liq.a_pagar)}",
            actor,
            {"estado": "por_confirmar"},
            {"estado": "confirmado"},
        )
    elif accion == "pagar":
        if not is_gerencia(actor):
            raise PermissionDeniedError("Gerencia aprueba y registra el pago del salario.")
        if liq.estado != EstadoSalario.CONFIRMADO:
            raise DomainError("Primero la Auxiliar confirma el salario a pagar.")
        cfg = get_config(db)
        pago = Pago(
            beneficiario_id=liq.user_id,
            tipo=TipoPago.SALARIO,
            concepto=_corte_txt(liq),
            valor=liq.a_pagar,
            fecha_programada=corte_fecha(liq.periodo, liq.corte, cfg),
            estado=EstadoPago.PAGADO,
            pagado_at=fechas.now(),
            registrado_por_id=actor.id,
        )
        db.add(pago)
        db.flush()
        liq.pago_id = pago.id
        liq.estado = EstadoSalario.PAGADO
        _ev(
            db,
            "liquidacion",
            liq.id,
            f"Salario pagado · {money(liq.a_pagar)}",
            actor,
            {"estado": "confirmado"},
            {"estado": "pagado"},
        )
    else:
        raise DomainError("Acción no válida.")
    db.flush()
    return liq


# ---------------------------------------------------------------- reads


def comisiones(
    db: Session, actor: User, *, desde: date | None = None, hasta: date | None = None
) -> list[Comision]:
    ensure_manage(actor)
    sincronizar_cierres(db, actor)
    return _list(db, Comision, None, desde, hasta)


def bonos(
    db: Session, actor: User, *, desde: date | None = None, hasta: date | None = None
) -> list[Bono]:
    ensure_manage(actor)
    return _list(db, Bono, None, desde, hasta)


def pagos(
    db: Session, actor: User, *, desde: date | None = None, hasta: date | None = None
) -> list[Pago]:
    ensure_manage(actor)
    q = select(Pago).order_by(Pago.fecha_programada.desc(), Pago.created_at.desc())
    if desde:
        q = q.where(Pago.fecha_programada >= desde)
    if hasta:
        q = q.where(Pago.fecha_programada <= hasta)
    return list(db.scalars(q).unique())


def _list(db: Session, model, user_id, desde, hasta):
    q = select(model).order_by(model.fecha.desc())
    if user_id:
        q = q.where(model.beneficiario_id == user_id)
    if desde:
        q = q.where(model.fecha >= fechas.start_of_day(desde))
    if hasta:
        q = q.where(model.fecha < fechas.start_of_day(hasta + timedelta(days=1)))
    return list(db.scalars(q).unique())


def historial(db: Session, actor: User, entidad: str, eid: str) -> list[CompensacionEvento]:
    ensure_manage(actor)
    return list(
        db.scalars(
            select(CompensacionEvento)
            .where(CompensacionEvento.entidad == entidad, CompensacionEvento.entidad_id == eid)
            .order_by(CompensacionEvento.created_at)
        ).unique()
    )


def se_paga(item: Comision | Bono, cfg: dict[str, Any]) -> str:
    if item.estado == E.ANULADA:
        return "—"
    d = item.pago.fecha_programada if item.pago else fecha_pago_cb(item.periodo, cfg)
    return f"Pagada el {dia_mes(d)}" if item.estado == E.PAGADA else dia_mes(d)


COMO_GANAS = {
    "asesor": [
        (
            "Salario de tu cargo",
            "En dos cortes: el {c1} y el {c2}. Las fechas las configura Gerencia.",
        ),
        (
            "Comisión por negocio",
            "Cuando se cierra un negocio en el que participaste: {pp} de la ganancia efectiva "
            "para el "
            "personal, repartido {rc} para quien cierra y {rk} para quien captó. "
            "Se paga el {dp} del "
            "mes siguiente.",
        ),
        (
            "Bono por rendimiento",
            "{bm} si tu resultado del mes llega a {bu}. Se paga el {dp} del mes siguiente.",
        ),
    ],
    "atencion": [
        (
            "Salario de tu cargo",
            "En dos cortes: el {c1} y el {c2}. Las fechas las configura Gerencia.",
        ),
        (
            "Comisión por cita que termina en negocio",
            "{pf} de la ganancia efectiva cuando una cita que programaste termina en venta "
            "o arriendo "
            "cerrado. Se paga el {dp} del mes siguiente.",
        ),
        (
            "Bono por rendimiento",
            "{bm} si tu resultado del mes llega a {bu}. Se paga el {dp} del mes siguiente.",
        ),
    ],
    "coordinacion": [
        (
            "Salario de tu cargo",
            "En dos cortes: el {c1} y el {c2}. Las fechas las configura Gerencia.",
        ),
        (
            "Comisión por meta grupal",
            "{pg} de la ganancia del equipo cuando el mes llega a {mg}. "
            "Se paga el {dp} del mes siguiente.",
        ),
        (
            "Bono individual por rendimiento",
            "{bm} si tu resultado del mes llega a {bu}. Se paga el {dp} del mes siguiente.",
        ),
    ],
    None: [
        (
            "Salario de tu cargo",
            "En dos cortes: el {c1} y el {c2}. Las fechas las configura Gerencia.",
        )
    ],
}


def mio(db: Session, user: User) -> dict[str, Any]:
    """«Mis pagos y bonos» (Z05) and «Mis comisiones / Mis bonos / Pagos» (M12–M14)."""
    sincronizar_cierres(db)
    cfg = get_config(db)
    perf = rend.perfil(user)
    hoy = fechas.local_date(fechas.now())
    # Salary periods of this month that have started.
    sal = db.get(SalarioConfig, user.id)
    if sal is not None and user.is_active:
        mes = hoy.replace(day=1)
        _ensure_liq(db, user, sal.salario_mensual, mes, 1)
        if hoy.day > int(cfg["dia_corte_1"]):
            _ensure_liq(db, user, sal.salario_mensual, mes, 2)
    rows: list[dict[str, Any]] = []
    for clase, model in (("comision", Comision), ("bono", Bono)):
        for it in _list(db, model, user.id, None, None):
            rows.append(
                {
                    "id": it.id,
                    "clase": clase,
                    "concepto": it.concepto,
                    "detalle": it.detalle or "",
                    "fecha": it.fecha,
                    "valor": it.valor,
                    "se_paga": se_paga(it, cfg),
                    "estado": it.estado.value,
                    "estado_txt": ESTADO_LABELS[clase][it.estado],
                }
            )
    for liq in db.scalars(
        select(LiquidacionSalario)
        .where(LiquidacionSalario.user_id == user.id)
        .order_by(LiquidacionSalario.periodo.desc(), LiquidacionSalario.corte.desc())
    ).unique():
        f = corte_fecha(liq.periodo, liq.corte, cfg)
        rows.append(
            {
                "id": liq.id,
                "clase": "salario",
                "concepto": _corte_txt(liq),
                "detalle": "Según tu cargo"
                + (f" · {liq.novedades}" if liq.novedades else " · sin novedades"),
                "fecha": fechas.start_of_day(f),
                "valor": liq.a_pagar,
                "se_paga": dia_mes(f),
                "estado": liq.estado.value,
                "estado_txt": SALARIO_LABELS[liq.estado],
            }
        )
    rows.sort(key=lambda r: r["fecha"], reverse=True)
    pagos_rows = [
        {
            "id": p.id,
            "concepto": p.concepto,
            "detalle": (
                "Transferencia · registrado por Gerencia el "
                + dia_mes(fechas.local_date(p.pagado_at))
                if p.estado == EstadoPago.PAGADO and p.pagado_at
                else f"Aprobado · se paga el {dia_mes(p.fecha_programada)}"
            ),
            "fecha": p.fecha_programada,
            "valor": p.valor,
            "tipo": p.tipo.value,
            "estado": p.estado.value,
            "estado_txt": PAGO_LABELS[p.estado],
        }
        for p in db.scalars(
            select(Pago)
            .where(Pago.beneficiario_id == user.id)
            .order_by(Pago.fecha_programada.desc())
        ).unique()
    ]
    pagado = sum(p["valor"] for p in pagos_rows if p["estado"] == "pagado")
    por_pagar = sum(r["valor"] for r in rows if r["estado"] not in ("pagada", "pagado", "anulada"))
    cb = sum(r["valor"] for r in rows if r["clase"] != "salario" and r["estado"] != "anulada")
    proximos = sorted(
        [r for r in rows if r["estado"] not in ("pagada", "pagado", "anulada")],
        key=lambda r: r["fecha"],
    )
    fmt = {
        "c1": int(cfg["dia_corte_1"]),
        "c2": int(cfg["dia_corte_2"]),
        "dp": int(cfg["dia_pago"]),
        "pp": pct_txt(cfg["pct_personal"]),
        "rc": pct_txt(cfg["reparto_cerrador"]),
        "rk": pct_txt(cfg["reparto_captador"]),
        "pf": pct_txt(cfg["pct_filtro"]),
        "pg": pct_txt(cfg["pct_grupal"]),
        "mg": money(cfg["meta_grupal"]),
        "bm": money(cfg["bono_monto"]),
        "bu": pct_txt(cfg["bono_umbral"]),
    }
    como = [{"titulo": t, "detalle": d.format(**fmt)} for t, d in COMO_GANAS[perf]]
    if sal is not None:
        como[0]["detalle"] = (
            f"{money(sal.salario_mensual)} al mes, "
            + como[0]["detalle"][0].lower()
            + como[0]["detalle"][1:]
        )
    return {
        "perfil": perf,
        "como_ganas": como,
        "salario_mensual": sal.salario_mensual if sal else None,
        "kpis": {
            "pagado": pagado,
            "por_pagar": por_pagar,
            "comisiones_bonos": cb,
            "proximo": proximos[0]["se_paga"] if proximos else None,
            "proximo_txt": proximos[0]["concepto"] if proximos else None,
        },
        "items": rows,
        "pagos": pagos_rows,
    }


def resumen(db: Session, actor: User) -> dict[str, Any]:
    """Totals for G05's three cards per tab."""
    ensure_manage(actor)
    out: dict[str, dict[str, int]] = {}
    for clase, model in (("comision", Comision), ("bono", Bono)):
        tot = {e.value: 0 for e in E}
        for it in db.scalars(select(model)).unique():
            tot[it.estado.value] += it.valor
        out[clase] = tot
    tp = {e.value: 0 for e in EstadoPago}
    for p in db.scalars(select(Pago)).unique():
        tp[p.estado.value] += p.valor
    out["pago"] = tp
    return out


def export_csv(db: Session, actor: User, tab: str) -> str:
    ensure_manage(actor)
    cfg = get_config(db)
    buf = io.StringIO()
    w = csv.writer(buf)
    if tab == "pagos":
        w.writerow(["Persona", "Concepto", "Tipo", "Fecha", "Valor", "Estado"])
        for p in pagos(db, actor):
            w.writerow(
                [
                    p.beneficiario.full_name,
                    p.concepto,
                    p.tipo.value,
                    p.fecha_programada.isoformat(),
                    p.valor,
                    PAGO_LABELS[p.estado],
                ]
            )
    else:
        clase = "comision" if tab == "comisiones" else "bono"
        w.writerow(["Persona", "Concepto", "Detalle", "Fecha", "Valor", "Se paga", "Estado"])
        for it in comisiones(db, actor) if clase == "comision" else bonos(db, actor):
            w.writerow(
                [
                    it.beneficiario.full_name,
                    it.concepto,
                    it.detalle or "",
                    fechas.local_date(it.fecha).isoformat(),
                    it.valor,
                    se_paga(it, cfg),
                    ESTADO_LABELS[clase][it.estado],
                ]
            )
    return "﻿" + buf.getvalue()
