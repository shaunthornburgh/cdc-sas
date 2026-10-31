from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession
from app.api.permissions import USER_MANAGERS, require_cargo
from app.models import User
from app.schemas.dashboard import (
    CaptacionesSummary,
    CitasSummary,
    DashboardCoordinacion,
    Equipo,
    LeadsSummary,
)
from app.services import dashboard as service

# Coordinación and Gerencia only: everyone else gets 403.
router = APIRouter(prefix="/dashboard", tags=["dashboard"])
Manager = Annotated[User, Depends(require_cargo(*USER_MANAGERS))]


@router.get("/coordinacion", response_model=DashboardCoordinacion)
def coordinacion(db: DbSession, user: Manager) -> dict:
    """Everything the K01 dashboard shows, in one request."""
    return service.coordinacion(db, user)


@router.get("/leads", response_model=LeadsSummary)
def leads(db: DbSession, _: Manager) -> dict:
    return service.leads_summary(db)


@router.get("/citas", response_model=CitasSummary)
def citas(db: DbSession, _: Manager) -> dict:
    return service.citas_summary(db)


@router.get("/captaciones", response_model=CaptacionesSummary)
def captaciones(db: DbSession, _: Manager) -> dict:
    return service.captaciones_summary(db)


@router.get("/equipo", response_model=Equipo)
def equipo(db: DbSession, _: Manager) -> dict:
    return service.equipo(db)
