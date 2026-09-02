from datetime import datetime, timezone

from fastapi import FastAPI

from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.organizations import router as organizations_router
from app.api.v1.routes.procedures import router as procedures_router
from app.api.v1.routes.professionals import router as professionals_router
from app.api.v1.routes.users import router as users_router
from app.config import settings
from app.database import check_database_connection

app = FastAPI(
    title="Booking Engine",
    description="A REST scheduling API designed around dynamic availability and concurrency.",
    version="1.0.0",
    debug=settings.DEBUG
)

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

# Include all v1 routes
app.include_router(auth_router)

app.include_router(users_router)

app.include_router(organizations_router)

app.include_router(professionals_router)

app.include_router(procedures_router)