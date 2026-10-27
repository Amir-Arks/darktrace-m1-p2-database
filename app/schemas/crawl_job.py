"""
app/schemas/crawl_job.py
Pydantic schemas for CrawlJob data validation.
"""
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict


JobStatusEnum = Literal["pending", "running", "completed", "failed", "cancelled"]


class CrawlJobBase(BaseModel):
    job_name: Optional[str] = Field(None, max_length=255, description="Optional human-readable label.")
    description: Optional[str] = Field(None, description="Optional notes.")
    depth_used: int = Field(1, ge=1, le=10, description="Crawl depth (1-10).")
    user_agent: Optional[str] = Field(None, max_length=255, description="HTTP User-Agent string.")
    extra_config: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom crawler settings.")
    scheduled_at: Optional[datetime] = Field(None, description="When scheduled; None = immediate.")


class CrawlJobCreate(CrawlJobBase):
    triggered_by: uuid.UUID = Field(..., description="UUID of the Login user triggering this job.")
    source_id: uuid.UUID = Field(..., description="UUID of the Source to crawl.")


class CrawlJobStatusUpdate(BaseModel):
    status: JobStatusEnum = Field(..., description="New job status.")
    pages_crawled: Optional[int] = Field(None, ge=0, description="Pages crawled count.")
    errors_count: Optional[int] = Field(None, ge=0, description="Errors encountered.")
    error_details: Optional[str] = Field(None, description="Error message / traceback summary.")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp.")


class CrawlJobResponse(CrawlJobBase):
    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    triggered_by: uuid.UUID
    source_id: uuid.UUID
    status: str
    pages_crawled: int
    errors_count: int
    error_details: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
