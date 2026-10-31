"""Demo preoperacionales (called from app.scripts.seed): ~30 business days of history.

Deterministic: each person has a fixed medio and plate, a couple of missed days and the odd
novedad (older ones already reviewed). Today mirrors K09: one novedad, one person missing.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Preoperacional
from app.models.enums import MEDIOS_CON_VEHICULO
from app.models.enums import MedioTransporte as M
from app.services import fechas
from app.services import preoperacional as svc
from app.services.users import get_user_by_email

# email prefix → (medio, placa, days ago (business) missed, days ago with novedad)
PERFILES = {
    "gerencia": (M.CARRO, "GHI789", set(), set()),
    "coordinacion": (M.CARRO, "DEF456", set(), set()),
    "asesor": (M.CARRO, "ABC123", {0, 6, 13}, {9}),  # today not done (like Juan in K09)
    "bruno": (M.MOTO, "KLM78F", set(), {0, 11}),  # today: frenos con ruido
    "carla": (M.TRANSPORTE_PUBLICO, None, {4, 15}, set()),
    "diego": (M.CARRO, "XYZ987", {8}, set()),
    "atencion": (M.A_PIE, None, set(), set()),
    "preventas": (M.BICICLETA, None, {2}, {5}),
    "auxiliar": (M.TRANSPORTE_PUBLICO, None, {12}, set()),
}
NOVEDADES = {
    M.MOTO: (2, "Frenos con ruido, la llevo al taller esta semana."),
    M.CARRO: (2, "Llanta trasera baja, la inflé antes de salir."),
    M.BICICLETA: (None, "La cadena se salió dos veces en el camino."),
}


def _business_days_back(n: int) -> list:
    out, d = [], svc.hoy()
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d -= timedelta(days=1)
    return out  # index 0 = today (or last business day)


def seed_preoperacional(db: Session) -> int:
    if db.scalar(select(func.count()).select_from(Preoperacional)):
        return 0
    coord = get_user_by_email(db, "coordinacion@example.com")
    ger = get_user_by_email(db, "gerencia@example.com")
    dias = _business_days_back(30)
    for prefix, (medio, placa, faltas, novedades) in PERFILES.items():
        user = get_user_by_email(db, f"{prefix}@example.com")
        if user is None:
            continue
        for i, d in enumerate(dias):
            if i in faltas:
                continue
            minute = (sum(map(ord, prefix)) * 7 + i * 13) % 40 + 30  # 7:30–8:09, stable
            at = datetime.combine(d, time(7, 0), tzinfo=fechas.BOGOTA) + timedelta(minutes=minute)
            respuestas, obs = [], None
            if medio in MEDIOS_CON_VEHICULO:
                respuestas = [{"pregunta": q, "si": True} for q in svc.PREGUNTAS[medio]]
            if i in novedades:
                idx, obs = NOVEDADES.get(medio, (None, "Novedad en el desplazamiento."))
                if idx is not None and respuestas:
                    respuestas[idx]["si"] = False
            pre = Preoperacional(
                user_id=user.id,
                fecha=d,
                realizado_at=at,
                medio=medio,
                placa=placa,
                respuestas=respuestas,
                observaciones=obs,
                tiene_novedad=bool(obs) or any(not r["si"] for r in respuestas),
            )
            if pre.tiene_novedad and i > 0:  # older novedades were already reviewed
                reviewer = ger if prefix == "coordinacion" else coord
                pre.revisado_por_id = reviewer.id
                pre.revisado_at = at + timedelta(hours=2)
                pre.revision_nota = "Revisada con la persona."
            db.add(pre)
    db.flush()
    return db.scalar(select(func.count()).select_from(Preoperacional)) or 0
