"""Data models for tagging system."""

from pydantic import BaseModel, Field, field_validator
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
from uuid import uuid4


class Tag(BaseModel):
    """Hierarchical tag model."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None
    level: int = Field(default=0, ge=0, le=4)  # Max 4 levels deep
    full_path: str  # e.g., "language/python/async"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Normalize and validate tag name."""
        v = v.strip().lower()
        if not v:
            raise ValueError("Tag name cannot be empty")
        # Allow letters, numbers, hyphens, underscores
        if not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(
                "Tag name can only contain letters, numbers, hyphens, and underscores"
            )
        return v

    @field_validator("full_path")
    @classmethod
    def validate_full_path(cls, v: str) -> str:
        """Validate tag path format."""
        if not v or v != v.strip():
            raise ValueError("Tag path cannot be empty or have leading/trailing spaces")
        # Validate path depth
        parts = v.split("/")
        if len(parts) > 4:
            raise ValueError("Tag hierarchy cannot exceed 4 levels")
        return v


class TagCreate(BaseModel):
    """Request model for creating a tag."""

    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[str] = None


class Collection(BaseModel):
    """Memory collection model."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    auto_generated: bool = False
    tag_filter: Optional[Dict[str, Any]] = None  # {"tags": [...], "op": "AND/OR"}
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate collection name."""
        v = v.strip()
        if not v:
            raise ValueError("Collection name cannot be empty")
        return v


class CollectionCreate(BaseModel):
    """Request model for creating a collection."""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    tag_filter: Optional[Dict[str, Any]] = None


class MemoryTag(BaseModel):
    """Junction model for memory-tag relationship."""

    memory_id: str
    tag_id: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    auto_generated: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class CollectionMemory(BaseModel):
    """Junction model for collection-memory relationship."""

    collection_id: str
    memory_id: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
