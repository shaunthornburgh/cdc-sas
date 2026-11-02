"""Integraciones (prototype G07; decisions G-019, G-037, G-042 and «Integraciones · resultados»).

* **Solo Gerencia** sees and manages this page.
* **Groups** (G07): plataformas tradicionales (portals), redes sociales, canales y servicios.
* **Resultados** are real for lead sources: leads, cierres (arriendos / ventas), en proceso and the
  last lead come from the leads whose `fuente` is the platform. Cost: portals use their plans in
  «Plataformas tradicionales» (one source of truth); the others use the monthly cost registered
  here, spread over the days of the range (up to today). WhatsApp's usage = messages sent by
  WhatsApp recorded in the leads.
* **Conexión**: there are **no connectors yet**. «Guardar y conectar» saves what Gerencia typed and
  leaves it «Por confirmar conexión»; «Probar conexión» says honestly that there's no connector.
  Secrets are never stored: only a masked hint («••••1234»); G07: «no se pueden volver a ver».
* Every action is an `IntegracionEvento`, shown in «Registro de cambios».
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Integracion, IntegracionEvento, Lead, LeadEvento, Plataforma, User
from app.models.enums import (
    ETAPAS_CERRADAS,
    Cargo,
    EtapaLead,
    FuenteLead,
    TipoEventoLead,
    TipoNegocio,
)
from app.services import fechas
from app.services.errors import ConflictError, DomainError, NotFoundError, PermissionDeniedError

GRUPOS = {
    "trad": "Plataformas tradicionales",
    "red": "Redes sociales",
    "otro": "Canales y servicios",
}
ESTADOS = {
    "conectado": ("Conectado", "ok"),
    "por_confirmar": ("Por confirmar conexión", "pend"),
    "sin_conectar": ("Sin conectar", "gray"),
}
COMO = {
    "directa": "Conexión directa (si la plataforma la ofrece)",
    "correo": "Correo de avisos",
    "excel": "Carga desde Excel",
    "manual": "Registro a mano en Atención y Preventa",
    "por_confirmar": "Por confirmar con la plataforma",
}


@dataclass
class Campo:
    key: str
    label: str
    ph: str
    secreto: bool = False


@dataclass
class Def:
    clave: str
    nombre: str
    grupo: str
    que: str
    donde: str
    campos: list[Campo] = field(default_factory=list)
    fuente: FuenteLead | None = None
    nota: str | None = None  # services without leads
    uso_t: str | None = None
    nota_campos: str | None = None


_PORTAL = dict(
    que="Datos del interesado y el inmueble que vio",
    donde="Leads nuevos",
    campos=[
        Campo("usuario", "Usuario o código de cliente del portal", "Código asignado por el portal"),
        Campo("clave", "Clave de acceso (si el portal la ofrece)", "••••••••", True),
    ],
)
_META = "Nombre, teléfono, correo, interés y campaña de cada lead · costo de los anuncios"
CATALOGO: list[Def] = [
    Def("ciencuadras", "Ciencuadras", "trad", fuente=FuenteLead.CIENCUADRAS, **_PORTAL),
    Def("espacio_urbano", "Espacio Urbano", "trad", fuente=FuenteLead.ESPACIO_URBANO, **_PORTAL),
    Def("proppi", "Proppi", "trad", fuente=FuenteLead.PROPPI, **_PORTAL),
    Def("finca_raiz", "Finca Raíz", "trad", fuente=FuenteLead.FINCA_RAIZ, **_PORTAL),
    Def("metrocuadrado", "Metrocuadrado", "trad", fuente=FuenteLead.METROCUADRADO, **_PORTAL),
    Def(
        "facebook",
        "Facebook",
        "red",
        _META,
        "Leads nuevos · panel de Atención",
        [
            Campo("cuenta", "ID de la cuenta publicitaria (Meta)", "Ej: act_000000"),
            Campo("api", "Clave de acceso (API)", "••••••••", True),
            Campo("formularios", "Formularios a conectar", "Todos los formularios activos"),
        ],
        fuente=FuenteLead.FACEBOOK,
    ),
    Def(
        "instagram",
        "Instagram",
        "red",
        _META,
        "Leads nuevos · panel de Atención",
        [
            Campo("cuenta", "ID de la cuenta publicitaria (Meta)", "Ej: act_000000"),
            Campo("api", "Clave de acceso (API)", "••••••••", True),
        ],
        fuente=FuenteLead.INSTAGRAM,
    ),
    Def(
        "tiktok",
        "TikTok",
        "red",
        "Nombre, teléfono, interés y campaña de cada lead · costo de los anuncios",
        "Leads nuevos · panel de Atención",
        [
            Campo("cuenta", "ID de la cuenta de anuncios de TikTok", "Lo da TikTok"),
            Campo("api", "Clave de acceso (API)", "••••••••", True),
        ],
        fuente=FuenteLead.TIKTOK,
    ),
    Def(
        "correo_avisos",
        "Correo de avisos de portales",
        "otro",
        "Lee los correos de aviso de los portales y crea el lead",
        "Leads nuevos",
        [
            Campo("buzon", "Buzón de correo exclusivo para avisos", "avisos@correo.com"),
            Campo("clave", "Contraseña de aplicación", "••••••••", True),
        ],
        nota="Es un canal, no una fuente: trae los leads de los portales que no tienen conexión "
        "directa. Sus leads ya se cuentan en cada portal.",
        uso_t="Leads que llegaron por aquí",
    ),
    Def(
        "whatsapp",
        "WhatsApp Business",
        "otro",
        "Envía y recibe mensajes de los clientes",
        "Conversación del lead · recordatorios",
        [
            Campo("numero", "Número de WhatsApp Business", "+57 300 000 0000"),
            Campo("cuenta", "ID de la cuenta de WhatsApp Business", "Lo da Meta"),
            Campo("api", "Clave de acceso (API)", "••••••••", True),
        ],
        nota="No genera leads. Se usa para conversar con los clientes y enviar avisos.",
        uso_t="Mensajes por WhatsApp registrados en los leads",
    ),
    Def(
        "maps",
        "Google Maps",
        "otro",
        "Envía direcciones y recibe mapas, rutas y distancias",
        "Mi ruta · movimientos y GPS",
        [Campo("api", "Clave de acceso (API de Google)", "••••••••", True)],
        nota="No genera leads. Se usa para mapas, rutas y ubicación.",
        uso_t="Consultas de mapa",
    ),
    Def(
        "calendario",
        "Google Calendar / Outlook",
        "otro",
        "Envía citas y seguimientos al calendario de cada persona",
        "Mi agenda",
        [],
        nota="No genera leads. Pasa las citas al calendario personal.",
        uso_t="Personas conectadas",
        nota_campos="No pide datos aquí: cada persona autoriza su propio calendario "
        "desde «Mi agenda».",
    ),
    Def(
        "firma",
        "Firma electrónica",
        "otro",
        "Envía documentos para firmar y recibe su estado",
        "Detalle del negocio",
        [
            Campo("proveedor", "Proveedor de firma", "Por definir"),
            Campo("api", "Clave de acceso (API)", "••••••••", True),
        ],
        nota="No genera leads. Se usa para firmar contratos y promesas.",
        uso_t="Documentos firmados",
    ),
]
POR_CLAVE = {d.clave: d for d in CATALOGO}
_GENERICO = [
    Campo("usuario", "Usuario o código de cliente de la plataforma", "Lo da la plataforma"),
    Campo("clave", "Clave de acceso (si la plataforma la ofrece)", "••••••••", True),
]


def definicion(i: Integracion) -> Def:
    d = POR_CLAVE.get(i.clave)
    if d is not None:
        return d
    return Def(
        i.clave,
        i.nombre,
        i.grupo,
        "Datos de los interesados" if i.grupo != "otro" else "Por definir con la plataforma",
        "Por definir",
        _GENERICO,
        nota=None if i.grupo != "otro" else "Canal o servicio agregado por Gerencia.",
        uso_t=None if i.grupo != "otro" else "Uso",
    )


# ---------------------------------------------------------------- access


def ensure_gerencia(user: User) -> None:
    if not (user.is_active and user.cargo == Cargo.GERENCIA):
        raise PermissionDeniedError("Las integraciones solo las administra Gerencia.")


def asegurar_catalogo(db: Session) -> None:
    """Create G07's integrations that don't exist yet (fresh databases, tests)."""
    existentes = set(db.scalars(select(Integracion.clave)).all())
    for n, d in enumerate(CATALOGO):
        if d.clave not in existentes:
            db.add(
                Integracion(clave=d.clave, nombre=d.nombre, grupo=d.grupo, fuente=d.fuente, orden=n)
            )
    db.flush()


def todas(db: Session) -> list[Integracion]:
    asegurar_catalogo(db)
    return list(
        db.scalars(select(Integracion).order_by(Integracion.orden, Integracion.created_at)).unique()
    )


def get(db: Session, user: User, id_: uuid.UUID) -> Integracion:
    ensure_gerencia(user)
    i = db.get(Integracion, id_)
    if i is None:
        raise NotFoundError("Esa integración no existe.")
    return i


def _evento(
    db: Session, i: Integracion, accion: str, actor: User, antes=None, despues=None
) -> None:
    db.add(
        IntegracionEvento(
            integracion_id=i.id,
            accion=accion,
            antes=(str(antes)[:300] if antes is not None else None),
            despues=(str(despues)[:300] if despues is not None else None),
            actor_id=actor.id,
        )
    )


# ---------------------------------------------------------------- results


def _cop(v: float | int | None) -> str:
    return "—" if v is None else "$" + f"{round(v):,}".replace(",", ".")


def _dias(d1: date, d2: date) -> int:
    fin = min(d2, fechas.local_date(fechas.now()))
    return max(0, (fin - d1).days + 1)


def costo(db: Session, i: Integracion, d1: date, d2: date) -> float:
    """Portals: their plans (Plataformas tradicionales). The rest: the monthly cost, per day."""
    if i.fuente is not None:
        p = db.scalar(select(Plataforma).where(Plataforma.fuente == i.fuente))
        if p is not None and p.planes:
            from app.services import plataformas

            return plataformas.costo(p, d1, d2, fechas.local_date(fechas.now()))
    return (i.costo_mensual or 0) * _dias(d1, d2) / 30


def origen_costo(db: Session, i: Integracion) -> str:
    if i.fuente is not None:
        p = db.scalar(select(Plataforma).where(Plataforma.fuente == i.fuente))
        if p is not None and p.planes:
            return "Planes de «Plataformas tradicionales»"
    return "Costo mensual registrado aquí" if i.costo_mensual else "Sin costo registrado"


def resultados_leads(db: Session, i: Integracion, d1: date, d2: date) -> dict[str, Any]:
    t1, t2 = fechas.start_of_day(d1), fechas.start_of_day(d2 + timedelta(days=1))
    leads = (
        db.scalar(
            select(func.count()).where(
                Lead.fuente == i.fuente, Lead.created_at >= t1, Lead.created_at < t2
            )
        )
        or 0
    )
    cer = dict(
        db.execute(
            select(Lead.negocio, func.count())
            .where(
                Lead.fuente == i.fuente,
                Lead.etapa == EtapaLead.GANADO,
                Lead.cerrado_at >= t1,
                Lead.cerrado_at < t2,
            )
            .group_by(Lead.negocio)
        ).all()
    )
    arr, ven = cer.get(TipoNegocio.ARRIENDO, 0), cer.get(TipoNegocio.VENTA, 0)
    cerrados = sum(cer.values())
    proceso = (
        db.scalar(
            select(func.count()).where(
                Lead.fuente == i.fuente,
                Lead.created_at >= t1,
                Lead.created_at < t2,
                Lead.etapa.not_in(tuple(ETAPAS_CERRADAS)),
            )
        )
        or 0
    )
    ultimo = db.scalar(
        select(Lead).where(Lead.fuente == i.fuente).order_by(Lead.created_at.desc()).limit(1)
    )
    c = costo(db, i, d1, d2)
    return {
        "leads": leads,
        "costo": round(c),
        "costo_lead": round(c / leads) if leads else None,
        "cerrados": cerrados,
        "arriendos": arr,
        "ventas": ven,
        "sin_negocio": cerrados - arr - ven,
        "conversion": round(100 * cerrados / leads, 1) if leads else None,
        "costo_cierre": round(c / cerrados) if cerrados else None,
        "en_proceso": proceso,
        "ultimo": f"{fechas.fmt(ultimo.created_at)} · {ultimo.code}" if ultimo else None,
        "ultimo_at": ultimo.created_at if ultimo else None,
    }


def uso(db: Session, i: Integracion, d1: date, d2: date) -> str:
    """The usage figure of services without leads, where the app has it."""
    if i.clave == "whatsapp":
        t1, t2 = fechas.start_of_day(d1), fechas.start_of_day(d2 + timedelta(days=1))
        n = db.scalar(
            select(func.count()).where(
                LeadEvento.tipo.in_((TipoEventoLead.MENSAJE, TipoEventoLead.OPCIONES)),
                LeadEvento.datos["medio"].astext == "whatsapp",
                LeadEvento.created_at >= t1,
                LeadEvento.created_at < t2,
            )
        )
        return str(n or 0)
    if i.clave == "calendario":
        return "0"
    return "—"


def resumen(db: Session, i: Integracion, d1: date, d2: date) -> dict[str, Any]:
    e, cls = ESTADOS[i.estado]
    out = {
        "id": i.id,
        "clave": i.clave,
        "nombre": i.nombre,
        "grupo": i.grupo,
        "estado": i.estado,
        "estado_txt": e,
        "estado_cls": cls,
        "es_lead": i.fuente is not None,
    }
    if i.fuente is not None:
        r = resultados_leads(db, i, d1, d2)
        n_l, n_c = r["leads"], r["cerrados"]
        out["res"] = (
            f"{n_l} lead{'s' if n_l != 1 else ''} · {_cop(r['costo'])} · "
            f"{n_c} {'cerrado' if n_c == 1 else 'cerrados'}"
        )
        out["_r"] = r
    else:
        c = costo(db, i, d1, d2)
        out["res"] = f"Costo pagado {_cop(c)}"
        out["_c"] = c
    return out


def tablero(db: Session, user: User, d1: date, d2: date) -> dict[str, Any]:
    ensure_gerencia(user)
    if d1 > d2:
        raise DomainError("La fecha «Desde» no puede ser posterior a «Hasta».")
    items = [resumen(db, i, d1, d2) for i in todas(db)]
    rs = [x["_r"] for x in items if "_r" in x]
    leads = sum(r["leads"] for r in rs)
    costo_leads = sum(r["costo"] for r in rs)
    costo_total = costo_leads + sum(round(x["_c"]) for x in items if "_c" in x)
    cerrados = sum(r["cerrados"] for r in rs)
    for x in items:
        x.pop("_r", None)
        x.pop("_c", None)
    return {
        "desde": d1,
        "hasta": d2,
        "kpis": {
            "leads": leads,
            "costos": costo_total,
            "costo_lead": round(costo_leads / leads) if leads else None,
            "cerrados": cerrados,
            "conversion": round(100 * cerrados / leads, 1) if leads else None,
        },
        "grupos": [
            {"grupo": g, "titulo": t, "items": [x for x in items if x["grupo"] == g]}
            for g, t in GRUPOS.items()
        ],
    }


def detalle(db: Session, user: User, i: Integracion, d1: date, d2: date) -> dict[str, Any]:
    ensure_gerencia(user)
    d = definicion(i)
    base = resumen(db, i, d1, d2)
    r = base.pop("_r", None)
    c = base.pop("_c", None)
    plataforma = None
    if i.grupo == "trad" and i.fuente is not None:
        p = db.scalar(select(Plataforma).where(Plataforma.fuente == i.fuente))
        plataforma = (
            "Activa en «Plataformas tradicionales»"
            if p is not None and p.activa
            else "Inactiva en «Plataformas tradicionales»: actívala allá para que "
            "Coordinación la actualice"
        )
    campos = [
        {
            "key": f.key,
            "label": f.label,
            "ph": f.ph,
            "secreto": f.secreto,
            "valor": None if f.secreto else (i.datos or {}).get(f.key),
            "guardado": (i.secretos or {}).get(f.key) if f.secreto else None,
        }
        for f in d.campos
    ]
    ultimo = r["ultimo"] if r else None
    return base | {
        "resultados": r,
        "costo": round(c) if c is not None else (r["costo"] if r else 0),
        "origen_costo": origen_costo(db, i),
        "nota": d.nota,
        "uso_t": d.uso_t,
        "uso": None if r else uso(db, i, d1, d2),
        "conexion": {
            "que": d.que,
            "donde": d.donde,
            "ultimo_dato": ultimo or ("—" if i.estado != "conectado" else "Sin datos todavía"),
            "campos": campos,
            "nota_campos": d.nota_campos,
            "como": i.como,
            "como_txt": COMO.get(i.como, i.como),
            "costo_mensual": i.costo_mensual,
            "avisar_falla": i.avisar_falla,
            "prueba_at": i.prueba_at,
            "prueba_txt": i.prueba_txt,
            "plataforma": plataforma,
        },
    }


def historial(db: Session, i: Integracion, limit: int = 15) -> list[IntegracionEvento]:
    return list(
        db.scalars(
            select(IntegracionEvento)
            .where(IntegracionEvento.integracion_id == i.id)
            .order_by(IntegracionEvento.created_at.desc())
            .limit(limit)
        ).unique()
    )


# ---------------------------------------------------------------- commands


def _mask(v: str) -> str:
    return "••••" + (v[-4:] if len(v) >= 8 else "")


def guardar_datos(
    db: Session, i: Integracion, valores: dict[str, Any], *, actor: User
) -> Integracion:
    """«Guardar y conectar»: keeps the non-secret data and only a hint of the secrets. With no
    connector to confirm it, it stays «Por confirmar conexión»."""
    ensure_gerencia(actor)
    d = definicion(i)
    if not d.campos:
        raise DomainError(d.nota_campos or "Esta integración no pide datos aquí.")
    validos = {f.key: f for f in d.campos}
    if extra := set(valores) - set(validos):
        raise DomainError(f"No existe el dato «{sorted(extra)[0]}».")
    datos, secretos = dict(i.datos or {}), dict(i.secretos or {})
    cambiados = []
    for k, v in valores.items():
        v = (str(v) if v is not None else "").strip()
        if len(v) > 300:
            raise DomainError("Un dato es demasiado largo.")
        f = validos[k]
        if f.secreto:
            if v:  # empty = keep the one already saved
                secretos[k] = _mask(v)
                cambiados.append(f.label)
        elif datos.get(k) != (v or None):
            datos[k] = v or None
            cambiados.append(f.label)
    if not any(datos.values()) and not secretos:
        raise DomainError("Escribe al menos un dato para conectar.")
    if not cambiados and i.estado != "sin_conectar":
        return i
    antes = ESTADOS[i.estado][0]
    i.datos, i.secretos = datos, secretos
    if i.estado == "sin_conectar":
        i.estado = "por_confirmar"
    _evento(
        db,
        i,
        "Guardó los datos de conexión",
        actor,
        antes,
        f"{ESTADOS[i.estado][0]} · {', '.join(cambiados) or 'sin cambios'}",
    )
    db.flush()
    return i


def probar(db: Session, i: Integracion, *, actor: User) -> tuple[bool, str]:
    """There is no connector yet, so a test can't reach the platform: it says so."""
    ensure_gerencia(actor)
    if i.estado == "sin_conectar":
        raise DomainError("Primero guarda los datos para conectar.")
    txt = (
        f"Todavía no hay conector para {i.nombre}: no se pudo comprobar la conexión. "
        "Los datos quedan guardados para cuando se active."
    )
    i.prueba_at, i.prueba_txt = fechas.now(), txt
    _evento(db, i, "Probó la conexión", actor, None, "Sin conector todavía")
    db.flush()
    return False, txt


