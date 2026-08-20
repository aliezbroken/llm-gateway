from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import get_current_user
from ...models import User
from ..tokens.service import get_scoped_user_id
from . import service

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _parse_dt(s: str) -> datetime:
    s = s.strip()
    if s[-1:] in ("Z", "z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)


def _parse_range(from_: str | None, to: str | None) -> tuple[datetime | None, datetime | None]:
    start = None
    end = None
    if from_:
        try:
            start = _parse_dt(from_)
        except ValueError:
            start = None
    if to:
        try:
            end = _parse_dt(to)
            if end.hour == 0 and end.minute == 0 and end.second == 0 and end.microsecond == 0:
                end = end + timedelta(days=1) - timedelta(microseconds=1)
        except ValueError:
            end = None
    return start, end


@router.get("/overview")
def overview_(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    userId: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = _parse_range(from_, to)
    return service.overview(db, start, end, get_scoped_user_id(user, userId))


@router.get("/trend")
def trend(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    granularity: str = Query("hour"),
    userId: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = _parse_range(from_, to)
    return service.trend(db, start, end, get_scoped_user_id(user, userId), granularity)


@router.get("/latency")
def latency(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    userId: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = _parse_range(from_, to)
    return service.latency_percentiles(db, start, end, get_scoped_user_id(user, userId))


@router.get("/distribution")
def distribution(
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
    by: str = Query("model"),
    userId: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start, end = _parse_range(from_, to)
    return service.distribution(db, start, end, get_scoped_user_id(user, userId), by)
