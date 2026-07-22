from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import time

from app.config import settings
from app.database import create_tables

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Application Lifespan
# ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):

    logger.info("🚀 FYP Repository API starting...")

    # Only create tables during development
    # Production uses Alembic migrations
    if settings.app_env == "development":
        create_tables()

    yield

    logger.info("🛑 FYP Repository API stopped.")



# ─────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Final Year Project Topic Repository REST API",

    # Keep Swagger enabled for Render
    docs_url="/docs",
    redoc_url="/redoc",

    lifespan=lifespan,
)



# ─────────────────────────────────────────────
# CORS
# ─────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ─────────────────────────────────────────────
# Request Timing Middleware
# ─────────────────────────────────────────────

@app.middleware("http")
async def add_request_timing(request: Request, call_next):

    start = time.perf_counter()

    response = await call_next(request)

    duration = (time.perf_counter() - start) * 1000

    response.headers["X-Process-Time"] = f"{duration:.2f}ms"

    return response



# ─────────────────────────────────────────────
# Global Error Handler
# ─────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception
):

    logger.exception("Unhandled exception: %s", exc)

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "message": "An unexpected error occurred.",
            "errors": [str(exc)] if settings.debug else []
        },
    )



# ─────────────────────────────────────────────
# Root Endpoint
# ─────────────────────────────────────────────

@app.get("/")
def root():

    return {
        "success": True,
        "message": "FYP Topic Repository API is running",
        "environment": settings.app_env,
        "docs": "/docs"
    }



# ─────────────────────────────────────────────
# Routers
# ─────────────────────────────────────────────

from app.routers import (
    auth,
    users,
    departments,
    academic_years,
    proposals,
    comments,
    documents,
    similarity,
    allocations,
    repository,
    notifications,
    reports,
    admin,
    projects,
    deadlines,
    config,
    health,
)


API = "/api/v1"


app.include_router(
    auth.router,
    prefix=f"{API}/auth",
    tags=["Auth"]
)

app.include_router(
    users.router,
    prefix=f"{API}/users",
    tags=["Users"]
)

app.include_router(
    departments.router,
    prefix=f"{API}/departments",
    tags=["Departments"]
)

app.include_router(
    academic_years.router,
    prefix=f"{API}/academic-years",
    tags=["Academic Years"]
)

app.include_router(
    proposals.router,
    prefix=f"{API}/proposals",
    tags=["Proposals"]
)

app.include_router(
    comments.router,
    prefix=f"{API}/proposals",
    tags=["Comments"]
)

app.include_router(
    documents.router,
    prefix=f"{API}",
    tags=["Documents"]
)

app.include_router(
    similarity.router,
    prefix=f"{API}/proposals",
    tags=["Similarity"]
)

app.include_router(
    allocations.router,
    prefix=f"{API}/allocations",
    tags=["Allocations"]
)

app.include_router(
    repository.router,
    prefix=f"{API}/repository",
    tags=["Repository"]
)

app.include_router(
    notifications.router,
    prefix=f"{API}/notifications",
    tags=["Notifications"]
)

app.include_router(
    reports.router,
    prefix=f"{API}/reports",
    tags=["Reports"]
)

app.include_router(
    admin.router,
    prefix=f"{API}/admin",
    tags=["Admin"]
)

app.include_router(
    projects.router,
    prefix=f"{API}/projects",
    tags=["Project Supervision"]
)

app.include_router(
    deadlines.router,
    prefix=f"{API}/deadlines",
    tags=["Deadlines"]
)

app.include_router(
    config.router,
    prefix=f"{API}/config",
    tags=["Config"]
)

app.include_router(
    health.router,
    prefix=f"{API}/health",
    tags=["Health"]
)



# ─────────────────────────────────────────────
# Health Endpoint
# ─────────────────────────────────────────────

@app.get("/health")
def health_check():

    return {
        "success": True,
        "data": {
            "status": "ok"
        },
        "message": "API is running",
        "errors": []
    }
