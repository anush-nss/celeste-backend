from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr


class LocationSchema(BaseModel):
    latitude: float
    longitude: float


class StoreSchema(BaseModel):
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    address: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    location: LocationSchema
    isActive: Optional[bool] = True
    createdAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None


class CreateStoreSchema(BaseModel):
    name: str
    description: Optional[str] = None
    address: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    location: LocationSchema
    isActive: Optional[bool] = True


class UpdateStoreSchema(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    location: Optional[LocationSchema] = None
    isActive: Optional[bool] = None
