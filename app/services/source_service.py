"""
app/services/source_service.py
Service and Repository operations for the `source` table.
"""
import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.source import Source
from app.models.login import Login
from app.schemas.source import SourceCreate, SourceUpdate


class SourceService:
    @staticmethod
    def create_source(db: Session, source_in: SourceCreate) -> Source:
        """
        Creates a new source target.
        Validates that the registering user exists.
        """
        # Ensure registrar exists
        registrar = db.get(Login, source_in.registered_by)
        if not registrar:
            raise ValueError(f"Registering user with ID '{source_in.registered_by}' does not exist.")

        # Check for URL uniqueness
        existing = db.scalars(select(Source).where(Source.url == source_in.url)).first()
        if existing:
            raise ValueError(f"A source with URL '{source_in.url}' already exists (ID: {existing.source_id}).")

        source = Source(
            name=source_in.name,
            url=source_in.url,
            description=source_in.description,
            source_type=source_in.source_type,
            tags=source_in.tags,
            crawl_depth=source_in.crawl_depth,
            crawl_frequency=source_in.crawl_frequency,
            allowed_paths=source_in.allowed_paths,
            registered_by=source_in.registered_by,
            is_active=source_in.is_active,
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        return source

    @staticmethod
    def get_source(db: Session, source_id: uuid.UUID) -> Optional[Source]:
        """Fetch a source by its UUID."""
        return db.get(Source, source_id)

    @staticmethod
    def get_sources(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        is_active: Optional[bool] = None,
    ) -> List[Source]:
        """List sources with optional pagination and active filter."""
        stmt = select(Source)
        if is_active is not None:
            stmt = stmt.where(Source.is_active == is_active)
        stmt = stmt.offset(skip).limit(limit)
        return list(db.scalars(stmt).all())

    @staticmethod
    def update_source(db: Session, source_id: uuid.UUID, source_in: SourceUpdate) -> Optional[Source]:
        """Update source details."""
        source = db.get(Source, source_id)
        if not source:
            return None

        update_data = source_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(source, key, value)

        db.commit()
        db.refresh(source)
        return source

    @staticmethod
    def delete_source(db: Session, source_id: uuid.UUID) -> bool:
        """Soft-delete or delete a source by ID."""
        source = db.get(Source, source_id)
        if not source:
            return False
        db.delete(source)
        db.commit()
        return True
