from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator
from src.config.constants import (
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
)
from src.api.shared.tags.models import EntityTagSchema


class LocationSchema(BaseModel):
    latitude: float = Field(
        ..., ge=MIN_LATITUDE, le=MAX_LATITUDE, description="Latitude in degrees"
    )
    longitude: float = Field(
        ..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="Longitude in degrees"
    )


class ContactSchema(BaseModel):
    email: Optional[EmailStr] = Field(None, description="Store email address")
    phone: Optional[str] = Field(None, description="Store phone number")


class StoreTagSchema(EntityTagSchema):
    """Store-specific tag schema"""
    pass


class StoreSchema(BaseModel):
    id: Optional[int] = None
    name: str = Field(..., min_length=1, max_length=200, description="Store name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Store description"
    )
    address: str = Field(
        ..., min_length=1, max_length=500, description="Complete store address"
    )
    latitude: float = Field(..., ge=MIN_LATITUDE, le=MAX_LATITUDE, description="Latitude in degrees")
    longitude: float = Field(..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="Longitude in degrees")
    email: Optional[str] = Field(None, description="Store email address")
    phone: Optional[str] = Field(None, description="Store phone number")
    is_active: bool = Field(True, description="Whether the store is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Dynamic fields (added by service layer)
    distance: Optional[float] = Field(
        None, description="Distance from search location in km"
    )
    store_tags: Optional[List[Dict[str, Any]]] = None  # Raw store_tags data

    model_config = {"from_attributes": True}


class CreateStoreSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Store name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Store description"
    )
    address: str = Field(
        ..., min_length=1, max_length=500, description="Complete store address"
    )
    latitude: float = Field(..., ge=MIN_LATITUDE, le=MAX_LATITUDE, description="Latitude in degrees")
    longitude: float = Field(..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="Longitude in degrees")
    email: Optional[str] = Field(None, description="Store email address")
    phone: Optional[str] = Field(None, description="Store phone number")
    tag_ids: List[int] = Field(default=[], description="IDs of tags to assign")
    is_active: Optional[bool] = Field(True, description="Whether the store is active")


class UpdateStoreSchema(BaseModel):
    name: Optional[str] = Field(
        None, min_length=1, max_length=200, description="Store name"
    )
    description: Optional[str] = Field(
        None, max_length=1000, description="Store description"
    )
    address: Optional[str] = Field(
        None, min_length=1, max_length=500, description="Complete store address"
    )
    latitude: Optional[float] = Field(None, ge=MIN_LATITUDE, le=MAX_LATITUDE, description="Latitude in degrees")
    longitude: Optional[float] = Field(None, ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="Longitude in degrees")
    email: Optional[str] = Field(None, description="Store email address")
    phone: Optional[str] = Field(None, description="Store phone number")
    tag_ids: Optional[List[int]] = None
    is_active: Optional[bool] = None


class StoreQuerySchema(BaseModel):
    latitude: Optional[float] = Field(
        None,
        ge=MIN_LATITUDE,
        le=MAX_LATITUDE,
        description="User latitude for location-based search",
    )
    longitude: Optional[float] = Field(
        None,
        ge=MIN_LONGITUDE,
        le=MAX_LONGITUDE,
        description="User longitude for location-based search",
    )
    radius: Optional[float] = Field(
        10.0, ge=0.1, le=50.0, description="Search radius in kilometers"
    )
    limit: Optional[int] = Field(
        20, ge=1, le=100, description="Maximum number of stores to return"
    )
    is_active: Optional[bool] = Field(True, description="Filter by store status")
    tag_types: Optional[List[str]] = Field(None, description="Filter by tag types")
    tag_ids: Optional[List[int]] = Field(None, description="Filter by specific tags")
    include_distance: Optional[bool] = Field(
        True, description="Include distance calculations"
    )
    include_tags: Optional[bool] = Field(
        False, description="Include tag information"
    )

    @validator("radius")
    def validate_radius_with_location(cls, v, values):
        """Validate that radius is provided only with location"""
        if v and v > 0.1:
            if not values.get("latitude") or not values.get("longitude"):
                raise ValueError("Radius search requires both latitude and longitude")
        return v


class StoreLocationResponse(BaseModel):
    stores: List[StoreSchema]
    user_location: Optional[Dict[str, float]] = None
    search_radius: Optional[float] = None
    total_found: int
    returned: int
