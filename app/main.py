"""
app/main.py
FastAPI application entry point for DarkTrace Pod 2 (Source + Crawl Job).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_tables, verify_fk_enforcement, db_info
from app.api.routes.source import router as source_router
from app.api.routes.crawl_job import router as crawl_job_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure tables exist and foreign keys are verified
    create_tables()
    verify_fk_enforcement()
    yield
    # Shutdown logic if any


app = FastAPI(
    title="DarkTrace — Source & Crawl Job Service (Pod 2 / Member 2)",
    description="Backend API and Database services for monitored Sources and Crawl Jobs.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(source_router)
app.include_router(crawl_job_router)


@app.get("/health", tags=["System"])
def health_check():
    """Health check endpoint returning DB dialect and status."""
    return {
        "status": "healthy",
        "service": "source-crawl-job",
        "db": db_info(),
    }
