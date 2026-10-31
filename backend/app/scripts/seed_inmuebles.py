"""Demo property catalog (called from app.scripts.seed, after captaciones).

* The approved captaciones join the catalog through the service (as when Coordinación approves).
* Their captadores complete the data of most quick captaciones; a few stay «datos incompletos».
* Properties the company already handled (the codes the prototypes use) are registered by hand by
  Coordinación, in different states. Owners and addresses are fictitious.
"""

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Inmueble
from app.models.enums import EstadoInmueble as S
from app.models.enums import TipoInmueble as T
from app.models.enums import TipoNegocio as N
from app.services import inmuebles as svc
from app.services.users import get_user_by_email

# codigo, negocio, tipo, direccion, zona, precio, m², hab, baños, parq, estrato, estado, nota
MANUALES = [
    (
        "INM-0318",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cl 30A # 76-41 apto 502",
        "Belén",
        2_100_000,
        70,
        3,
        2,
        True,
        4,
        S.SEPARADO,
        "Separado por Cliente Ejemplo 9 mientras sale el estudio",
    ),
    (
        "INM-0333",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cra 75 # 39-20 apto 301",
        "Laureles",
        2_300_000,
        74,
        3,
        2,
        True,
        5,
        S.DISPONIBLE,
        None,
    ),
    (
        "INM-0340",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cl 42 # 73-15 apto 201",
        "Laureles",
        1_900_000,
        60,
        2,
        1,
        False,
        4,
        S.DISPONIBLE,
        None,
    ),
    (
        "INM-0301",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cl 10 # 37-60 apto 904",
        "El Poblado",
        3_800_000,
        95,
        3,
        2,
        True,
        6,
        S.ARRENDADO,
        None,
    ),
    (
        "INM-0245",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cra 80 # 32-15 apto 103",
        "Belén",
        1_700_000,
        58,
        2,
        1,
        False,
        3,
        S.ARRENDADO,
        None,
    ),
    (
        "INM-0372",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cl 75 Sur # 43A-30 apto 1204",
        "Sabaneta",
        2_000_000,
        64,
        3,
        2,
        True,
        4,
        S.DISPONIBLE,
        None,
    ),
    (
        "INM-0219",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cl 34 # 81-50 apto 402",
        "Belén",
        1_800_000,
        62,
        2,
        2,
        True,
        4,
        S.DISPONIBLE,
        None,
    ),
    (
        "INM-0255",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cra 72 # 44-30 apto 601",
        "Laureles",
        2_600_000,
        80,
        3,
        2,
        True,
        5,
        S.DISPONIBLE,
        None,
    ),
    (
        "INM-0280",
        N.ARRIENDO,
        T.APARTAMENTO,
        "Cl 7 # 25-20 apto 1502",
        "El Poblado",
        4_500_000,
        110,
        3,
        3,
        True,
        6,
        S.RETIRADO,
        "El propietario decidió venderlo por su cuenta",
    ),
    (
        "INM-0310",
        N.ARRIENDO,
        T.LOCAL,
        "Cra 52 # 8B-40 local 2",
        "Guayabal",
        4_000_000,
        75,
        None,
        1,
        False,
        None,
        S.DISPONIBLE,
        None,
    ),
    (
        "INM-0290",
        N.VENTA,
        T.CASA,
        "Cl 37 Sur # 31-25",
        "Envigado",
        690_000_000,
        180,
        4,
        3,
        True,
        5,
        S.DISPONIBLE,
        None,
    ),
    (
        "INM-0342",
        N.VENTA,
        T.CASA,
        "Cra 45 # 70 Sur-80",
        "Sabaneta",
        520_000_000,
        150,
        3,
        3,
        True,
        4,
        S.SEPARADO,
        "Cliente Ejemplo 6 presentó oferta",
    ),
    (
        "INM-0288",
        N.VENTA,
        T.APARTAMENTO,
        "Cl 9 # 43-10 apto 701",
        "El Poblado",
        780_000_000,
        120,
        3,
        3,
        True,
        6,
        S.VENDIDO,
        None,
    ),
    (
        "INM-0350",
        N.VENTA,
        T.APARTAMENTO,
        "Cl 37 Sur # 39-10 apto 803",
        "Envigado",
        410_000_000,
        85,
        3,
        2,
        True,
        4,
        S.DISPONIBLE,
        None,
    ),
]
DUENOS = [
    "Rosa Elena Múnera",
    "Jorge Iván Restrepo",
    "Luz Marina Ochoa",
    "Hernán Darío Gómez",
    "Gloria Inés Arango",
    "Carlos Mario Vélez",
    "Beatriz Henao",
    "Fernando Zapata",
]


