"""
ExceptionLoop API — v0.5.0
Operational control plane for AI agent exceptions.
"""

import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from database import engine, Base
from routers.workspaces import router as workspaces_router
from routers.intake import router as intake_router
from routers.enrichment import router as enrichment_router
from routers.resolutions import router as resolutions_router
from routers.clusters import router as clusters_router

import models  # noqa: F401 — registers all ORM models with Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("exceptionloop")

APP_ENV = os.getenv("APP_ENV", "development")
IS_PROD = APP_ENV == "production"

# Validate required env vars at startup
_REQUIRED = ["DATABASE_URL", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
_missing = [k for k in _REQUIRED if not os.getenv(k)]
if _missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(_missing)}")

# CORS — comma-separated list in production, permissive in dev
_cors_raw = os.getenv("ALLOWED_ORIGINS", "")
if _cors_raw:
    ALLOWED_ORIGINS = [o.strip() for o in _cors_raw.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:3001"] if not IS_PROD else []


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting ExceptionLoop API (env=%s)", APP_ENV)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables verified via create_all")
    yield
    await engine.dispose()
    logger.info("ExceptionLoop API shutdown complete")


app = FastAPI(
    title="ExceptionLoop",
    description="Operational control plane for AI agent exceptions.",
    version="0.5.0",
    docs_url=None if IS_PROD else "/docs",
    redoc_url=None if IS_PROD else "/redoc",
    openapi_url=None if IS_PROD else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspaces_router)
app.include_router(intake_router)
app.include_router(enrichment_router)
app.include_router(resolutions_router)
app.include_router(clusters_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "exceptionloop-api", "version": "0.5.0", "env": APP_ENV}
