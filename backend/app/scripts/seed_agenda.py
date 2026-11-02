"""Demo assigned activities (G09 agenda, G-088), called from app.scripts.seed after seed_avisos.

G09's examples between people: Coordinación → asesores and Atención y Preventa, the Auxiliar → an
asesor, Gerencia → Coordinación and the Auxiliar. One was rejected with a reason and one was deleted
by whoever put it, so «Actividades eliminadas» has an entry. Personal items come from seed_avisos.
"""

from datetime import time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgendaItem
from app.services import fechas
from app.services.users import get_user_by_email

# by, for, days from today, time, title, note, priority, (state, reason) | None, deleted
ASIGNADAS = [
    (
        "coordinacion",
        "asesor",
        0,
        time(17, 0),
        "Actualizar las fotos de INM-0333 en Proppi",
        None,
        "alta",
        None,
        False,
    ),
    (
        "coordinacion",
        "carla",
        0,
        time(12, 0),
        "Llamar al propietario de INM-0350 para la visita",
        None,
        "normal",
        None,
        False,
    ),
    (
        "coordinacion",
        "atencion",
        1,
        time(10, 0),
        "Revisar respuestas pendientes de LD-1095",
        None,
        "normal",
        None,
        False,
    ),
    (
        "auxiliar",
        "bruno",
        4,
        time(10, 0),
        "Visita de control a INM-0262 con el arrendatario",
        "Llevar el acta de entrega",
        "normal",
        None,
        False,
    ),
    (
        "gerencia",
        "coordinacion",
        3,
        time(9, 0),
        "Reunión con Gerencia · revisar captación de noviembre",
        None,
        "alta",
        None,
        False,
    ),
    (
        "gerencia",
        "auxiliar",
        2,
        time(15, 0),
        "Revisar las pólizas por activar",
        "Arriendos firmados sin póliza activa",
        "normal",
        None,
        False,
    ),
    (
        "coordinacion",
        "carla",
        5,
        time(8, 30),
        "Captación en Envigado el sábado",
        None,
        "normal",
        ("rechazada", "Tengo permiso aprobado ese día"),
        False,
    ),
    (
        "coordinacion",
        "asesor",
        2,
        time(11, 0),
        "Volantes en la portería de INM-0371",
        None,
        "normal",
        None,
        True,
    ),
]


def seed_agenda(db: Session) -> int:
    if db.scalar(
        select(AgendaItem.id).where(AgendaItem.creado_por_id != AgendaItem.user_id).limit(1)
    ):
        return 0
    emails = {x for row in ASIGNADAS for x in row[:2]}
    u = {k: get_user_by_email(db, f"{k}@example.com") for k in emails}
    if None in u.values():
        raise RuntimeError("Seed the demo users first.")
    now = fechas.now()
    hoy = fechas.local_date(now)
    for por, para, dias, hora, titulo, nota, prio, respuesta, borrada in ASIGNADAS:
        it = AgendaItem(
            user_id=u[para].id,
            creado_por_id=u[por].id,
            fecha=hoy + timedelta(days=dias),
            hora=hora,
            titulo=titulo,
            nota=nota,
            prioridad=prio,
            estado="pendiente",
        )
        it.created_at = now - timedelta(hours=20)
        if respuesta:
            it.estado, it.motivo = respuesta
            it.respondida_at = now - timedelta(hours=2)
        if borrada:
            it.eliminado_at, it.eliminado_por_id = now - timedelta(hours=1), u[por].id
        db.add(it)
    db.flush()
    return (
        db.scalar(
            select(func.count())
            .select_from(AgendaItem)
            .where(AgendaItem.creado_por_id != AgendaItem.user_id)
        )
        or 0
    )
