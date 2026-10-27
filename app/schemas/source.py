"""
app/schemas/source.py
Pydantic schemas for Source data validation.
"""
import uuid
from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, HttpUrl, ConfigDict


SourceTypeEnum = Literal["web", "api", "darkweb", "feed", "other"]
CrawlFrequencyEnum = Literal["manual", "hourly", "daily", "weekly"]


class SourceBase(BaseModel):
    name: str = Field(..., max_length=255, description="Human-readable name for this source.")
    url: str = Field(..., description="Canonical base URL — unique across all sources.")
    description: Optional[str] = Field(None, description="Optional description / notes.")
    source_type: SourceTypeEnum = Field("web", description="Category: web | api | darkweb | feed | other.")
    tags: Optional[List[str]] = Field(default_factory=list, description="List of labels.")
    crawl_depth: int = Field(1, ge=1, le=10, description="Max link-levels deep (1-10).")
    crawl_frequency: CrawlFrequencyEnum = Field("manual", description="Scheduled cadence.")
    allowed_paths: Optional[List[str]] = Field(default_factory=list, description="Allowed URL path prefixes.")
    is_active: bool = Field(True, description="False = source disabled.")


class SourceCreate(SourceBase):
    registered_by: uuid.UUID = Field(..., description="UUID of the Login user registering this source.")


class SourceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    url: Optional[str] = None
    description: Optional[str] = None
    source_type: Optional[SourceTypeEnum] = None
    tags: Optional[List[str]] = None
    crawl_depth: Optional[int] = Field(None, ge=1, le=10)
    crawl_frequency: Optional[CrawlFrequencyEnum] = None
    allowed_paths: Optional[List[str]] = None
    is_active: Optional[bool] = None


class SourceResponse(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    source_id: uuid.UUID
    registered_by: uuid.UUID
    last_crawled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
