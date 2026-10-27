"""
app/api/routes/source.py
FastAPI routes for Source management.
"""
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.source import SourceCreate, SourceUpdate, SourceResponse
from app.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["Sources"])


@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
def create_source(source_in: SourceCreate, db: Session = Depends(get_db)):
    """Create a new monitored source."""
    try:
        return SourceService.create_source(db, source_in)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get("/", response_model=List[SourceResponse])
def list_sources(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
):
    """List all registered sources with pagination and filtering."""
    return SourceService.get_sources(db, skip=skip, limit=limit, is_active=is_active)


@router.get("/{source_id}", response_model=SourceResponse)
def get_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch details of a single source by UUID."""
    source = SourceService.get_source(db, source_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID '{source_id}' not found.",
        )
    return source


@router.patch("/{source_id}", response_model=SourceResponse)
def update_source(
    source_id: uuid.UUID,
    source_in: SourceUpdate,
    db: Session = Depends(get_db),
):
    """Update an existing source."""
    source = SourceService.update_source(db, source_id, source_in)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID '{source_id}' not found.",
        )
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, db: Session = Depends(get_db)):
    """Delete a source by UUID."""
    deleted = SourceService.delete_source(db, source_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID '{source_id}' not found.",
        )
    return None