def desconectar(db: Session, i: Integracion, *, actor: User) -> Integracion:
    ensure_gerencia(actor)
    if i.estado == "sin_conectar":
        raise ConflictError("Ya está sin conectar.")
    antes = ESTADOS[i.estado][0]
    i.estado, i.datos, i.secretos, i.conectado_at = "sin_conectar", {}, {}, None
    i.prueba_at = i.prueba_txt = None
    _evento(db, i, "Desconectó la integración", actor, antes, "Sin conectar · datos borrados")
    db.flush()
    return i


def ajustes(db: Session, i: Integracion, data: dict[str, Any], *, actor: User) -> Integracion:
    """Monthly cost, how the data arrives, and «Avisar a Gerencia si la conexión falla»."""
    ensure_gerencia(actor)
    if "costo_mensual" in data:
        v = data["costo_mensual"]
        if v is not None and not 0 <= int(v) <= 1_000_000_000:
            raise DomainError("Revisa el costo mensual.")
        if v != i.costo_mensual:
            _evento(db, i, "Cambió el costo mensual", actor, _cop(i.costo_mensual), _cop(v))
            i.costo_mensual = v
    if "como" in data:
        if data["como"] not in COMO:
            raise DomainError("Elige cómo llegan los datos.")
        if data["como"] != i.como:
            _evento(
                db, i, "Cambió cómo llegan los datos", actor, COMO.get(i.como), COMO[data["como"]]
            )
            i.como = data["como"]
    if "avisar_falla" in data and data["avisar_falla"] != i.avisar_falla:
        i.avisar_falla = bool(data["avisar_falla"])
        _evento(
            db,
            i,
            "Avisar a Gerencia si la conexión falla",
            actor,
            None,
            "Sí" if i.avisar_falla else "No",
        )
    db.flush()
    return i


