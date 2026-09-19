"""
Configure system-wide structured logging and provide utilities for masking sensitive PII.
"""
import logging
import sys
from typing import Literal

from pythonjsonlogger import jsonlogger


def sanitize_for_logging(value: str | None, field_type: str) -> str:
    """
    Sanitizes sensitive values for logging.
    
    Args:
        value: The value to sanitize (can be None)
        field_type: Field type ("email", "phone", "password_hash", "generic")
    
    Returns:
        Sanitized or partially masked value
        
    Rules:
        - password_hash: fully hidden (***hidden***)
        - email: first and last characters visible (r**t@gmail.com)
        - phone: first and last digits visible (+55 9***4-5**9)
        - generic: returns the original value
    """
    if value is None:
        return "None"
    
    value = str(value).strip()
    
    if field_type == "password_hash":
        return "***hidden***"
    
    elif field_type == "email":
        # Sanitizes email: first and last characters visible
        # Example: root@gmail.com -> r**t@gmail.com
        if len(value) <= 2:
            return f"{value[0]}***{value[-1]}"
        
        # Find the @ to keep the domain
        at_index = value.find("@")
        if at_index == -1:
            # Without @, treat as a normal string
            return f"{value[0]}***{value[-1]}"
        
        local_part = value[:at_index]
        domain_part = value[at_index:]
        
        if len(local_part) <= 2:
            sanitized_local = f"{local_part[0]}***{local_part[-1]}" if len(local_part) > 1 else f"{local_part[0]}***"
        else:
            sanitized_local = f"{local_part[0]}**{local_part[-1]}"
        
        return f"{sanitized_local}{domain_part}"
    
    elif field_type == "phone":
        # Sanitize phone: first and last digits visible
        # Example: +55 9***4-5**9 (only digits considered)
        digits_only = ''.join(filter(str.isdigit, value))
        
        if len(digits_only) <= 2:
            return f"{digits_only[0]}***{digits_only[-1]}" if len(digits_only) > 1 else "***"
        
        first_digit = digits_only[0]
        last_digit = digits_only[-1]
        middle_masked = "*" * (len(digits_only) - 2)
        
        # Reconstructs while preserving the original format (non-digit characters)
        result = []
        digit_index = 0
        for char in value:
            if char.isdigit():
                if digit_index == 0:
                    result.append(first_digit)
                elif digit_index == len(digits_only) - 1:
                    result.append(last_digit)
                else:
                    result.append("*")
                digit_index += 1
            else:
                result.append(char)
        
        return "".join(result)
    
    else:
        # generic or unknown: returns normal value
        return value


def setup_logging(log_format: Literal["TEXT", "JSON"], log_level: str) -> None:
    # Create logger root and define global level
    logger = logging.getLogger()
    logger.setLevel(log_level.upper())

    # Cleans existing handlers to prevent duplicated logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Creates output handler (Console)
    handler = logging.StreamHandler(sys.stdout)

    # Define formatter based on toggle
    if log_format == "JSON":
        # JSON format
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    else:
        # Simple TEXT format
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s em %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Add formatter to the handler and handler to logger root
    handler.setFormatter(formatter)
    logger.addHandler(handler)