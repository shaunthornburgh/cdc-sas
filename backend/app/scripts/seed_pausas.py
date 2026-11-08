"""Demo pausas activas (G11), called from app.scripts.seed.

The example schedule (10:00 a. m. and 3:00 p. m., 15 minutes on screen) and about six weeks of
pauses for every active person: most marked a few minutes after the time, a handful missed so
the compliance isn't 100 %, and today's pauses that already passed. DATOS DE EJEMPLO.
"""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import PausaActiva, PausaConfig, User
from app.services import fechas
from app.services import pausas as svc


def seed_pausas(db: Session) -> int:
    if db.scalar(select(PausaActiva.id).limit(1)) is not None:
        return 0
    if db.get(PausaConfig, 1) is None:
        db.add(PausaConfig(id=1, **svc.DEFAULT))
        db.flush()
    c = svc.cfg(db)
    now = fechas.now()
    hoy = fechas.local_date(now)
    gente = list(db.scalars(select(User).where(User.is_active).order_by(User.email)).unique())
    n = 0
    for back in range(42, -1, -1):
        d = hoy - timedelta(days=back)
        if d.weekday() >= 5:
            continue
        for i, u in enumerate(gente):
            for k, turno in enumerate(svc.TURNOS):
                a, b = svc.ventana(c, d, turno)
                if b > now:  # not closed yet: leave it for the person
                    continue
                # A few missed pauses per person, spread over the weeks
                if (back * 7 + i * 3 + k * 5) % 11 == 0:
                    continue
                at = a + timedelta(minutes=1 + (back + i * 2 + k) % 9)
                db.add(
                    PausaActiva(
                        user_id=u.id,
                        fecha=d,
                        turno=turno,
                        programada=c.hora(turno),
                        realizada_at=at,
                    )
                )
                n += 1
    db.flush()
    return n