def agregar(db: Session, data: dict[str, Any], *, actor: User) -> Integracion:
    """G07 «+ Agregar integración». Queda «Por confirmar conexión» hasta probarla."""
    ensure_gerencia(actor)
    asegurar_catalogo(db)
    nombre = (data.get("nombre") or "").strip()
    if len(nombre) < 2:
        raise DomainError("Escribe el nombre de la plataforma.")
    grupo = data.get("grupo")
    if grupo not in GRUPOS:
        raise DomainError("Elige el grupo.")
    if db.scalar(select(Integracion.id).where(func.lower(Integracion.nombre) == nombre.lower())):
        raise ConflictError(f"Ya existe la integración «{nombre}».")
    como = data.get("como") or "por_confirmar"
    if como not in COMO:
        raise DomainError("Elige cómo llegan los datos.")
    costo_m = data.get("costo_mensual")
    if costo_m is not None and costo_m < 0:
        raise DomainError("Revisa el costo mensual.")
    orden = (db.scalar(select(func.max(Integracion.orden))) or 0) + 1
    i = Integracion(
        clave=f"n-{uuid.uuid4().hex[:8]}",
        nombre=nombre[:80],
        grupo=grupo,
        orden=orden,
        estado="por_confirmar",
        como=como,
        costo_mensual=costo_m,
        datos={"usuario": (data.get("usuario") or "").strip()[:200] or None},
        creado_por_id=actor.id,
    )
    db.add(i)
    db.flush()
    _evento(
        db,
        i,
        "Agregó la integración",
        actor,
        None,
        f"{GRUPOS[grupo]} · {ESTADOS['por_confirmar'][0]}",
    )
    db.flush()
    return i
