"""Configuración (prototypes Z02 / Z02-ger).

Settings Gerencia defines for the whole tool. Coordinación opens the page, reads the pay dates and
reaches its own settings through the cards (Z02: «Coordinación configura lo de su equipo»).

Sections stored here (table `configuracion`, one row per section, defaults below):

* **marca** - logo, company name, tagline and the three greens. The traffic-light colours never
  change. Read without login, because the login page shows it.
* **tarifas** - what the company charges (arriendo %, papelería, IVA, venta %, referidos,
  retención).
* **automatizaciones** - minutes before a lead without responsable alerts (used by the
  Coordinación dashboard), the daily summary time and escalation of urgent alerts.
* **idioma** - Spanish only for now.
* **leads** - points per lead ganado / perdido (rendimiento of Atención y Preventa) and the calls
  on consecutive days after which «No contesta» doesn't cost points (leads.perdida_descuenta).
* **produccion** - the «Pendientes para salir a producción» marked as defined, and «uso real».

«Fechas de pago al personal» isn't stored here: it reads and writes Compensación's config
(dia_corte_1, dia_corte_2, dia_pago), which «Salarios del mes» and «Comisiones» already use.

Every change is a `ConfigEvento` with who, when, and the values before and after.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConfigEvento, ConfigSeccion, MovimientosConfig, PlataformasConfig, User
from app.models.enums import Cargo
from app.services import fechas
from app.services.errors import ConflictError, DomainError, PermissionDeniedError

DEFAULTS: dict[str, dict[str, Any]] = {
    "marca": {
        "nombre": "CASA DOLCE CASA",
        "lema": "Confianza que construye hogares",
        "color_principal": "#00843D",
        "color_oscuro": "#0B3D23",
        "color_claro": "#8DC63F",
        "logo": None,  # data URL (PNG or SVG) or None = the built-in logo
    },
    "tarifas": {
        "arriendo_pct": 20.0,
        "papeleria": 75_000,
        "iva_pct": 19.0,
        "venta_pct": 3.0,
        "referidos_pct": 10.0,
        "retencion_pct": None,  # PENDIENTE DE CONFIGURACIÓN
    },
    "automatizaciones": {
        "lead_sin_responsable_min": 15,
        "resumen_diario": "07:30",
        "escalar_urgentes": True,
    },
    "idioma": {"idioma": "es"},
    "leads": {
        "puntos_ganado": 1.0,
        "puntos_perdido": 0.5,
        "llamadas_minimas": 3,
        "dias_seguidos": 3,
    },
    "produccion": {"resueltos": [], "uso_real": False, "uso_real_at": None, "uso_real_por": None},
    # Internal: the ISO week the «área por debajo del 60 %» check last ran (avisos).
    "avisos": {"semana_areas": None},
    # G-048/G-050 · edited by the Auxiliar and Gerencia in «Asistencia» (services/asistencia.py)
    "asistencia": {
        "entrada_lv": "08:00",
        "salida_lv": "18:00",
        "entrada_sab": "08:00",
        "salida_sab": "12:00",
        "limite_min": 30,  # entrada can be marked up to N minutes after its hour (15/30/45/60)
        "leve_max": 10,  # 1…N minutes late = leve; more = grave
        "recordatorio_min": 5,  # «Recuerda marcar salida» N minutes before
        "extra_min": 15,  # leaving N or more minutes after the hour = horas extra to review
        "radio_zona_m": 2000,  # route zones have no address: radius around the zone's center
        "exigir_preoperacional": True,
        "marcan": {
            "asesor": True,
            "atencion_cliente": True,
            "coordinacion": True,
            "auxiliar_administrativa": True,
            "gerencia": False,
        },
    },
}
EDITABLES = ("marca", "tarifas", "automatizaciones", "idioma", "leads")
SECCION_LABELS = {
    "marca": "Marca de la empresa",
    "tarifas": "Tarifas de intermediación",
    "automatizaciones": "Automatizaciones y avisos",
    "idioma": "Idioma",
    "leads": "Leads ganados y perdidos",
    "produccion": "Pendientes para salir a producción",
    "pagos": "Fechas de pago al personal",
    "registro_cambios": "Registro de cambios",
    "asistencia": "Asistencia y puntualidad",
}
OPCIONES = {
    "puntos_ganado": [0.5, 1.0, 1.5, 2.0],
    "puntos_perdido": [0.25, 0.5, 0.75],
    "llamadas_minimas": [2, 3, 4, 5],
    "dias_seguidos": [2, 3, 4, 5],
    "lead_sin_responsable_min": [5, 10, 15, 30],
    "resumen_diario": ["07:00", "07:30", "08:00"],
}
IDIOMAS = {"es": "Español", "en": "English (inglés)", "it": "Italiano"}
IDIOMAS_DISPONIBLES = ("es",)  # the others need the translations (pending)
MAX_LOGO = 200_000  # characters of the data URL (~150 KB file)
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_LOGO = re.compile(r"^data:image/(png|svg\+xml);base64,[A-Za-z0-9+/=]+$")

# «Pendientes para salir a producción» (Z02-ger, G-053). Some resolve on their own once the value
# is set somewhere; the rest Gerencia marks as defined.
PENDIENTES_MANUALES = [
    (
        "metas",
        "Metas reales de cada área",
        "Ventas, arriendos, captación, Atención, Coordinador y Auxiliar",
        "Gerencia",
        "/rendimiento",
    ),
    (
        "comisiones",
        "Porcentajes de comisión y de cada parte en ventas",
        "Comisiones y bonos (D-008)",
        "Gerencia",
        "/compensacion",
    ),
    ("etapas", "Etapas definitivas de venta y de arriendo", "Hoy son de ejemplo", "Gerencia", None),
    (
        "documentos",
        "Documentos obligatorios de una captación",
        "Formulario completo de captación",
        "Gerencia",
        "/captaciones",
    ),
    (
        "salario",
        "Fórmulas de salario e incapacidad",
        "Deducciones de ley, auxilio de transporte, incapacidades y descuento por impuntualidad",
        "Contador y abogado",
        "/salarios",
    ),
    (
        "gps_legal",
        "Retención de ubicaciones y validación legal del GPS",
        "D-006",
        "Abogado",
        "/movimientos",
    ),
    (
        "polizas",
        "Tipos de póliza, aseguradoras y recordatorios",
        "Pólizas",
        "Gerencia",
        "/polizas",
    ),
]


# ---------------------------------------------------------------- access


def can_view(user: User) -> bool:
    return user.is_active and user.cargo in (Cargo.GERENCIA, Cargo.COORDINACION)


def can_edit(user: User) -> bool:
    return user.is_active and user.cargo == Cargo.GERENCIA


def ensure_view(user: User) -> None:
    if not can_view(user):
        raise PermissionDeniedError("La configuración la abren Coordinación y Gerencia.")


def ensure_edit(user: User) -> None:
    if not can_edit(user):
        raise PermissionDeniedError("Esto solo lo cambia Gerencia.")


# ---------------------------------------------------------------- read / write


def get(db: Session, seccion: str) -> dict[str, Any]:
    row = db.get(ConfigSeccion, seccion)
    return DEFAULTS[seccion] | ((row.valores if row else {}) or {})


def _row(db: Session, seccion: str) -> ConfigSeccion | None:
    return db.get(ConfigSeccion, seccion)


def _save(db: Session, seccion: str, new: dict[str, Any], actor: User, detalle: str | None = None):
    cur = get(db, seccion)
    cambios = {k: v for k, v in new.items() if cur.get(k) != v}
    if not cambios:
        return cur
    row = _row(db, seccion)
    if row is None:
        row = ConfigSeccion(seccion=seccion, valores={})
        db.add(row)
    # Only what differs from the default is stored, so new defaults reach untouched values.
    merged = cur | cambios
    row.valores = {k: v for k, v in merged.items() if DEFAULTS[seccion].get(k) != v}
    row.updated_by_id, row.updated_by = actor.id, actor
    row.updated_at = fechas.now()
    antes = {k: _resumen(k, cur.get(k)) for k in cambios}
    despues = {k: _resumen(k, v) for k, v in cambios.items()}
    ev = ConfigEvento(
        seccion=seccion, actor_id=actor.id, antes=antes, despues=despues, detalle=detalle
    )
    ev.actor = actor
    db.add(ev)
    db.flush()
    return merged


def _resumen(k: str, v: Any) -> Any:
    """Logos are big: the history keeps only whether there was one."""
    if k == "logo":
        return "logo propio" if v else "logo de Casa Dolce Casa"
    return v


def _num(v: Any, label: str, *, minimo: float = 0, maximo: float | None = None) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise DomainError(f"Revisa «{label}»: debe ser un número.") from None
    if x < minimo or (maximo is not None and x > maximo):
        rango = (
            f"de {minimo:g} a {maximo:g}" if maximo is not None else f"mayor o igual a {minimo:g}"
        )
        raise DomainError(f"«{label}» va {rango}.")
    return x


def guardar(db: Session, seccion: str, valores: dict[str, Any], *, actor: User) -> dict[str, Any]:
    ensure_edit(actor)
    if seccion not in EDITABLES:
        raise DomainError("Esa sección no existe.")
    if extra := set(valores) - set(DEFAULTS[seccion]):
        raise DomainError(f"No existe el valor «{sorted(extra)[0]}».")
    new = get(db, seccion) | valores
    _VALIDAR[seccion](new)
    return _save(db, seccion, new, actor)


def _v_marca(m: dict[str, Any]) -> None:
    m["nombre"] = (m.get("nombre") or "").strip()
    m["lema"] = (m.get("lema") or "").strip()
    if not m["nombre"]:
        raise DomainError("Escribe el nombre de la empresa.")
    if len(m["nombre"]) > 40 or len(m["lema"]) > 80:
        raise DomainError("El nombre va hasta 40 caracteres y la frase hasta 80.")
    for k in ("color_principal", "color_oscuro", "color_claro"):
        if not _HEX.match(str(m.get(k) or "")):
            raise DomainError("Los colores van en formato #RRGGBB.")
        m[k] = m[k].upper()
    logo = m.get("logo")
    if logo is not None:
        if not isinstance(logo, str) or not _LOGO.match(logo):
            raise DomainError("El logo debe ser una imagen PNG o SVG.")
        if len(logo) > MAX_LOGO:
            raise DomainError("El logo es muy pesado: usa uno de menos de 150 KB.")


def _v_tarifas(t: dict[str, Any]) -> None:
    for k, label, maximo in (
        ("arriendo_pct", "Arriendo · comisión", 100),
        ("iva_pct", "IVA", 100),
        ("venta_pct", "Venta · comisión por defecto", 100),
        ("referidos_pct", "Pago a referidos", 100),
    ):
        t[k] = _num(t[k], label, maximo=maximo)
    t["papeleria"] = int(_num(t["papeleria"], "Arriendo · papelería", maximo=10_000_000))
    if t.get("retencion_pct") in ("", None):
        t["retencion_pct"] = None
    else:
        t["retencion_pct"] = _num(t["retencion_pct"], "Retención en la fuente", maximo=100)


def _v_auto(a: dict[str, Any]) -> None:
    if a["lead_sin_responsable_min"] not in OPCIONES["lead_sin_responsable_min"]:
        raise DomainError("Elige los minutos de la lista.")
    if a["resumen_diario"] not in OPCIONES["resumen_diario"]:
        raise DomainError("Elige la hora del resumen de la lista.")
    if not isinstance(a["escalar_urgentes"], bool):
        raise DomainError("Elige si se escala o no.")


def _v_idioma(i: dict[str, Any]) -> None:
    if i["idioma"] not in IDIOMAS:
        raise DomainError("Ese idioma no existe.")
    if i["idioma"] not in IDIOMAS_DISPONIBLES:
        raise DomainError("La traducción a ese idioma todavía no está hecha.")


def _v_leads(rl: dict[str, Any]) -> None:
    """«Se elige de las listas, no se escribe. El perdido siempre descuenta menos de lo que suma
    un ganado.» (Z02-ger)."""
    for k in ("puntos_ganado", "puntos_perdido", "llamadas_minimas", "dias_seguidos"):
        if rl[k] not in OPCIONES[k]:
            raise DomainError("Elige los valores de las listas.")
    if rl["puntos_perdido"] >= rl["puntos_ganado"]:
        raise DomainError("El perdido siempre descuenta menos de lo que suma un ganado.")


_VALIDAR = {
    "marca": _v_marca,
    "tarifas": _v_tarifas,
    "automatizaciones": _v_auto,
    "idioma": _v_idioma,
    "leads": _v_leads,
}


def restaurar_marca(db: Session, *, actor: User) -> dict[str, Any]:
    ensure_edit(actor)
    return _save(
        db, "marca", dict(DEFAULTS["marca"]), actor, detalle="Volvió a la marca de Casa Dolce Casa"
    )


# ---------------------------------------------------------------- pay dates (Compensación's config)


def pagos(db: Session) -> dict[str, int]:
    from app.services import compensacion as comp  # compensación → rendimiento → this module

    c = comp.get_config(db)
    return {k: int(c[k]) for k in ("dia_corte_1", "dia_corte_2", "dia_pago")}


def guardar_pagos(db: Session, valores: dict[str, int], *, actor: User) -> dict[str, int]:
    from app.services import compensacion as comp

    ensure_edit(actor)
    if valores.get("dia_corte_1", 1) > 28 or valores.get("dia_pago", 1) > 28:
        raise DomainError("El 1.er corte y el pago de comisiones van del día 1 al 28.")
    antes = pagos(db)
    comp.set_config(db, valores, actor=actor)
    despues = pagos(db)
    if antes != despues:
        ev = ConfigEvento(
            seccion="pagos",
            actor_id=actor.id,
            antes={k: v for k, v in antes.items() if despues[k] != v},
            despues={k: v for k, v in despues.items() if antes[k] != v},
        )
        ev.actor = actor
        db.add(ev)
        db.flush()
    return despues


# ---------------------------------------------------------------- pendientes para producción


def pendientes(db: Session) -> list[dict[str, Any]]:
    resueltos = set(get(db, "produccion")["resueltos"])
    mov = db.get(MovimientosConfig, 1)
    plat = db.get(PlataformasConfig, 1)
    auto = [
        (
            "gps_plazo",
            "Plazo para justificar alertas de GPS",
            "Sin plazo no se puede aplicar el descuento por alerta sin justificar",
            "Gerencia",
            "/movimientos",
            mov is not None and mov.plazo_horas is not None,
        ),
        (
            "plataformas_regla",
            "Cada cuántos días se actualizan las plataformas",
            "Hoy se usa 7 días como valor de ejemplo",
            "Gerencia",
            "/plataformas",
            plat is not None and plat.confirmada,
        ),
        (
            "retencion",
            "Retención en la fuente al propietario",
            "Tarifas de intermediación, en esta página",
            "Gerencia",
            None,
            get(db, "tarifas")["retencion_pct"] is not None,
        ),
    ]
    out = [
        {
            "clave": k,
            "titulo": t,
            "detalle": d,
            "quien": q,
            "link": link,
            "resuelto": ok,
            "manual": False,
        }
        for k, t, d, q, link, ok in auto
    ]
    out += [
        {
            "clave": k,
            "titulo": t,
            "detalle": d,
            "quien": q,
            "link": link,
            "resuelto": k in resueltos,
            "manual": True,
        }
        for k, t, d, q, link in PENDIENTES_MANUALES
    ]
    return out


def marcar_pendiente(
    db: Session, clave: str, resuelto: bool, *, actor: User
) -> list[dict[str, Any]]:
    ensure_edit(actor)
    if clave not in {k for k, *_ in PENDIENTES_MANUALES}:
        raise DomainError("Ese pendiente se resuelve en su propio ajuste.")
    prod = get(db, "produccion")
    res = set(prod["resueltos"])
    res = res | {clave} if resuelto else res - {clave}
    _save(db, "produccion", prod | {"resueltos": sorted(res)}, actor)
    return pendientes(db)


def activar_uso_real(db: Session, *, actor: User) -> dict[str, Any]:
    ensure_edit(actor)
    prod = get(db, "produccion")
    if prod["uso_real"]:
        raise ConflictError("El uso real ya está activado.")
    faltan = [p["titulo"] for p in pendientes(db) if not p["resuelto"]]
    if faltan:
        raise ConflictError(f"Faltan {len(faltan)} pendientes: {faltan[0]}…")
    return _save(
        db,
        "produccion",
        prod
        | {
            "uso_real": True,
            "uso_real_at": fechas.now().isoformat(),
            "uso_real_por": actor.full_name,
        },
        actor,
        detalle="Uso real activado",
    )


def cambios(db: Session, limit: int = 15) -> list[ConfigEvento]:
    return list(
        db.scalars(
            select(ConfigEvento).order_by(ConfigEvento.created_at.desc()).limit(limit)
        ).unique()
    )
