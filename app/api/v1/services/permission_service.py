"""
All services related to access permissions used across all Booking Engine routes.
"""

async def is_root(user_id: int) -> bool:
    from app.api.v1.services.user_service import search_user_by_id
    # Search user by its user id
    user = await search_user_by_id(user_id)

    # Check if the user role is root and return it
    return user["role"] == 'ROOT'

async def is_owner(user_id: int, organization_id: int) -> bool:
    from app.api.v1.services.user_service import search_user_by_id
    # Search user by its id
    user = await search_user_by_id(user_id)

    # Check if the user role is owner and return it
    return user["role"] == 'OWNER' and user["organization_id"] == organization_id

async def is_staff(user_id: int, organization_id: int) -> bool:
    from app.api.v1.services.user_service import search_user_by_id
    # Search user by its id
    user = await search_user_by_id(user_id)

    # Check if the user role is staff and return it
    return user["role"] == 'STAFF' and user["organization_id"] == organization_id