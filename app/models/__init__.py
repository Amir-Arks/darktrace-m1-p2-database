"""
app/models/__init__.py
Exports all registered SQLAlchemy models so Alembic, FastAPI, and test suites can import from one place.
"""
from app.models.base import Base
from app.models.login import Login
from app.models.source import Source
from app.models.crawl_job import CrawlJob
from app.models.watchlist import Watchlist, WatchlistVersion
from app.models.alert import (
    Alert,
    AlertState,
    Severity,
    InvalidStateTransition,
    make_fingerprint,
    record_alert,
    transition_alert,
)

__all__ = [
    "Base",
    "Login",
    "Source",
    "CrawlJob",
    "Watchlist",
    "WatchlistVersion",
    "Alert",
    "AlertState",
    "Severity",
    "InvalidStateTransition",
    "make_fingerprint",
    "record_alert",
    "transition_alert",
]
