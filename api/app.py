"""FastAPI application factory."""

import hmac
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from config.settings import get_settings
from api.routes import tds as tds_router
from api.routes import gst as gst_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.output_dir).mkdir(parents=True, exist_ok=True)
    logger.info(f"CAA AI Service v{settings.app_version} started")
    yield
    logger.info("CAA AI Service shutting down")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


OPEN_PATHS = {"/health"}


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    """Only the backend may call this service: it must send the shared key in X-API-Key."""
    if request.method == "OPTIONS" or request.url.path in OPEN_PATHS:
        return await call_next(request)
    expected = settings.api_key
    if not expected:
        logger.error("API_KEY is not set: refusing every request. Set the same key in the backend's AI_ENGINE_API_KEY.")
        return JSONResponse({"detail": "Service not configured"}, status_code=503)
    given = request.headers.get("x-api-key", "")
    if not hmac.compare_digest(given.encode(), expected.encode()):
        return JSONResponse({"detail": "Unauthorized"}, status_code=401)
    return await call_next(request)


app.include_router(tds_router.router, prefix="/api/v1/tds", tags=["TDS"])
app.include_router(gst_router.router, prefix="/api/v1/gst", tags=["GST"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
