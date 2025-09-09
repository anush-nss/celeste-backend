from datetime import datetime, time
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, validator
from src.config.constants import (
    StoreFeatures,
    MIN_LATITUDE,
    MAX_LATITUDE,
    MIN_LONGITUDE,
    MAX_LONGITUDE,
    HOUR_FORMAT,
)


class LocationSchema(BaseModel):
    latitude: float = Field(
        ..., ge=MIN_LATITUDE, le=MAX_LATITUDE, description="Latitude in degrees"
    )
    longitude: float = Field(
        ..., ge=MIN_LONGITUDE, le=MAX_LONGITUDE, description="Longitude in degrees"
    )


class ContactSchema(BaseModel):
    phone: Optional[str] = Field(None, description="Store phone number")
    email: Optional[EmailStr] = Field(None, description="Store email address")


class BusinessHoursSchema(BaseModel):
    open: Optional[str] = Field(
        None,
        pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$",
        description="Opening time in HH:MM format",
    )
    close: Optional[str] = Field(
        None,
        pattern=r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$",
        description="Closing time in HH:MM format",
    )
    closed: bool = Field(False, description="Whether the store is closed on this day")


class StoreHoursSchema(BaseModel):
    monday: Optional[BusinessHoursSchema] = None
    tuesday: Optional[BusinessHoursSchema] = None
    wednesday: Optional[BusinessHoursSchema] = None
    thursday: Optional[BusinessHoursSchema] = None
    friday: Optional[BusinessHoursSchema] = None
    saturday: Optional[BusinessHoursSchema] = None
    sunday: Optional[BusinessHoursSchema] = None


class StoreSchema(BaseModel):
    id: Optional[str] = None
    name: str = Field(..., min_length=1, max_length=200, description="Store name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Store description"
    )
    address: str = Field(
        ..., min_length=1, max_length=500, description="Complete store address"
    )
    location: LocationSchema
    contact: Optional[ContactSchema] = None
    hours: Optional[StoreHoursSchema] = None
    features: Optional[List[StoreFeatures]] = Field(
        default_factory=list, description="Store features and amenities"
    )
    isActive: bool = Field(True, description="Whether the store is active")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Dynamic fields (added by service layer)
    distance: Optional[float] = Field(
        None, description="Distance from search location in km"
    )
    is_open_now: Optional[bool] = Field(
        None, description="Whether the store is currently open"
    )
    next_change: Optional[str] = Field(None, description="Next opening/closing time")


class CreateStoreSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Store name")
    description: Optional[str] = Field(
        None, max_length=1000, description="Store description"
    )
    address: str = Field(
        ..., min_length=1, max_length=500, description="Complete store address"
    )
    location: LocationSchema
    contact: Optional[ContactSchema] = None
    hours: Optional[StoreHoursSchema] = None
    features: Optional[List[StoreFeatures]] = Field(
        default_factory=list, description="Store features"
    )
    isActive: Optional[bool] = Field(True, description="Whether the store is active")


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
    location: Optional[LocationSchema] = None
    contact: Optional[ContactSchema] = None
    hours: Optional[StoreHoursSchema] = None
    features: Optional[List[StoreFeatures]] = None
    isActive: Optional[bool] = None


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
    isActive: Optional[bool] = Field(True, description="Filter by store status")
    features: Optional[List[StoreFeatures]] = Field(
        None, description="Filter by store features"
    )
    includeDistance: Optional[bool] = Field(
        True, description="Include distance calculations"
    )
    includeOpenStatus: Optional[bool] = Field(
        True, description="Include open/closed status"
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
