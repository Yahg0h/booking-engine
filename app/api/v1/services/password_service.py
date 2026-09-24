"""
Password hashing utilities.
"""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    """
    Hashes a plain-text password using Argon2.

    Args:
        password: The plain-text password to hash

    Returns:
        str: The hashed password value
    """
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """
    Verifies whether a plain-text password matches the stored hash.

    Args:
        password: The plain-text password supplied for verification
        hashed: The stored password hash to compare against

    Returns:
        bool: True if the password matches the hash, otherwise False
    """
    return pwd_context.verify(password, hashed)
