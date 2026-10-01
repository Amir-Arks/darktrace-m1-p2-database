"""
app/api/routes/crawl_job.py
FastAPI routes for CrawlJob management.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.crawl_job import CrawlJobCreate, CrawlJobStatusUpdate, CrawlJobResponse
from app.services.crawl_job_service import CrawlJobService

router = APIRouter(tags=["Crawl Jobs"])


@router.post("/crawl-jobs/", response_model=CrawlJobResponse, status_code=status.HTTP_201_CREATED)
def create_crawl_job(job_in: CrawlJobCreate, db: Session = Depends(get_db)):
    """
    Trigger a new crawl job for a monitored source.
    Returns 404 / 400 if the source or user is invalid.
    """
    try:
        return CrawlJobService.create_crawl_job(db, job_in)
    except ValueError as e:
        # Check if it was a missing source/user
        err_msg = str(e)
        if "does not exist" in err_msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)


@router.get("/crawl-jobs/", response_model=List[CrawlJobResponse])
def list_crawl_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List all crawl jobs with optional status filter."""
    return CrawlJobService.list_crawl_jobs(db, status=status_filter, skip=skip, limit=limit)


@router.get("/crawl-jobs/{job_id}", response_model=CrawlJobResponse)
def get_crawl_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch details of a specific crawl job."""
    job = CrawlJobService.get_crawl_job(db, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crawl job with ID '{job_id}' not found.",
        )
    return job


@router.get("/sources/{source_id}/crawl-jobs", response_model=List[CrawlJobResponse])
def list_jobs_for_source(
    source_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List all crawl attempts/jobs belonging to a specific source."""
    try:
        return CrawlJobService.list_crawl_jobs_for_source(db, source_id, skip=skip, limit=limit)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.patch("/crawl-jobs/{job_id}/status", response_model=CrawlJobResponse)
def update_crawl_job_status(
    job_id: uuid.UUID,
    update_in: CrawlJobStatusUpdate,
    db: Session = Depends(get_db),
):
    """Update crawl job lifecycle status and metrics (pages crawled, errors, completed_at)."""
    job = CrawlJobService.update_job_status(db, job_id, update_in)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Crawl job with ID '{job_id}' not found.",
        )
    return job
