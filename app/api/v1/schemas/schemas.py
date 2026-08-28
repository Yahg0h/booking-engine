"""
All Pydantic schemas and models used in BookingEngine.

These schemas mirror schema.sql.
Business rules are validated by the API/services layer.
"""

from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

# ==========================================
# 1. ENUMS
# ==========================================

class UserRole(str, Enum):
    ROOT = "ROOT"
    OWNER = "OWNER"
    STAFF = "STAFF"


class AppointmentStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


# ==========================================
# 2. ORGANIZATION SCHEMAS
# ==========================================

class OrganizationBase(BaseModel):
    name: str = Field(..., max_length=150)
    slug: str = Field(..., max_length=150)
    min_work_time: time
    max_work_time: time

    @model_validator(mode="after")
    def validate_work_time(self) -> "OrganizationBase":
        if self.min_work_time >= self.max_work_time:
            raise ValueError("min_work_time must be before max_work_time.")
        return self


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    slug: str | None = Field(default=None, max_length=150)
    min_work_time: time | None = None
    max_work_time: time | None = None

    model_config = ConfigDict(from_attributes=True)


class OrganizationResponse(OrganizationBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 3. USER SCHEMAS
# ==========================================

class UserBase(BaseModel):
    name: str = Field(..., max_length=150)
    email: EmailStr
    role: UserRole
    is_active: bool = True


class UserCreate(UserBase):
    organization_id: int | None = None
    password: str = Field(..., min_length=6, max_length=255)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=6, max_length=255)
    role: UserRole | None = None
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class UserResponse(BaseModel):
    id: int
    organization_id: int | None = None
    name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ==========================================
# 4. PROFESSIONAL SCHEMAS
# ==========================================

class ProfessionalBase(BaseModel):
    name: str = Field(..., max_length=150)
    buffer_time_minutes: int = Field(default=0, ge=0)
    is_active: bool = True


class ProfessionalCreate(ProfessionalBase):
    user_id: int | None = None


class ProfessionalUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    user_id: int | None = None
    buffer_time_minutes: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class ProfessionalResponse(ProfessionalBase):
    id: int
    organization_id: int
    user_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 5. PROCEDURE SCHEMAS
# ==========================================

class ProcedureBase(BaseModel):
    name: str = Field(..., max_length=150)
    description: str | None = None
    duration_minutes: int = Field(..., gt=0)
    price: Decimal = Field(default=Decimal("0.00"), ge=0)
    is_active: bool = True


class ProcedureCreate(ProcedureBase):
    pass


class ProcedureUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    description: str | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    price: Decimal | None = Field(default=None, ge=0)
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class ProcedureResponse(ProcedureBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 6. PROFESSIONAL-PROCEDURE SCHEMAS
# ==========================================

class ProfessionalProcedureBase(BaseModel):
    professional_id: int
    procedure_id: int
    is_active: bool = True


class ProfessionalProcedureCreate(ProfessionalProcedureBase):
    pass


class ProfessionalProcedureUpdate(BaseModel):
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class ProfessionalProcedureResponse(ProfessionalProcedureBase):
    organization_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 7. WORKING HOURS SCHEMAS
# ==========================================

class WorkingHoursBase(BaseModel):
    weekday: int = Field(..., ge=1, le=7)
    start_time: time
    end_time: time
    is_active: bool = True

    @model_validator(mode="after")
    def validate_time_range(self) -> "WorkingHoursBase":
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before a end_time.")
        return self


class WorkingHoursCreate(WorkingHoursBase):
    pass


class WorkingHoursUpdate(BaseModel):
    weekday: int | None = Field(default=None, ge=1, le=7)
    start_time: time | None = None
    end_time: time | None = None
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkingHoursResponse(WorkingHoursBase):
    id: int
    professional_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 8. BLACKOUT SCHEMAS
# ==========================================

class BlackoutBase(BaseModel):
    start_at: datetime
    end_at: datetime
    reason: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_period(self) -> "BlackoutBase":
        if self.start_at >= self.end_at:
            raise ValueError("start_at must be before a end_at.")
        return self


class BlackoutCreate(BlackoutBase):
    pass


class BlackoutUpdate(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None
    reason: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(from_attributes=True)


class BlackoutResponse(BlackoutBase):
    id: int
    professional_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 9. CUSTOMER SCHEMAS
# ==========================================

class CustomerBase(BaseModel):
    name: str = Field(..., max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool = True


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=150)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    is_active: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class CustomerResponse(CustomerBase):
    id: int
    organization_id: int
    last_appointment_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# 10. APPOINTMENT SCHEMAS
# ==========================================

class AppointmentBase(BaseModel):
    customer_id: int
    professional_id: int
    procedure_id: int
    start_at: datetime
    end_at: datetime
    status: AppointmentStatus = AppointmentStatus.SCHEDULED
    notes: str | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "AppointmentBase":
        if self.start_at >= self.end_at:
            raise ValueError("start_at must be before end_at.")
        return self


class AppointmentCreate(BaseModel):
    customer_id: int
    professional_id: int
    procedure_id: int
    start_at: datetime
    notes: str | None = None


class AppointmentUpdate(BaseModel):
    customer_id: int | None = None
    professional_id: int | None = None
    procedure_id: int | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    status: AppointmentStatus | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AppointmentResponse(AppointmentBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class AppointmentReschedule(BaseModel):
    start_at: datetime


# ==========================================
# 11. AUDIT LOG SCHEMAS
# ==========================================

class AuditLogBase(BaseModel):
    action: str = Field(..., max_length=100)
    entity_type: str = Field(..., max_length=100)
    entity_id: int | None = None
    old_values: dict[str, Any] | None = None
    new_values: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None
    ip_address: str | None = Field(default=None, max_length=45)


class AuditLogCreate(AuditLogBase):
    organization_id: int | None = None
    actor_user_id: int | None = None


class AuditLogResponse(AuditLogBase):
    id: int
    organization_id: int | None = None
    actor_user_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
