from fastapi import APIRouter

from app.api.routes import (
    administracion,
    agenda,
    asesor,
    auth,
    avisos,
    captaciones,
    citas,
    compensacion,
    configuracion,
    dashboard,
    health,
    inmuebles,
    integraciones,
    leads,
    movimientos,
    novedades,
    pedidos,
    perfil,
    plataformas,
    polizas,
    preoperacional,
    rendimiento,
    rutas,
    trazabilidad,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(leads.router)
api_router.include_router(citas.router)
api_router.include_router(captaciones.router)
api_router.include_router(dashboard.router)
api_router.include_router(asesor.router)
api_router.include_router(preoperacional.router)
api_router.include_router(pedidos.router)
api_router.include_router(rendimiento.router)
api_router.include_router(compensacion.router)
api_router.include_router(inmuebles.router)
api_router.include_router(administracion.router)
api_router.include_router(novedades.router)
api_router.include_router(movimientos.router)
api_router.include_router(plataformas.router)
api_router.include_router(configuracion.router)
api_router.include_router(avisos.router)
api_router.include_router(agenda.router)
api_router.include_router(perfil.router)
api_router.include_router(trazabilidad.router)
api_router.include_router(integraciones.router)
api_router.include_router(polizas.router)
api_router.include_router(rutas.router)
