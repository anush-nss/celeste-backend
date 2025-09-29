from typing import List
from sqlalchemy.future import select
from sqlalchemy import update
from src.database.connection import AsyncSessionLocal
from src.database.models.address import Address
from src.api.users.models import AddressSchema, UpdateAddressSchema
from src.shared.exceptions import ResourceNotFoundException, ValidationException
from src.shared.sqlalchemy_utils import safe_model_validate_list
from src.shared.error_handler import ErrorHandler


class UserAddressService:
    """Handles address management for users"""

    def __init__(self):
        self._error_handler = ErrorHandler(__name__)

    async def add_address(self, user_id: str, address_data: AddressSchema) -> AddressSchema:
        """Add a new address for a user"""
        async with AsyncSessionLocal() as session:
            # If new address is default, atomically set all other addresses for this user to not default
            if address_data.is_default:
                await session.execute(
                    update(Address).where(Address.user_id == user_id).values(is_default=False)
                )

            new_address = Address(
                user_id=user_id,
                address=address_data.address,
                latitude=address_data.latitude,
                longitude=address_data.longitude,
                is_default=address_data.is_default
            )
            session.add(new_address)
            await session.commit()
            await session.refresh(new_address)
            return AddressSchema.model_validate(new_address)

    async def get_addresses(self, user_id: str) -> List[AddressSchema]:
        """Get all addresses for a user"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Address).filter_by(user_id=user_id)
            )
            addresses = result.scalars().all()
            return safe_model_validate_list(AddressSchema, addresses)

    async def get_address_by_id(self, user_id: str, address_id: int) -> AddressSchema | None:
        """Get a specific address by ID for a user"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()
            if address:
                return AddressSchema.model_validate(address)
            return None

    async def update_address(self, user_id: str, address_id: int, address_data: UpdateAddressSchema) -> AddressSchema | None:
        """Update an existing address"""
        async with AsyncSessionLocal() as session:
            # First verify the address exists and belongs to the user
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()

            if not address:
                raise ResourceNotFoundException(detail=f"Address with ID {address_id} not found for user {user_id}")

            update_data = address_data.model_dump(exclude_unset=True)

            # if no data to update, return early
            if len(update_data) == 0:
                raise ValidationException(detail="No data provided for update")

            # Update the specific address with all provided fields
            for field, value in update_data.items():
                setattr(address, field, value)

            await session.commit()
            await session.refresh(address)
            return AddressSchema.model_validate(address)

    async def delete_address(self, user_id: str, address_id: int) -> bool:
        """Delete an address"""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()

            if not address:
                return False

            await session.delete(address)
            await session.commit()
            return True

    async def set_default_address(self, user_id: str, address_id: int) -> AddressSchema | None:
        """Set an address as the default for a user"""
        async with AsyncSessionLocal() as session:
            # Atomically unset current default address and set new default in one transaction
            # First verify the address exists and belongs to the user
            result = await session.execute(
                select(Address).filter_by(user_id=user_id, id=address_id)
            )
            address = result.scalars().first()

            if not address:
                raise ResourceNotFoundException(detail=f"Address with ID {address_id} not found for user {user_id}")

            # Atomically update all addresses for this user:
            # 1. Set the specified address as default
            # 2. Set all other addresses as non-default
            await session.execute(
                update(Address).where(Address.user_id == user_id).where(Address.id == address_id).values(is_default=True)
            )
            await session.execute(
                update(Address).where(Address.user_id == user_id).where(Address.id != address_id).values(is_default=False)
            )

            await session.commit()

            # Refresh the specific address we're returning
            await session.refresh(address)
            return AddressSchema.model_validate(address)