"""
All services related to access permissions used across all Booking Engine routes.
"""

async def is_root(user_id: int) -> bool:
    """
    Checks whether the user has the ROOT role.

    Args:
        user_id: The user ID to evaluate

    Returns:
        bool: True if the user is a ROOT user, otherwise False
    """
    from app.api.v1.services.user_service import search_user_by_id
    # Search user by its user id
    user = await search_user_by_id(user_id)

    # Check if the user role is root and return it
    return user["role"] == 'ROOT'

async def is_owner(user_id: int, organization_id: int) -> bool:
    """
    Checks whether the user is the owner of a specific organization.

    Args:
        user_id: The user ID to evaluate
        organization_id: The organization ID to compare against

    Returns:
        bool: True if the user is an OWNER for the target organization, otherwise False
    """
    from app.api.v1.services.user_service import search_user_by_id
    # Search user by its id
    user = await search_user_by_id(user_id)

    # Check if the user role is owner and return it
    return user["role"] == 'OWNER' and user["organization_id"] == organization_id

async def is_staff(user_id: int, organization_id: int) -> bool:
    """
    Checks whether the user is a staff member of a specific organization.

    Args:
        user_id: The user ID to evaluate
        organization_id: The organization ID to compare against

    Returns:
        bool: True if the user is STAFF for the target organization, otherwise False
    """
    from app.api.v1.services.user_service import search_user_by_id
    # Search user by its id
    user = await search_user_by_id(user_id)

    # Check if the user role is staff and return it
    return user["role"] == 'STAFF' and user["organization_id"] == organization_id