def seed_inmuebles(db: Session) -> int:
    # Approved captaciones may already be in the catalog (approval adds them), so look for ours.
    if db.scalar(select(Inmueble.id).where(Inmueble.codigo == MANUALES[1][0])):
        return 0
    coord = get_user_by_email(db, "coordinacion@example.com")
    if coord is None:
        raise RuntimeError("Seed the demo users first.")

    svc.sincronizar_captaciones(db)

    for i, (
        cod,
        neg,
        tipo,
        dir_,
        zona,
        precio,
        m2,
        hab,
        ban,
        parq,
        estr,
        estado,
        nota,
    ) in enumerate(MANUALES):
        inm = db.scalar(select(Inmueble).where(Inmueble.codigo == cod))
        datos = {
            "tipo_inmueble": tipo,
            "zona": zona,
            "precio": precio,
            "area_m2": Decimal(m2),
            "habitaciones": hab,
            "banos": ban,
            "parqueadero": parq,
            "estrato": estr,
            "administracion": None if neg == N.VENTA else round(precio * 0.08, -3),
            "descripcion": "Iluminado, cerca de transporte y comercio."
            if i % 2
            else "Buena vista, unidad con portería.",
            "propietario_nombre": DUENOS[i % len(DUENOS)],
            "propietario_telefono": f"300 555 {2100 + i:04d}",
        }
        if inm is None:
            inm = svc.crear(
                db, {"codigo": cod, "negocio": neg, "direccion": dir_, **datos}, actor=coord
            )
        else:  # it came from a quick captación: its captador completes it
            svc.actualizar(
                db,
                inm,
                {k: v for k, v in datos.items() if getattr(inm, k) in (None, "")},
                actor=inm.captador or coord,
            )
        if estado != S.DISPONIBLE:
            if estado in (S.ARRENDADO, S.VENDIDO) and inm.estado == S.DISPONIBLE and i % 2 == 0:
                svc.cambiar_estado(db, inm, S.SEPARADO, nota="Cliente firmando", actor=coord)
            svc.cambiar_estado(db, inm, estado, nota=nota, actor=coord)

    # Quick captaciones from the demo month: their captador completes most of them.
    rapidas = list(
        db.scalars(
            select(Inmueble).where(Inmueble.codigo.like("INM-7%")).order_by(Inmueble.codigo)
        ).unique()
    )
    for i, inm in enumerate(rapidas):
        if i % 9 == 4:
            continue  # stays «datos incompletos»
        venta = inm.negocio == N.VENTA
        tipo = [T.APARTAMENTO, T.APARTAMENTO, T.CASA, T.APARTAMENTO, T.LOCAL][i % 5]
        datos = {
            "tipo_inmueble": tipo,
            "zona": inm.zona or ["Laureles", "Envigado", "Belén", "El Poblado", "Sabaneta"][i % 5],
            "precio": (380_000_000 + 25_000_000 * (i % 9))
            if venta
            else (1_600_000 + 150_000 * (i % 12)),
            "area_m2": Decimal(55 + 7 * (i % 10)),
            "habitaciones": None if tipo == T.LOCAL else 2 + i % 3,
            "banos": 1 + i % 2,
            "parqueadero": i % 3 != 0,
            "propietario_nombre": DUENOS[(i + 3) % len(DUENOS)],
            "propietario_telefono": f"301 555 {3000 + i:04d}",
        }
        svc.actualizar(db, inm, datos, actor=inm.captador or coord)
        if i % 11 == 7:
            svc.cambiar_estado(db, inm, S.VENDIDO if venta else S.ARRENDADO, nota=None, actor=coord)
    db.flush()
    return db.scalar(select(func.count()).select_from(Inmueble)) or 0
