"""Demo capacitaciones (X07 · Z03), called from app.scripts.seed.

The prototype's examples, with dates relative to today: three upcoming trainings programmed by
Gerencia, Coordinación and the Auxiliar with a mix of answers (accepted, pending, can't with a
reason); one that already happened with its attendance marked; one that happened yesterday still
waiting for attendance (so the organizer has the aviso); and four the team registered themselves.
All are DATOS DE EJEMPLO.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Capacitacion
from app.services import capacitaciones as svc
from app.services import fechas
from app.services.users import get_user_by_email


def _d(k: int) -> date:
    return fechas.local_date(fechas.now()) + timedelta(days=k)


def seed_capacitaciones(db: Session) -> int:
    if db.scalar(select(Capacitacion.id).limit(1)) is not None:
        return 0
    keys = ("gerencia", "coordinacion", "auxiliar", "asesor", "bruno", "carla", "diego")
    u = {k: get_user_by_email(db, f"{k}@example.com") for k in (*keys, "atencion", "preventas")}
    if any(v is None for v in u.values()):
        raise RuntimeError("Seed the demo users first.")
    ger, coord, aux = u["gerencia"], u["coordinacion"], u["auxiliar"]

    def prog(actor, k, hora, area, tema, presenta, lugar, part="todo", personas=()):
        c = svc.programar(
            db,
            {
                "fecha": _d(max(k, 1)),
                "hora": time(hora),
                "area": area,
                "tema": tema,
                "presenta": presenta,
                "lugar": lugar,
                "participantes": part,
                "personas": [p.id for p in personas],
            },
            actor=actor,
        )
        if k < 1:  # one that already happened: programmed earlier, moved back
            c.inicio_at = datetime.combine(_d(k), time(hora), tzinfo=fechas.BOGOTA)
        return c

    def resp(c, who, motivo=None):
        svc.responder(db, c, acepta=motivo is None, motivo=motivo, detalle=None, actor=u[who])

    # Upcoming
    c1 = prog(
        ger,
        2,
        8,
        "Todas las áreas",
        "Uso del software: seguimientos y agenda",
        ger.full_name,
        "Sala de reuniones",
    )
    for w in ("asesor", "carla", "coordinacion", "auxiliar", "preventas"):
        resp(c1, w)
    resp(c1, "diego", "Cita con cliente a esa hora")
    c2 = prog(
        coord,
        14,
        8,
        "Comercial",
        "Cómo presentar un inmueble en la cita",
        coord.full_name,
        "Sala de reuniones",
        part="com",
    )
    resp(c2, "asesor")
    resp(c2, "carla")
    c3 = prog(
        aux,
        9,
        15,
        "Seguridad y salud en el trabajo",
        "Pausas activas y cuidado postural",
        "Proveedor externo (ejemplo)",
        "Enlace de videollamada",
    )
    for w in ("diego", "coordinacion", "auxiliar"):
        resp(c3, w)
    # Happened, attendance marked
    c4 = prog(
        aux,
        -6,
        8,
        "Comercial",
        "Manejo de objeciones en arriendos",
        coord.full_name,
        "Sala de reuniones",
        part="com",
    )
    for w in ("asesor", "bruno", "carla"):
        resp(c4, w)
    resp(c4, "diego", "Incapacidad o permiso")
    svc.completar(db, c4, [u[w].id for w in ("asesor", "bruno", "carla")], actor=aux)
    svc.aprendizaje(
        db,
        c4,
        "Responder dudas de precio y requisitos con ejemplos reales.",
        None,
        actor=u["asesor"],
    )
    # Happened yesterday, attendance still to mark (aviso for the Auxiliar)
    c5 = prog(
        aux,
        -1,
        9,
        "Atención y Preventa",
        "Protocolo de atención telefónica",
        ger.full_name,
        "Sala de reuniones",
        part="ate",
    )
    resp(c5, "atencion")

    # Registered by the team (Z03 «Registrar participación»)
    regs = [
        (
            "atencion",
            -12,
            16,
            "Comercial",
            "Fotos que venden en portales",
            "Proveedor externo (ejemplo)",
            "Luz natural, orden y foto de fachada primero.",
        ),
        (
            "asesor",
            -9,
            14,
            "Comercial",
            "Negociación de arriendos (curso externo)",
            "Entidad externa (ejemplo)",
            "Preparar 3 opciones antes de la cita.",
        ),
        (
            "carla",
            -7,
            10,
            "Comercial",
            "Requisitos de estudio de arrendatario",
            "Aseguradora (ejemplo)",
            "Documentos que piden y tiempos de respuesta.",
        ),
        (
            "auxiliar",
            -5,
            15,
            "Administrativa",
            "Novedades de nómina electrónica",
            "Proveedor contable (ejemplo)",
            "Fechas de reporte y soportes.",
        ),
    ]
    for who, k, hora, area, tema, presenta, aprendio in regs:
        svc.registrar(
            db,
            {
                "fecha": _d(k),
                "hora": time(hora),
                "area": area,
                "tema": tema,
                "presenta": presenta,
                "aprendio": aprendio,
            },
            actor=u[who],
        )
    db.flush()
    return 5 + len(regs)
