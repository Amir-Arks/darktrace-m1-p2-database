"""
app/services/crawl_job_service.py
Service and Repository operations for the `crawl_job` table.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.crawl_job import CrawlJob
from app.models.source import Source
from app.models.login import Login
from app.schemas.crawl_job import CrawlJobCreate, CrawlJobStatusUpdate


class CrawlJobService:
    @staticmethod
    def create_crawl_job(db: Session, job_in: CrawlJobCreate) -> CrawlJob:
        """
        Creates a new crawl job for a monitored source.
        Validates:
          1. Source exists and is active.
          2. Triggering Login user exists.
        """
        # Validate Source existence
        source = db.get(Source, job_in.source_id)
        if not source:
            raise ValueError(f"Source with ID '{job_in.source_id}' does not exist. Job creation rejected.")

        # Validate User existence
        triggerer = db.get(Login, job_in.triggered_by)
        if not triggerer:
            raise ValueError(f"Triggering user with ID '{job_in.triggered_by}' does not exist.")

        # Default depth from source if not specified
        depth = job_in.depth_used if job_in.depth_used is not None else source.crawl_depth

        job = CrawlJob(
            triggered_by=job_in.triggered_by,
            source_id=job_in.source_id,
            job_name=job_in.job_name or f"Crawl {source.name} ({datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')})",
            description=job_in.description,
            depth_used=depth,
            user_agent=job_in.user_agent,
            extra_config=job_in.extra_config,
            status="pending",
            scheduled_at=job_in.scheduled_at,
            pages_crawled=0,
            errors_count=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_crawl_job(db: Session, job_id: uuid.UUID) -> Optional[CrawlJob]:
        """Fetch a single crawl job by ID."""
        return db.get(CrawlJob, job_id)

    @staticmethod
    def list_crawl_jobs_for_source(
        db: Session,
        source_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CrawlJob]:
        """List all crawl jobs associated with a given source."""
        # Verify source exists
        source = db.get(Source, source_id)
        if not source:
            raise ValueError(f"Source with ID '{source_id}' does not exist.")

        stmt = (
            select(CrawlJob)
            .where(CrawlJob.source_id == source_id)
            .order_by(CrawlJob.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def list_crawl_jobs(
        db: Session,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CrawlJob]:
        """List all crawl jobs with optional status filter."""
        stmt = select(CrawlJob)
        if status:
            stmt = stmt.where(CrawlJob.status == status)
        stmt = stmt.order_by(CrawlJob.created_at.desc()).offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def update_job_status(
        db: Session,
        job_id: uuid.UUID,
        update_in: CrawlJobStatusUpdate,
    ) -> Optional[CrawlJob]:
        """
        Updates the execution status and metrics of a crawl job.
        If status is 'completed', updates the parent source's last_crawled_at timestamp.
        """
        job = db.get(CrawlJob, job_id)
        if not job:
            return None

        now = datetime.now(timezone.utc)
        job.status = update_in.status

        if update_in.status == "running" and not job.started_at:
            job.started_at = now

        if update_in.status in ("completed", "failed", "cancelled"):
            job.completed_at = update_in.completed_at or now

        if update_in.pages_crawled is not None:
            job.pages_crawled = update_in.pages_crawled

        if update_in.errors_count is not None:
            job.errors_count = update_in.errors_count

        if update_in.error_details is not None:
            job.error_details = update_in.error_details

        # On successful completion, update parent source's last_crawled_at
        if update_in.status == "completed":
            source = db.get(Source, job.source_id)
            if source:
                source.last_crawled_at = job.completed_at

        db.commit()
        db.refresh(job)
        return job
