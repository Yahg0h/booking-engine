"""
Application entry point to initialize the FastAPI app, configure logging, and register all API routers.
"""

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.database import check_database_connection
from app.logging_config import setup_logging
from app.rate_limiter import limiter

# Trigger logging configuration before app initialization
setup_logging(settings.LOG_FORMAT, settings.LOG_LEVEL)

# Initialize app
app = FastAPI(
    title="Booking Engine",
    description="A REST scheduling API designed around dynamic availability and concurrency.",
    version="1.0.0",
    debug=settings.DEBUG
)

# Initialize HTTP Bearer
security = HTTPBearer()

# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Rate limiter error handler
def _rate_limit_exceeded_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please try again later."}
    )

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Import routers after the limiter exists because routes decorate endpoints with it.
from app.api.v1.routes.appointments import router as appointment_service
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.availability import router as availability_router
from app.api.v1.routes.customers import router as customers_router
from app.api.v1.routes.organizations import router as organizations_router
from app.api.v1.routes.procedures import router as procedures_router
from app.api.v1.routes.professionals import router as professionals_router
from app.api.v1.routes.root.appointments import router as root_appointments
from app.api.v1.routes.root.customers import router as root_customers
from app.api.v1.routes.root.organizations import router as root_organizations
from app.api.v1.routes.root.procedures import router as root_procedures
from app.api.v1.routes.root.professionals import router as root_professionals
from app.api.v1.routes.root.users import router as root_users
from app.api.v1.routes.users import router as users_router


# Customize OpenAPI schema to include Bearer token
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Booking Engine API",
        version="1.0.0",
        description="Multi-tenant appointment booking REST API",
        routes=app.routes,
    )

    openapi_schema["components"]["securitySchemes"] = {
        "HTTPBearer": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    openapi_schema["security"] = [{"HTTPBearer": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# ==== ROUTES ====
@app.get("/")
async def root():
    return {
        "api_name": "booking-engine",
        "status": "available at /health",
        "documentation": "available at /docs",
        "repository": "https://github.com/Yahg0h/booking-engine",
        "message": "Welcome to Booking Engine!"
    }

@app.get("/health")
async def health_check():
    """
    Health check endpoint showing service and database status.
    """
    connect_check, error_message = await check_database_connection()
    now = datetime.now(tz=timezone.utc)
    return {
        "service_name": 'Booking Engine',
        "service_version": '1.0.0',
        "db_connected": connect_check,
        "checked_at": now,
        "db_error": error_message
    }

# ==== Include all v1 routes ====
# Normal routes
app.include_router(auth_router)

app.include_router(users_router)

app.include_router(organizations_router)

app.include_router(professionals_router)

app.include_router(procedures_router)

app.include_router(customers_router)

app.include_router(availability_router)

app.include_router(appointment_service)

# ==== Include all v1 root routes ====
app.include_router(root_users)
app.include_router(root_organizations)
app.include_router(root_professionals)
app.include_router(root_procedures)
app.include_router(root_customers)
app.include_router(root_appointments)
