"""Recontact API entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.errors import install_error_handlers
from app.graph.db import connect
from app.graph.schema import apply_schema
from app.logging import RequestIdMiddleware, configure_logging
from app.main_version import VERSION
from app.routes.health import router as health_router
from app.routes.kb import router as kb_router

configure_logging()
log = logging.getLogger("recontact")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_settings()
    try:
        connect()
    except Exception:
        log.warning("starting with falkordb down")
    else:
        apply_schema()
    yield


def build_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="Recontact", version=VERSION, lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    application.add_middleware(RequestIdMiddleware)
    install_error_handlers(application)
    application.include_router(health_router)
    application.include_router(kb_router)
    return application


app = build_app()
