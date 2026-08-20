from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models import QuotaLedger, UsageLog, User


def base_query(db: Session, from_ts, to_ts, scope_user_id: int | None):
    q = db.query(UsageLog)
    if from_ts is not None:
        q = q.filter(UsageLog.ts >= from_ts)
    if to_ts is not None:
        q = q.filter(UsageLog.ts <= to_ts)
    if scope_user_id is not None:
        q = q.filter(UsageLog.user_id == scope_user_id)
    return q


def total_distributed_quota(db: Session) -> int:
    """Sum of all positive quota grants (init + admin grants) ever distributed."""
    return db.query(func.coalesce(func.sum(QuotaLedger.delta), 0)).filter(QuotaLedger.delta > 0).scalar() or 0


def overview(db: Session, from_ts, to_ts, scope_user_id: int | None) -> dict:
    q = base_query(db, from_ts, to_ts, scope_user_id)
    requests, total_tokens, quota_cost, avg_latency = q.with_entities(
        func.count(UsageLog.id),
        func.coalesce(func.sum(UsageLog.total_tokens), 0),
        func.coalesce(func.sum(UsageLog.quota_cost), 0),
        func.coalesce(func.avg(UsageLog.latency_ms), 0),
    ).first()
    return {
        "requests": requests,
        "total_tokens": total_tokens,
        "quota_cost": quota_cost,
        "avg_latency_ms": round(avg_latency, 2),
        "total_distributed_quota": total_distributed_quota(db),
    }


def trend(db: Session, from_ts, to_ts, scope_user_id: int | None, granularity: str) -> dict:
    if granularity == "hour":
        bucket = func.strftime("%Y-%m-%dT%H", UsageLog.ts)
    else:
        bucket = func.strftime("%Y-%m-%d", UsageLog.ts)
    q = base_query(db, from_ts, to_ts, scope_user_id)
    rows = q.with_entities(
        bucket.label("bucket"),
        func.count(UsageLog.id),
        func.coalesce(func.sum(UsageLog.total_tokens), 0),
        func.coalesce(func.sum(UsageLog.quota_cost), 0),
    ).group_by(bucket).order_by(bucket).all()
    return {
        "labels": [r[0] for r in rows],
        "requests": [r[1] for r in rows],
        "tokens": [r[2] for r in rows],
        "quota": [r[3] for r in rows],
    }


def latency_percentiles(db: Session, from_ts, to_ts, scope_user_id: int | None) -> dict:
    q = base_query(db, from_ts, to_ts, scope_user_id).filter(UsageLog.status == "ok")
    values = [r[0] for r in q.with_entities(UsageLog.latency_ms).all()]
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    values.sort()

    def pct(percent: float) -> float:
        idx = (len(values) - 1) * percent
        lo = int(idx)
        hi = min(lo + 1, len(values) - 1)
        frac = idx - lo
        return values[lo] + (values[hi] - values[lo]) * frac

    return {"p50": round(pct(0.5), 2), "p95": round(pct(0.95), 2), "p99": round(pct(0.99), 2)}


def distribution(db: Session, from_ts, to_ts, scope_user_id: int | None, by: str) -> list[dict]:
    value_col = func.coalesce(func.sum(UsageLog.total_tokens), 0)
    q = base_query(db, from_ts, to_ts, scope_user_id)
    if by == "user":
        rows = q.join(User, User.id == UsageLog.user_id).with_entities(
            User.username.label("name"), value_col.label("value")
        ).group_by(User.username, UsageLog.user_id).order_by(value_col.desc()).all()
        return [{"name": r[0], "value": r[1]} for r in rows]

    if by == "token":
        unames = {uid: uname for uid, uname in db.query(User.id, User.username).all()}
        rows = q.with_entities(
            UsageLog.token_name, UsageLog.user_id, value_col.label("value")
        ).group_by(UsageLog.token_name, UsageLog.user_id).order_by(value_col.desc()).all()
        return [
            {"name": f"{unames.get(uid, uid)}: {tname}", "value": v}
            for tname, uid, v in rows
        ]

    rows = q.with_entities(
        UsageLog.model.label("name"), value_col.label("value")
    ).group_by(UsageLog.model).order_by(value_col.desc()).all()
    return [{"name": r[0], "value": r[1]} for r in rows]
