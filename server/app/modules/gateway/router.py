from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ...db import get_db
from . import service

router = APIRouter(tags=["gateway"])


@router.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
async def gateway(request: Request, db: Session = Depends(get_db)):
    if request.method == "OPTIONS":
        return service.preflight()
    return await service.proxy(request, db)
