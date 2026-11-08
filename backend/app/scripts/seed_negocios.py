"""Demo negocios (X02 · M16), in two steps.

1. ``valores`` (called by the compensación seed, before it registers each deal's ganancia): a
   canon or a sale price for every deal, so the ganancia efectiva comes from Gerencia's tariffs.
2. ``seed_negocios`` (called from app.scripts.seed after pólizas): deals that already have a
   ganancia, and the platform leads won without an asesor, are closed (signature confirmed by the
   Auxiliar on the day the lead was won), rentals
   take the property of their policy, and a few new deals go through the services so every state
   of X02 shows up: a promesa and a contract to confirm, a sale in escrituración with money
   received and a notary appointment, a request returned to the asesor, a caída reported by the
   asesor and one confirmed. Dates are relative to today. All are DATOS DE EJEMPLO.
"""

from datetime import datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Cierre, CompensacionEvento, Inmueble, Lead, NegocioAbono, Poliza
from app.models.enums import EstadoCierre, EtapaLead, FuenteLead, TipoNegocio
from app.services import compensacion as comp
from app.services import configuracion, fechas
from app.services import negocios as svc
from app.services.users import get_user_by_email

CANONES = (1_600_000, 1_800_000, 2_100_000, 1_500_000, 2_400_000, 1_700_000, 2_600_000)
PRECIOS = (390_000_000, 300_000_000, 420_000_000, 350_000_000, 480_000_000)
DOCS = (
    "Carpeta física A-12 · archivador de la oficina principal",
    "Drive · Negocios/2026/{code}",
    "Carpeta física B-05",
    "Notaría 2 de Envigado + carpeta B-03",
)


def _at(d, hour=10) -> datetime:
    return datetime.combine(d, time(hour), tzinfo=fechas.BOGOTA)


def valores(db: Session, deals: list[Cierre]) -> None:
    """A canon or price for each deal that has none (step 1)."""
    ia = iv = 0
    for c in sorted(deals, key=lambda x: x.numero):
        if c.valor:
            continue
        if c.negocio == TipoNegocio.VENTA:
            c.valor = PRECIOS[iv % len(PRECIOS)]
            iv += 1
        else:
            c.valor = CANONES[ia % len(CANONES)]
            ia += 1
    db.flush()


def _valor_desde_ganancia(c: Cierre, t: dict) -> int:
    """Databases seeded before «Negocios»: the value that gives the ganancia already registered."""
    g = c.ganancia or 0
    if c.negocio == TipoNegocio.VENTA:
        return round(g / (float(t["venta_pct"]) / 100), -6)
    base_pap = float(t["papeleria"]) / (1 + float(t["iva_pct"]) / 100)
    return round(max(g - base_pap, 300_000) / (float(t["arriendo_pct"]) / 100), -4)


def _lead(db: Session, k: int, nombre: str, negocio: TipoNegocio, dias: int, busca: str, atencion):
    ld = Lead(
        full_name=nombre,
        phone=f"30055501{k:02d}",
        fuente=FuenteLead.FACEBOOK if negocio == TipoNegocio.VENTA else FuenteLead.OTRO,
        negocio=negocio,
        busca=busca,
        etapa=EtapaLead.GANADO,
        cerrado_at=fechas.now() - timedelta(days=dias),
        assigned_to_id=atencion.id if atencion else None,
    )
    db.add(ld)
    db.flush()
    return ld


