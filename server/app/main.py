import asyncio
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

from .config import BASE_DIR, settings
from .db import Base, SessionLocal, engine
from .models import QuotaLedger, User
from .modules.auth.router import router as auth_router
from .modules.gateway.router import router as gateway_router
from .modules.logs.router import router as logs_router
from .modules.stats.router import router as stats_router
from .modules.system import service as system_service
from .modules.system.router import router as system_router
from .modules.tokens.router import router as tokens_router
from .modules.users.router import router as users_router
from .security import hash_password

STATIC_DIR = Path(settings.static_dir)

WEAK_JWT = "change-me-in-production"


def ensure_strong_jwt_secret() -> None:
    """If JWT secret is still the weak default, generate a random one and persist to server/.env."""
    if settings.jwt_secret != WEAK_JWT:
        return
    secret = secrets.token_urlsafe(48)
    env_path = Path(BASE_DIR) / ".env"
    line = f"JWT_SECRET={secret}\n"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        if "JWT_SECRET=" in content:
            content = "\n".join(
                l for l in content.splitlines() if not l.startswith("JWT_SECRET=")
            ) + "\n"
        content = content.rstrip() + "\n" + line
    else:
        content = line
    env_path.write_text(content, encoding="utf-8")
    settings.jwt_secret = secret


def upstream_url_provider() -> str:
    with SessionLocal() as db:
        return system_service.get_upstream_url(db, settings.upstream_url)


def seed_admin() -> None:
    db = SessionLocal()
    try:
        if db.query(User).filter(User.username == settings.seed_admin_username).first() is not None:
            return
        admin = User(
            username=settings.seed_admin_username,
            password_hash=hash_password(settings.seed_admin_password),
            role="admin",
            status="active",
            quota=settings.seed_admin_quota,
            max_concurrency=0,
        )
        db.add(admin)
        db.flush()
        db.add(
            QuotaLedger(
                user_id=admin.id,
                operator_id=0,
                delta=settings.seed_admin_quota,
                balance_after=settings.seed_admin_quota,
                reason="init",
            )
        )
        db.commit()
    finally:
        db.close()


def migrate_sqlite() -> None:
    """Lightweight auto-migration for existing SQLite DBs (add columns).
    Skips on fresh databases (no tables yet); create_all() builds the schema."""
    with engine.connect() as conn:
        has_users = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        ).scalar()
        if not has_users:
            return
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(users)").fetchall()}
        if "max_concurrency" not in cols:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN max_concurrency INTEGER NOT NULL DEFAULT 0")
            conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_sqlite()
    Base.metadata.create_all(bind=engine)
    ensure_strong_jwt_secret()
    seed_admin()
    health_task = asyncio.create_task(
        system_service.health_loop(settings.health_check_interval, upstream_url_provider)
    )
    yield
    health_task.cancel()
    try:
        await health_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="LLM Gateway",
    lifespan=lifespan,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(tokens_router)
app.include_router(gateway_router)
app.include_router(logs_router)
app.include_router(stats_router)
app.include_router(system_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# Serve the built frontend (web/dist) directly - single process replaces nginx.
# Enabled automatically when web/dist exists; otherwise pure API mode.
if STATIC_DIR.is_dir():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(request: Request, full_path: str = ""):
        if full_path.startswith(("api/", "v1/")) or full_path in ("docs", "redoc", "openapi.json"):
            return Response(status_code=404)
        candidate = (STATIC_DIR / full_path).resolve()
        if (STATIC_DIR / full_path).is_file() and candidate.is_relative_to(STATIC_DIR):
            return FileResponse(candidate)
        index = STATIC_DIR / "index.html"
        if index.is_file():
            return FileResponse(index)
        return Response(status_code=404)
