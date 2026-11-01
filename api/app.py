"""FastAPI application factory."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
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

app.include_router(tds_router.router, prefix="/api/v1/tds", tags=["TDS"])
app.include_router(gst_router.router, prefix="/api/v1/gst", tags=["GST"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.app_version}