def seed_negocios(db: Session) -> int:
    if db.scalar(select(NegocioAbono.id).limit(1)) is not None:
        return 0
    u = {
        k: get_user_by_email(db, f"{k}@example.com")
        for k in ("auxiliar", "asesor", "carla", "diego", "atencion")
    }
    if any(v is None for v in u.values()):
        raise RuntimeError("Seed the demo users first.")
    aux = u["auxiliar"]
    hoy = svc.hoy()
    comp.sincronizar_cierres(db, aux)
    deals = list(db.scalars(select(Cierre).order_by(Cierre.numero)).unique())
    t = configuracion.get(db, "tarifas")
    for c in deals:
        if not c.valor:
            c.valor = _valor_desde_ganancia(c, t) if c.ganancia else None
    valores(db, deals)

    # Rentals: the property of their policy; sales: a sale property, in order
    pol = {p.cierre_id: p for p in db.scalars(select(Poliza)).unique() if p.cierre_id}
    inm_venta = list(
        db.scalars(
            select(Inmueble).where(Inmueble.negocio == TipoNegocio.VENTA).order_by(Inmueble.codigo)
        ).unique()
    )
    iv = 0
    for k, c in enumerate(deals):
        p = pol.get(c.id)
        if c.negocio == TipoNegocio.ARRIENDO and p is not None and p.inmueble_id:
            c.inmueble_id = p.inmueble_id
        elif c.negocio == TipoNegocio.VENTA and inm_venta:
            c.inmueble_id = inm_venta[iv % len(inm_venta)].id
            iv += 1
        if k % 4 != 3:
            c.docs_ubicacion = DOCS[k % len(DOCS)].format(code=c.code)

    # Deals with a ganancia, and the platform leads won without an asesor (Plataformas seed):
    # closed on the day the lead was won
    n = 0
    sin_asesor = []
    for k, c in enumerate(deals):
        if c.estado != EstadoCierre.CERRADO or not (c.ganancia or c.cerrador_id is None):
            continue
        if not c.ganancia:
            sin_asesor.append(c)
        dia = fechas.local_date(c.cerrado_at)
        etapas = comp.etapas_de(c.negocio)
        c.firma_fecha = dia
        c.etapa = etapas[-1]
        c.confirmado_por_id = aux.id
        c.contrato_adjunto = k % 3 != 0
        if c.negocio == TipoNegocio.VENTA:
            c.promesa_fecha = dia - timedelta(days=20)
            db.add(
                NegocioAbono(
                    cierre_id=c.id,
                    valor=c.valor,
                    fecha=dia,
                    momento="escritura",
                    soporte=True,
                    created_by_id=aux.id,
                )
            )
        db.add(
            CompensacionEvento(
                entidad="cierre",
                entidad_id=str(c.id),
                accion=(
                    "Firma de la escritura confirmada · negocio cerrado"
                    if c.negocio == TipoNegocio.VENTA
                    else "Firma confirmada · negocio cerrado"
                ),
                despues={"fecha": svc._fd(dia)},
                created_by_id=aux.id,
                created_at=_at(dia, 16),
            )
        )
        n += 1
    db.flush()
    for c in sin_asesor:  # nobody took part: the ganancia is registered, without commissions
        svc.enviar_ganancia(db, c, aux)

    # The open ones the earlier seeds left (the two newest with an asesor)
    abiertos = [
        c
        for c in deals
        if c.estado == EstadoCierre.CERRADO and c.firma_fecha is None and c.cerrador_id
    ]
    for k, c in enumerate(abiertos[:2]):
        ase = c.cerrador
        siguiente = comp.etapas_de(c.negocio)[1]
        svc.pasar_etapa(
            db,
            c,
            {"etapa": siguiente, "observacion": "El cliente está listo para firmar"},
            actor=ase,
        )
        svc.solicitar(db, c, "El cliente firmó hoy", actor=ase)
        if k == 1:
            svc.devolver(db, c, "La póliza no está aprobada", actor=aux)
        n += 1

    # New deals for the remaining states
    nuevos = [
        # (cliente, tipo, días desde el lead ganado, busca, asesor, canon o precio)
        ("Cliente Ejemplo 11", TipoNegocio.VENTA, 25, "Apto en Envigado", "asesor", 390_000_000),
        ("Cliente Ejemplo 4", TipoNegocio.VENTA, 33, "Casa en Envigado", "diego", 420_000_000),
        ("Cliente Ejemplo 6", TipoNegocio.VENTA, 9, "Casa en Sabaneta", "asesor", 480_000_000),
        ("Cliente Ejemplo 2", TipoNegocio.ARRIENDO, 14, "Apto en Laureles", "carla", 1_800_000),
    ]
    creados = []
    for k, (nombre, tipo, dias, busca, _quien, _valor) in enumerate(nuevos):
        _lead(db, k, nombre, tipo, dias, busca, u["atencion"])
    comp.sincronizar_cierres(db, aux)
    for nombre, _tipo, _dias, _busca, quien, valor in nuevos:
        c = db.scalar(select(Cierre).join(Lead).where(Lead.full_name == nombre))
        c.cerrador_id = u[quien].id
        c.valor = valor
        db.flush()
        db.refresh(c)
        creados.append(c)
    promesa, escritura, desiste, caido = creados
    a_, d_ = u["asesor"], u["diego"]
    # A sale whose promesa is waiting for the Auxiliar
    svc.pasar_etapa(
        db,
        promesa,
        {
            "etapa": "Promesa firmada",
            "oferta": "Ofrece $380.000.000 · entrega en 60 días",
            "observacion": "Firmaron la promesa en la oficina",
        },
        actor=a_,
    )
    svc.solicitar(db, promesa, "El cliente firmó la promesa", actor=a_)
    # A sale with the promesa confirmed, money received and the notary in two days
    svc.pasar_etapa(
        db,
        escritura,
        {
            "etapa": "Promesa firmada",
            "oferta": "Ofreció $410.000.000 (pide $420.000.000)",
            "observacion": "Cliente aceptó la contraoferta",
        },
        actor=d_,
    )
    svc.solicitar(db, escritura, None, actor=d_)
    svc.confirmar(
        db,
        escritura,
        fecha=hoy - timedelta(days=10),
        contrato_adjunto=True,
        observacion=None,
        actor=aux,
    )
    svc.abono(
        db,
        escritura,
        {
            "valor": 42_000_000,
            "fecha": hoy - timedelta(days=10),
            "momento": "promesa",
            "soporte": True,
        },
        actor=aux,
    )
    svc.pasar_etapa(
        db,
        escritura,
        {
            "etapa": "Escrituración",
            "observacion": "Documentos completos para escriturar",
            "notaria": "Notaría 2 de Envigado",
            "notaria_at": _at(hoy + timedelta(days=2)),
        },
        actor=d_,
    )
    # A sale the asesor reported as fallen, waiting for the Auxiliar
    desiste.pct_venta = 2
    svc.pasar_etapa(
        db,
        desiste,
        {
            "oferta": "Ofrece $465.000.000 (pide $480.000.000)",
            "observacion": "Primera oferta del comprador",
        },
        actor=a_,
    )
    svc.caida(db, desiste, "El cliente desistió", "El comprador desistió de la compra", actor=a_)
    # A rental fallen and confirmed
    svc.caida(db, caido, "Póliza negada", "La aseguradora negó el estudio dos veces", actor=aux)
    db.flush()
    return n + len(creados)
