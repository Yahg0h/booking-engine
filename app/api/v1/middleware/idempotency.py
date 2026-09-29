"""
Middleware for requiring idempotency keys and replaying cached responses.
Uses Redis.
"""

import logging
import re

logger = logging.getLogger(__name__)

import json

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

from app.api.v1.services.auth_service import decode_token
from app.api.v1.services.cache_service import redis_client
from app.api.v1.services.idempotency_service import (
    check_idempotent_request,
    store_response,
)
from app.api.v1.services.user_service import search_user_by_id


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Enforces idempotency for selected API requests."""

    def __init__(self, app):
        """
        Initializes the middleware and its required-key route patterns.

        Args:
            app: The ASGI application wrapped by this middleware
        """
        super().__init__(app)
        # Routes that REQUIRE an idempotency key (as regex patterns)
        self.critical_routes_patterns = [
            r"^POST /v1/appointments$",
            r"^POST /v1/customers$",
            r"^POST /v1/professionals/\d+/blackouts$",
            r"^POST /v1/professionals/\d+/procedures$",
            r"^PATCH /v1/appointments/\d+$",
            r"^PATCH /v1/customers/\d+$",
            r"^PATCH /v1/organizations/\d+/settings$",
        ]
    
    async def dispatch(self, request: Request, call_next):
        """
        Processes a request using its idempotency key when provided or required.

        POST and PATCH requests to critical routes require an idempotency key.
        Requests with a key are authenticated, scoped to the user's organization,
        checked for a cached response, and stored after the downstream response.

        Args:
            request: The incoming HTTP request
            call_next: The next ASGI handler in the middleware chain

        Returns:
            Response: The cached response, a middleware error response, or the downstream response
        """
        # POST/PATCH only
        if request.method not in ["POST", "PATCH"]:
            return await call_next(request)
        
        # Verify if the current route is one of the critical routes
        route_str = f"{request.method} {request.url.path}"
        is_critical = any(re.match(p, route_str) for p in self.critical_routes_patterns)
        
        idempotency_key = request.headers.get("Idempotent-Key")
        
        # If it is a critical route and doesn't have a key, return 400
        if is_critical and not idempotency_key:
            return JSONResponse(
                status_code=400,
                content={"error": "Idempotent-Key header is required for this operation"}
            )
        
        # If it isn't critical and doesn't have a key, let it go
        if not idempotency_key:
            return await call_next(request)
        
        # Extract user_id from JWT
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return JSONResponse(
                    status_code=401,
                    content={"error": "Missing Authorization header"}
                )
            
            parts = auth_header.split()
            if len(parts) != 2 or parts[0] != "Bearer":
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid Authorization header format"}
                )
            
            token = parts[1]
            user_id = decode_token(token)
        except ValueError as e:
            return JSONResponse(
                status_code=401,
                content={"error": str(e)}
            )
        
        # Get organization_id from user
        try:
            user = await search_user_by_id(user_id)
            org_id = user["organization_id"]
        except Exception:
            return JSONResponse(
                status_code=500,
                content={"error": "Failed to fetch user organization"}
            )
        
        # Check if it was already processed
        try:
            exists, cached_response = await check_idempotent_request(
                redis_client, org_id, idempotency_key
            )
            
            if exists:
                return JSONResponse(
                    status_code=cached_response["status_code"],
                    content=cached_response["body"]
                )
        except Exception:
            # ==== STRUCTURED LOGGING ====
            logger.warning(
                "Idempotency check failed, "
                f"org_id={org_id}, idempotency_key={idempotency_key}."
            )
        
        # Executes the route
        response = await call_next(request)
        
        # Reads body
        body_parts = []
        async for chunk in response.body_iterator:
            body_parts.append(chunk)
        body_bytes = b"".join(body_parts)
        try:
            response_body = json.loads(body_bytes)
        except json.JSONDecodeError:
            # ==== STRUCTURED LOGGING ====
            logger.warning(
                "Idempotency response decode failed, "
                f"org_id={org_id}, idempotency_key={idempotency_key}."
            )
            response_body = {"error": "invalid response"}
        
        # Store response (all of them)
        try:
            await store_response(
                redis_client,
                org_id,
                idempotency_key,
                response.status_code,
                response_body
            )
        except Exception:
            # ==== STRUCTURED LOGGING ====
            logger.warning(
                "Idempotency store failed, "
                f"org_id={org_id}, idempotency_key={idempotency_key}."
            )

        # Return a new response with body
        return Response(
            content=body_bytes,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type
        )