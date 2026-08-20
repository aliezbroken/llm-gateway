import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...config import settings
from ...db import get_db
from ...deps import require_admin
from ...schemas.system import HealthOut, SystemSettingsOut, SystemSettingsUpdate
from . import service, state

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/settings", response_model=SystemSettingsOut)
def get_settings(db: Session = Depends(get_db)):
    ratios = service.get_model_ratios(db)
    return SystemSettingsOut(
        upstream_url=service.get_upstream_url(db, settings.upstream_url),
        model_ratios=ratios,
    )


@router.put("/settings", response_model=SystemSettingsOut)
def update_settings(data: SystemSettingsUpdate, admin=Depends(require_admin), db: Session = Depends(get_db)):
    if data.upstream_url is not None:
        service.set_setting(db, "upstream_url", data.upstream_url)
    if data.model_ratios is not None:
        service.set_setting(db, "model_ratios", json.dumps(data.model_ratios, ensure_ascii=False))
    return get_settings(db)


@router.get("/health", response_model=HealthOut)
async def health(db: Session = Depends(get_db)):
    upstream_url = service.get_upstream_url(db, settings.upstream_url)
    await service.do_health_check(upstream_url)
    return HealthOut(**state.snapshot())

