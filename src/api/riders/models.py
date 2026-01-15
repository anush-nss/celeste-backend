from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from src.config.constants import VehicleType


class CreateRiderSchema(BaseModel):
    phone: str = Field(..., min_length=5, max_length=20, description="Rider phone number")
    name: str = Field(..., min_length=2, max_length=100, description="Rider name")
    vehicle_type: str = Field(..., description="Type of vehicle (motorcycle, bicycle, etc.)")
    vehicle_registration_number: Optional[str] = Field(None, max_length=50)

    @field_validator("vehicle_type")
    @classmethod
    def validate_vehicle_type(cls, v: str) -> str:
        # Check against enum values, but store as string
        allowed_types = [t.value for t in VehicleType]
        if v not in allowed_types:
            raise ValueError(f"Invalid vehicle type. Must be one of: {allowed_types}")
        return v


class UpdateRiderSchema(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    vehicle_type: Optional[str] = Field(None)
    vehicle_registration_number: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = Field(None)

    @field_validator("vehicle_type")
    @classmethod
    def validate_vehicle_type(cls, v: str) -> str:
        if v is None:
            return v
        allowed_types = [t.value for t in VehicleType]
        if v not in allowed_types:
            raise ValueError(f"Invalid vehicle type. Must be one of: {allowed_types}")
        return v


class RiderProfileSchema(BaseModel):
    id: int
    user_id: Optional[str] = None
    phone: str
    name: str
    vehicle_type: str
    vehicle_registration_number: Optional[str] = None
    is_active: bool
    is_online: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RiderStatusUpdateSchema(BaseModel):
    is_online: bool


class VerifyRiderSchema(BaseModel):
    phone: str = Field(..., description="Phone number to verify")
