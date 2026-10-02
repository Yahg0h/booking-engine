<div align="center">

# Booking Engine


**A multi-tenant appointment booking REST API built with FastAPI and MySQL.**
Covers the full lifecycle from organization creation, users, professionals, procedures, customers and appointment management.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![MySQL 8.0+](https://img.shields.io/badge/MySQL-8.0+-orange.svg)](https://www.mysql.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

</div>

---

## About

Booking Engine is a backend REST API designed to manage appointment scheduling across multiple independent organizations. Each organization operates with its own professionals, procedures, working hours, and customer base. The system handles availability calculation, blackout periods, cancellation policies, rate limiting, audit logging, and role-based access control — all through a single, structured API.

---

## Features

- **Multi-tenant architecture** — each organization is fully isolated with its own data and access rules
- **Dynamic availability engine** — calculates open slots in real time based on working hours, existing appointments, blackouts, and professional buffer times
- **Role-based access control (RBAC)** — three-tier hierarchy: `ROOT`, `OWNER`, and `STAFF`
- **Professional blackout management** — professionals can request time-off blocks; owners approve or reject them
- **Cancellation policy enforcement** — configurable per-organization cancellation buffer (in hours)
- **Distributed locking** — Redis-based locks prevent double-booking race conditions
- **Comprehensive audit logging** — every mutation is recorded with actor, old values, new values, and IP address
- **Structured JSON logging** — supports both plain text and JSON log formats
- **Rate limiting** — per-endpoint request throttling via SlowAPI
- **JWT authentication** — stateless authentication with configurable expiration
- **Idempotency keys** — ensures safe retries for critical mutations via `Idempotent-Key` header; prevents duplicate appointments, customers, and professionals
- **Redis cache management** — multi-tier caching strategy with tiered TTLs (5s to 30min) and smart invalidation patterns
- **Statistics & analytics endpoints** — real-time appointment, revenue, and customer metrics with date-range filtering and weekly/monthly/yearly grouping
- **Advanced reporting** — PDF and CSV report generation with metadata, summary metrics, and detailed data export
- **Interactive API docs** — Swagger UI available at `/docs`

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| ASGI Server | [Uvicorn](https://www.uvicorn.org/) |
| ORM / DB Driver | [SQLAlchemy](https://www.sqlalchemy.org/) + [aiomysql](https://github.com/PyMySQL/aiomysql) |
| Database | MySQL 8.0 |
| Cache / Locking | Redis |
| Authentication | JWT ([PyJWT](https://pyjwt.readthedocs.io/)) |
| Password Hashing | [Passlib](https://passlib.readthedocs.io/) + Argon2 |
| Data Validation | [Pydantic v2](https://docs.pydantic.dev/) |
| Settings Management | [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) |
| Rate Limiting | [SlowAPI](https://slowapi.readthedocs.io/) |
| Logging | [python-json-logger](https://github.com/madzak/python-json-logger) |
| Caching & Locking | [redis-py](https://github.com/redis/redis-py) |
| Data Analysis | [pandas](https://pandas.pydata.org/) |
| PDF Generation | [reportlab](https://www.reportlab.com/) |
| Testing | [pytest](https://docs.pytest.org/) + [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) + [httpx](https://www.python-httpx.org/) |
| Containerization | Docker + Docker Compose |
| CI | GitHub Actions |

---

## Project Structure

```
booking-engine/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── middleware/         # ASGI middleware
│   │       │   ├── idempotency.py  # Idempotency enforcement and response caching
│   │       │   └── rate_limiter.py # Shared SlowAPI limiter instance
│   │       ├── routes/             # HTTP route handlers
│   │       │   ├── root/           # ROOT-only admin routes
│   │       │   │   ├── appointments.py
│   │       │   │   ├── customers.py
│   │       │   │   ├── organizations.py
│   │       │   │   ├── procedures.py
│   │       │   │   ├── professionals.py
│   │       │   │   ├── reports.py  # PDF/CSV report generation
│   │       │   │   ├── statistics.py # Aggregated metrics endpoints
│   │       │   │   └── users.py
│   │       │   ├── appointments.py
│   │       │   ├── auth.py
│   │       │   ├── availability.py
│   │       │   ├── customers.py
│   │       │   ├── organizations.py
│   │       │   ├── procedures.py
│   │       │   ├── professionals.py
│   │       │   └── users.py
│   │       ├── schemas/
│   │       │   └── schemas.py      # All Pydantic request/response models
│   │       └── services/           # Business logic layer
│   │           ├── appointment_service.py
│   │           ├── audit_service.py
│   │           ├── auth_service.py
│   │           ├── availability_service.py
│   │           ├── cache_service.py       # Redis locks, caching decorator, and helpers
│   │           ├── customer_service.py
│   │           ├── idempotency_service.py # Redis check/store for idempotent requests
│   │           ├── organization_service.py
│   │           ├── organization_settings_service.py
│   │           ├── password_service.py
│   │           ├── permission_service.py
│   │           ├── procedure_service.py
│   │           ├── professional_service.py
│   │           ├── report_generator.py    # PDF and CSV file generation
│   │           ├── report_service.py      # Report data queries via pandas
│   │           ├── statistics_service.py  # Statistics and metrics aggregation
│   │           └── user_service.py
│   ├── config.py                   # Environment settings via pydantic-settings
│   ├── database.py                 # SQLAlchemy async engine setup
│   ├── logging_config.py           # Structured logging configuration
│   └── main.py                     # FastAPI app initialization and router registration
├── tests/
│   ├── integration/                # Integration tests (route-level)
│   └── unit/
│       └── services/               # Unit tests for individual services
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI pipeline
├── schema.sql                      # Full MySQL schema definition
├── compose.yaml                    # Docker Compose (API + MySQL + Redis)
├── Dockerfile                      # Production Docker image
├── requirements.txt
├── pytest.ini
├── README.md
├── .env.example                    # Environment variable template
└── .env                            # Environment variables (not committed)
```

---

## Database Schema

The database (`booking_engine`) is defined in [`schema.sql`](schema.sql) and contains 11 tables:

| Table | Description |
|---|---|
| `organizations` | Top-level tenant. Defines name, slug, and operating time bounds. |
| `organization_settings` | Per-organization settings: operating weekdays and cancellation buffer hours. |
| `users` | System users with roles `ROOT`, `OWNER`, or `STAFF`. `ROOT` has no organization. |
| `professionals` | Service providers linked to a user account and an organization. Stores `buffer_time_minutes`. |
| `procedures` | Services offered by an organization (name, description, duration, price). |
| `professional_procedures` | Many-to-many join between professionals and the procedures they offer. |
| `working_hours` | Weekly schedule for each professional (one record per weekday). |
| `blackouts` | Time-off blocks requested by professionals, with approval workflow (`PENDING` → `ACCEPTED`/`REJECTED`). |
| `customers` | End-users of the booking service, scoped to an organization. |
| `appointments` | Booked sessions linking a customer, professional, and procedure with a start/end time and status. |
| `audit_logs` | Append-only log of all mutations, with actor, entity, old/new values, and IP address. |

**Key relationships:**

```
organizations ──< organization_settings (1:1)
organizations ──< users (1:N)
organizations ──< professionals (1:N)
organizations ──< procedures (1:N)
organizations ──< customers (1:N)
professionals ──< professional_procedures >── procedures (M:N)
professionals ──< working_hours (1:N)
professionals ──< blackouts (1:N)
professionals ──< appointments (1:N)
customers     ──< appointments (1:N)
procedures    ──< appointments (1:N)
```

---

## Setup & Installation

### Prerequisites

- Python 3.14+
- MySQL 8.0+
- Redis
- Docker & Docker Compose *(for Docker setup)*

---

### Option 1: Local Setup (without Docker)

**1. Clone the repository**

```bash
git clone https://github.com/Yahg0h/booking-engine.git
cd booking-engine
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# Linux/macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure environment variables**

Copy `.env.example` and fill in your values:

```bash
cp .env.example .env
```

```env
# Database
DB_USER=booking_admin
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
DB_NAME=booking_engine

# Security
JWT_SECRET=your_very_long_random_secret_here

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Redis
REDIS_SECRET_KEY=your_redis_secret
CACHE_DEFAULT_TTL=1800
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# Optional
DEBUG=false
LOG_FORMAT=TEXT   # TEXT or JSON
LOG_LEVEL=INFO
```

**5. Apply the database schema**

```bash
mysql -u root -p < schema.sql
```

**6. Start the server**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

### Option 2: Docker Setup (Recommended)

**1. Clone the repository**

```bash
git clone https://github.com/Yahg0h/booking-engine.git
cd booking-engine
```

**2. Configure environment variables**

Edit `.env` with your desired secrets before starting the containers. At minimum, update:

```env
JWT_SECRET=your_very_long_random_secret
REDIS_SECRET_KEY=your_redis_secret
```

**3. Start all services**

```bash
docker compose up --build
```

This will start three services:
- `booking_engine_db` — MySQL 8.0, initialized automatically from `schema.sql`
- `booking_engine_redis` — Redis cache and lock store
- `booking_engine_api` — FastAPI application on port `8000`

The API container waits for both MySQL and Redis to pass health checks before starting.

**4. Verify the API is running**

```bash
curl http://localhost:8000/health
```

**Stop the containers:**

```bash
docker compose down
```

**Stop and remove volumes (resets database):**

```bash
docker compose down -v
```

---

## Continuous Integration

The CI pipeline is defined in [`.github/workflows/ci.yml`](.github/workflows/ci.yml) and runs on every push to `main`, `develop`, or any `feature/**` branch, and on pull requests to `main` or `develop`.

The pipeline performs the following steps in order:

| Step | Description |
|---|---|
| **Checkout** | Fetches the repository code |
| **Setup Python 3.14** | Installs Python with pip caching enabled |
| **Install dependencies** | Installs `requirements.txt` plus test tools (`pytest`, `pytest-asyncio`, `pytest-cov`, `ruff`, `mypy`) |
| **Wait for MySQL** | Polls until the MySQL service container is accepting connections (up to 30 attempts) |
| **Wait for Redis** | Polls until the Redis service container responds to `PING` |
| **Apply schema** | Creates the `booking_engine` database and runs `schema.sql` using PyMySQL |
| **Run tests** | Executes the full test suite with coverage reporting (`--cov=app --cov-report=xml`) |
| **Upload coverage** | Sends the coverage report to Codecov |
| **Lint with Ruff** | Checks `app/` and `tests/` for style and error rules (`E`, `W`, `F`). Non-blocking. |
| **Type checking with Mypy** | Runs static type analysis on `app/`. Non-blocking. |
| **Summary** | Prints a completion message regardless of step outcomes |

The test environment variables (database host, JWT secret, Redis credentials) are injected directly into the test runner step — no `.env` file is used in CI.

⚠️ **Critical Warning for Testing Setup**

The `api_register_root()` helper in `conftest.py:157` executes `DELETE FROM users WHERE role = 'ROOT'` to ensure tests run without duplicate ROOT account conflicts.

**Risk:** If tests are run against a **production** database, **all ROOT accounts will be permanently removed**.

**How ​​it works:**
1. Attempts to log in using fixed credentials (`root_test_fixed@bookingengine.com` / `rootpass_fixed_123`)
2. If it receives a 401 (account exists but password differs), it deletes ALL ROOT accounts and recreates the test account
3. If it receives a 409 (email already registered), it likewise deletes all ROOT accounts and recreates the test account

**How ​​to protect yourself:**
- Use `.env.test` or a `DATABASE_URL` variable pointing exclusively to a **test** database
- Never run `pytest` against production connections
- If accidentally run in production:
  - Delete the account created by the test (`root_test_fixed@bookingengine.com`)
  - Recover the password/email for the original ROOT account

---

## Routes

All routes are prefixed with `/v1`. The API also exposes `/` (welcome) and `/health` (status check) at the root level.

Authentication uses **JWT Bearer tokens**. Obtain a token via `POST /v1/login` and include it in the `Authorization: Bearer <token>` header.

---

### Auth

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/v1/register` | Register a new user account | Optional |
| `POST` | `/v1/login` | Authenticate and receive a JWT token | No |

---

### Users

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/users` | Create a STAFF user account | OWNER / ROOT |
| `POST` | `/v1/users/owners` | Create an OWNER user account | ROOT only |
| `GET` | `/v1/users` | List users (filtered by role/status) | OWNER / ROOT |
| `GET` | `/v1/users/{id}` | Get a specific user | OWNER / ROOT |
| `PATCH` | `/v1/users/{id}` | Update own profile (requires current password) | Self only |
| `PATCH` | `/v1/users/admin/update/{id}` | Admin update of any user | OWNER / ROOT |
| `DELETE` | `/v1/users/{id}` | Deactivate a user account | OWNER / ROOT |

---

### Organizations

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/organizations` | Create an organization | ROOT only |
| `GET` | `/v1/organizations/{id}` | Get organization details | OWNER / ROOT |
| `PATCH` | `/v1/organizations/{id}` | Update organization details | OWNER / ROOT |
| `GET` | `/v1/organizations/{id}/settings` | Get organization settings | OWNER / ROOT |
| `PATCH` | `/v1/organizations/{id}/settings` | Update organization settings | OWNER / ROOT |

---

### Professionals

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/professionals` | Create a professional | OWNER / ROOT |
| `GET` | `/v1/professionals` | List professionals in an organization | OWNER / ROOT |
| `GET` | `/v1/professionals/all` | List all professionals across all orgs | ROOT only |
| `GET` | `/v1/professionals/{id}` | Get public professional info | Public |
| `PATCH` | `/v1/professionals/{id}` | Update a professional | OWNER / ROOT |
| `DELETE` | `/v1/professionals/{id}` | Deactivate a professional | OWNER / ROOT |

**Working Hours**

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/professionals/{id}/working-hours` | Add a working hours entry | OWNER / ROOT |
| `GET` | `/v1/professionals/{professional_id}/working-hours` | List working hours | Public |
| `PATCH` | `/v1/professionals/{professional_id}/working-hours/{id}` | Update a working hours entry | OWNER / ROOT |

**Blackouts**

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/professionals/{id}/blackouts` | Create a blackout request | Professional (self) |
| `GET` | `/v1/professionals/{id}/blackouts` | List blackouts for a professional | OWNER / ROOT |
| `GET` | `/v1/professionals/blackouts/{id}` | Get a specific blackout | OWNER / ROOT |
| `POST` | `/v1/blackouts/{id}/approve` | Approve a blackout | OWNER / ROOT |
| `POST` | `/v1/blackouts/{id}/reject` | Reject a blackout | OWNER / ROOT |

**Professional–Procedure Assignments**

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/professionals/{id}/procedures` | Assign a procedure to a professional | OWNER / ROOT |
| `GET` | `/v1/professionals/{id}/procedures` | List procedures assigned to a professional | OWNER / ROOT |
| `PATCH` | `/v1/professionals/{id}/procedures/{procedure_id}` | Update assignment (toggle active) | OWNER / ROOT |

---

### Procedures

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/procedures` | Create a procedure | OWNER / ROOT |
| `GET` | `/v1/procedures` | List procedures in an organization | Public |
| `GET` | `/v1/procedures/{id}` | Get a specific procedure | Public |
| `PATCH` | `/v1/procedures/{id}` | Update a procedure | OWNER / ROOT |
| `DELETE` | `/v1/procedures/{id}` | Deactivate a procedure | OWNER / ROOT |

---

### Customers

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/customers` | Create a customer | OWNER / STAFF / ROOT |
| `GET` | `/v1/customers` | List customers in an organization | OWNER / STAFF / ROOT |
| `GET` | `/v1/customers/{id}` | Get a specific customer | OWNER / STAFF / ROOT |
| `PATCH` | `/v1/customers/{id}` | Update customer information | OWNER / STAFF / ROOT |
| `DELETE` | `/v1/customers/{id}` | Deactivate a customer | OWNER / ROOT |

---

### Availability

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/v1/availability` | Get available booking slots for a given date | No |

Query parameters: `organization_id`, `professional_id`, `procedure_id`, `date`

---

### Appointments

| Method | Endpoint | Description | Access |
|---|---|---|---|
| `POST` | `/v1/appointments` | Book an appointment | OWNER / STAFF / ROOT |
| `GET` | `/v1/appointments` | List appointments with filters | OWNER / STAFF / ROOT |
| `GET` | `/v1/appointments/{id}` | Get a specific appointment | OWNER / STAFF / ROOT |
| `PATCH` | `/v1/appointments/{id}` | Update an appointment | OWNER / STAFF / ROOT |
| `DELETE` | `/v1/appointments/{id}` | Cancel an appointment | OWNER / STAFF / ROOT |

---

### Statistics *(ROOT only)*

All statistics routes are prefixed with `/v1/root` and results are cached in Redis.

| Method | Endpoint | Description | Cache TTL |
|---|---|---|---|
| `GET` | `/v1/root/statistics/appointments/global` | Appointment metrics across all organizations | 5 min |
| `GET` | `/v1/root/statistics/revenue/global` | Revenue metrics across all organizations | 10 min |
| `GET` | `/v1/root/statistics/customers/global` | Customer metrics across all organizations | 15 min |
| `GET` | `/v1/root/statistics/appointments/{organization_id}` | Appointment metrics for one organization | 5 min |
| `GET` | `/v1/root/statistics/revenue/{organization_id}` | Revenue metrics for one organization | 10 min |
| `GET` | `/v1/root/statistics/customers/{organization_id}` | Customer metrics for one organization | 15 min |

Query parameters: `start_date`, `end_date` (all); `group_by=week\|month\|year` (revenue only)

---

### Reports *(ROOT only)*

All report routes are prefixed with `/v1/root` and return a streaming `application/pdf` or `text/csv` file.

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/v1/root/reports/appointments/global` | Download global appointments report |
| `GET` | `/v1/root/reports/revenue/global` | Download global revenue report |
| `GET` | `/v1/root/reports/customers/global` | Download global customers report |

Query parameters: `format=pdf\|csv`, `start_date`, `end_date`, `professional_id`, `customer_id` (appointments/customers), `group_by` (revenue)

---

## Architecture

### How Routes Handle HTTP Errors

Routes are intentionally thin. They validate authorization, check for the existence of resources, and delegate all business logic to the service layer. HTTP errors are raised using FastAPI's `HTTPException` with explicit status codes:

```python
# Resource not found
if not resource:
    raise HTTPException(status_code=404, detail="Resource not found.")

# Unauthorized access
if not await check_access(user_id, org_id):
    raise HTTPException(status_code=403, detail="You aren't allowed to perform this action.")

# Business rule violation (from service layer)
try:
    result = await some_service(...)
except ValueError as e:
    raise HTTPException(status_code=409, detail=str(e))
```

Business rule violations (e.g., double-booking, cancellation policy violations) are raised as `ValueError` inside services and caught in the route, converted to `409 Conflict` or `422 Unprocessable Entity` as appropriate. This keeps HTTP concerns in the route layer and business logic in the service layer.

---

### What Services Do

Services are the core of the application. They contain all database queries and business rules. They are fully decoupled from HTTP — they raise `ValueError` for domain rule violations and return plain Python dicts or primitive values.

Examples of responsibilities:

- **`availability_service`** — Calculates open time slots for a professional on a given date, factoring in working hours, existing appointments, buffer time, and blackout periods.
- **`appointment_service`** — Acquires a Redis distributed lock before checking availability, preventing race conditions when two requests target the same slot simultaneously.
- **`audit_service`** — Records every state mutation to `audit_logs`, including actor identity, old and new values, and the requesting IP address.
- **`permission_service`** — Provides reusable helpers (`is_root`, `is_owner`) consumed by routes to enforce RBAC.
- **`cache_service`** — Redis utility layer. Provides distributed advisory locks (`acquire_lock` / `release_lock`) via `SET NX EX`, a `@cached(ttl)` decorator for GET route caching, manual `get_cached` / `set_cached` / `delete_cached` helpers, and a batch `invalidate_pattern` function. Includes a custom JSON serializer that handles `datetime`, `Decimal`, pandas `DataFrame` and `Series` objects.

---

### What Pydantic Schemas Do

All schemas live in [`app/api/v1/schemas/schemas.py`](app/api/v1/schemas/schemas.py). They serve three purposes:

**1. Request validation** — FastAPI automatically validates incoming request bodies against the schema before the route handler runs. Invalid payloads return `422 Unprocessable Entity` with structured error details.

**2. Business rule validation** — Schemas use `@model_validator` to enforce cross-field rules that cannot be expressed as simple field constraints:

```python
class OrganizationBase(BaseModel):
    min_work_time: time
    max_work_time: time

    @model_validator(mode="after")
    def validate_work_time(self) -> "OrganizationBase":
        if self.min_work_time >= self.max_work_time:
            raise ValueError("min_work_time must be before max_work_time.")
        return self
```

**3. Response serialization** — `*Response` schemas with `model_config = ConfigDict(from_attributes=True)` map SQLAlchemy row results directly to structured JSON responses, preventing accidental exposure of sensitive fields like `password_hash`.

Each entity follows the pattern:
- `*Base` — shared fields
- `*Create` — fields required for creation
- `*Update` — all fields optional (partial update / PATCH)
- `*Response` — fields returned to the client (includes `id`, timestamps)

---

### Role-Based Access Control (RBAC)

Booking Engine implements a three-tier role system designed for multi-tenant SaaS operations:

#### ROOT
- **Scope**: Global, no organization
- **Responsibilities**: 
  - Create and manage Organizations
  - Create OWNER accounts (the only user who can do this)
  - Emergency access and system-level administration
- **Usage**: Typically one ROOT account per deployment; used only for initial setup and critical operations
- **Security**: ROOT has unrestricted access—handle credentials carefully in production

#### OWNER
- **Scope**: Single organization
- **Responsibilities**:
  - Manage Staff accounts within the organization
  - Configure organization settings (operating weekdays, cancellation buffer)
  - Approve or reject blackouts (staff availability blocks)
  - View all appointments, customers, and professionals within the organization
  - Perform administrative tasks (create/update/delete procedures, professionals, customers)
- **Usage**: One per organization; typically the business administrator
- **Permissions**: Cannot create other Organizations or OWNER accounts

#### STAFF
- **Scope**: Single organization, assigned professional profile
- **Responsibilities**:
  - View own appointments and schedule
  - Create blackouts (pending Owner approval)
  - View customers who have booked with them
- **Usage**: One per professional (e.g., therapist, stylist, consultant)
- **Permissions**: Limited to own professional data; cannot create other Staff accounts or manage organization-wide settings

---

### Professional Buffer Time

Applies a configurable buffer time (`buffer_time_minutes`) to manage setup/teardown between appointments:

#### How Buffer Works

1. **Appointment Duration**: The procedure itself (e.g., 60-minute massage)
2. **Buffer Application**: After the appointment `end_at`, add buffer time
3. **Slot Calculation**: When checking availability for a new appointment:
   - Required duration = procedure duration + professional buffer
   - Example: 60-minute procedure + 15-minute buffer = 75-minute slot needed

#### Example Timeline

- Professional: Dr. Silva (buffer_time_minutes = 15)
- Procedure: Consultation (30 minutes)

- Appointment 1:

- Start: 10:00 | End: 10:30
- Blocked until: 10:45 (end + buffer)

- Available from: 10:45

- Next appointment can be scheduled at: 10:45 (the system checks 10:45 + 30min = 11:15 fits)


#### Why Buffer Matters

- **Setup time**: Cleaning, preparing materials, reviewing notes
- **Transition time**: Moving between clients, mental reset
- **Prevents back-to-back exhaustion**: Staff has breathing room
- **Reduces no-shows**: Realistic scheduling improves reliability

---

### Idempotency Keys

Ensures safe retries for critical write operations. The `Idempotent-Key` header (UUID v4) must be included in POST and PATCH requests to prevent duplicate records.

**Critical routes** requiring idempotency:
- `POST /v1/appointments`
- `POST /v1/customers`
- `POST /v1/professionals/{id}/blackouts`
- `POST /v1/professionals/{id}/procedures`
- `PATCH /v1/appointments/{id}`
- `PATCH /v1/customers/{id}`
- `PATCH /v1/organizations/{id}/settings`

**Example usage**:

```bash
curl -X POST http://localhost:8000/v1/appointments \
  -H "Authorization: Bearer <token>" \
  -H "Idempotent-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Content-Type: application/json" \
  -d '{
    "professional_id": 1,
    "customer_id": 2,
    "procedure_id": 3,
    "start_at": "2025-01-15T10:00:00Z"
  }'
```

**Implementation**:
- Middleware captures request body, extracts `Idempotent-Key`, and checks Redis cache
- Cache key format: `idempotency:{org_id}:{idempotency_key}`
- TTL: 5 minutes (300 seconds)
- Returns cached response if key exists; stores full response (success or error) after first execution
- Non-critical routes ignore missing headers; critical routes return `400 Bad Request`

---

### Redis Cache Management

Multi-tier caching strategy with smart invalidation to reduce database load while maintaining data freshness.

**Tiered TTL strategy**:

| Data Type | TTL | Use Case |
|-----------|-----|----------|
| Appointments, Availability, Blackouts | 5 seconds | Real-time data |
| Customers, Professionals, Users | 3 minutes | Moderate change frequency |
| Procedures, Org Settings | 30 minutes | Stable configuration |

**Cache key patterns**:
- `org:{org_id}:appointments:*`
- `org:{org_id}:professionals:*`
- `org:{org_id}:availability:prof:{prof_id}:*`
- `org:{org_id}:customers:{cust_id}:*`

**Invalidation matrix** (automatic on mutations):

| Resource | Invalidates |
|----------|-------------|
| Procedure | `org:{id}:procedures:*`, `org:{id}:availability:*` |
| Professional | `org:{id}:professionals:*`, `org:{id}:availability:prof:{prof_id}:*` |
| Appointment | `org:{id}:availability:prof:{prof_id}:*`, `org:{id}:appointments:customer:{cust_id}:*` |
| Working Hours / Blackouts | `org:{id}:availability:prof:{prof_id}:*` |

**Cache configuration** (`.env`):

```env
# Cache TTL in seconds (default: 1800)
CACHE_DEFAULT_TTL=1800

# Redis connection
REDIS_URL=redis://localhost:6379/0
```

**Cached endpoints** use `@cached(ttl=...)` decorator on GET routes:

```python
@router.get("/v1/organizations/{org_id}/appointments")
@cached(ttl=300)  # 5 minutes
async def list_appointments(org_id: int, ...):
    ...
```

**Custom JSON serializer** supports:
- `datetime`, `date` objects
- pandas `Timestamp`, `Decimal`, `DataFrame`, `Series`
- Automatic conversion during cache write/read

> The report routes (`routes/root/reports.py` at the root level and `organizations.py` at the organization level) use manual caching with `set-cached` instead of the decorator.

---

### Statistics & Analytics Endpoints

Real-time metrics aggregation for appointments, revenue, and customers with flexible date-range filtering.

**Available metrics**:

| Metric | Scope | Dimensions |
|--------|-------|-----------|
| Appointments | Org / Global | total, completed, cancelled, no_show, rates |
| Revenue | Org / Global | estimated (all), concrete (completed), grouped by week/month/year |
| Customers | Org / Global | unique per professional, engaged, inactive, rates |

**Routes**:

```
# Organization-level
GET /v1/organizations/{org_id}/statistics/appointments?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
GET /v1/organizations/{org_id}/statistics/revenue?start_date&end_date&group_by=week|month|year
GET /v1/organizations/{org_id}/statistics/customers?start_date&end_date

# Global (ROOT-only)
GET /root/statistics/appointments/global?start_date&end_date
GET /root/statistics/revenue/global?start_date&end_date&group_by
GET /root/statistics/customers/global?start_date&end_date
GET /root/statistics/appointments/{organization_id}
GET /root/statistics/revenue/{organization_id}
GET /root/statistics/customers/{organization_id}
```

**Default periods** (if not specified):
- Appointments, Customers: last 30 days
- Revenue: week=7 days, month=30 days, year=365 days

**Rate limiting**: 5 requests/minute per user

**Cache TTL**: 5 minutes (appointments), 10 minutes (revenue), 15 minutes (customers)

**Example request**:

```bash
curl -X GET "http://localhost:8000/v1/organizations/1/statistics/revenue?start_date=2025-01-01&end_date=2025-01-31&group_by=week" \
  -H "Authorization: Bearer <token>"
```

**Response structure**:

```json
{
  "period": {
    "start_date": "2025-01-01",
    "end_date": "2025-01-31"
  },
  "metrics": {
    "estimated_revenue": 5000.00,
    "concrete_revenue": 3200.50,
    "week_of_2025_01_01": 800.00,
    "week_of_2025_01_08": 950.50,
    ...
  }
}
```

---

### Advanced Reporting

PDF and CSV report generation with metadata, summary metrics, and optional detailed data export.

**Report types**:
- **Appointments**: total, completed, cancelled, no_show counts and rates
- **Revenue**: estimated vs concrete, groupable by week/month/year
- **Customers**: unique per professional, active/inactive, engagement rates

**Routes**:

```
# Organization-level
GET /v1/organizations/{org_id}/reports/appointments?format=pdf|csv&start_date&end_date&professional_id&customer_id
GET /v1/organizations/{org_id}/reports/revenue?format=pdf|csv&start_date&end_date&professional_id&group_by
GET /v1/organizations/{org_id}/reports/customers?format=pdf|csv&start_date&end_date&professional_id

# Global (ROOT-only)
GET /root/reports/appointments/global?format=pdf|csv&start_date&end_date&professional_id&customer_id
GET /root/reports/revenue/global?format=pdf|csv&start_date&end_date&professional_id&group_by
GET /root/reports/customers/global?format=pdf|csv&start_date&end_date&professional_id
```

**Report structure**:

1. **Metadata** (PDF + CSV header): title, generation timestamp, organization ID, period, applied filters
2. **Summary** (PDF + CSV): key metrics in human-readable format
3. **Detailed data** (CSV only): full dataset for further analysis

**Rate limiting**: 2 requests/minute (reports are compute-heavy)

**Cache TTL**: 5 minutes (data changes frequently)

**Example request**:

```bash
# PDF export
curl -X GET "http://localhost:8000/v1/organizations/1/reports/appointments?format=pdf&start_date=2025-01-01&end_date=2025-01-31" \
  -H "Authorization: Bearer <token>" \
  -o appointments_report.pdf

# CSV export with filters
curl -X GET "http://localhost:8000/root/reports/revenue/global?format=csv&start_date=2025-01-01&end_date=2025-01-31&professional_id=5&group_by=week" \
  -H "Authorization: Bearer <token>" \
  -o revenue_report.csv
```

**PDF content**:
- Metadata section with title, date, organization, period, and filters
- Summary metrics (readable format)
- No charts or data tables (avoid duplication with CSV)

**CSV content**:
- Metadata header (title, date, organization, period, filters)
- Summary section (metrics)
- Detailed data table (raw query results for analysis)

---

## Synchronous Pandas in an Async Environment

Booking Engine executes synchronous pandas operations within a FastAPI/asyncio environment using `asyncio.to_thread()`, which offloads CPU-bound work to a thread pool without blocking the event loop.

### Why synchronous pandas is necessary

pandas does not have native async support. `pd.read_sql()` is synchronous and would block the event loop if executed directly inside a coroutine, causing timeouts for other requests.

### Implementation

In `statistics_service.py`:

```python
import asyncio
from sqlalchemy import create_engine, text

# Dedicated synchronous engine for pandas
engine_sync = create_engine(
    DATABASE_URL.replace("+aiomysql", "+pymysql"),
    pool_size=5,
    max_overflow=10
)

async def _read_sql_sync(query: str, params: dict = None) -> pd.DataFrame:
    """Executes a synchronous SQL query in a thread pool and returns a DataFrame."""
    def sync_read():
        with engine_sync.begin() as conn:
            result = conn.execute(text(query), params or {})
            return pd.DataFrame(result.mappings())
    
    # to_thread() moves the function to a thread pool and returns an awaitable
    return await asyncio.to_thread(sync_read)

async def get_appointments_statistics(org_id: int | None, start_date, end_date) -> dict:
    """Service that utilizes synchronous pandas."""
    query = """
        SELECT status, COUNT(*) as count
        FROM appointments
        WHERE start_at BETWEEN :start AND :end
        {'AND organization_id = :org_id' if org_id else ''}
        GROUP BY status
    """
    
    # Executes pandas in a separate thread
    df = await _read_sql_sync(query, {
        'start': start_date,
        'end': end_date,
        'org_id': org_id
    })
    
    # Processes the DataFrame (also within thread pool)
    return {
        'total': len(df),
        'completed': int(df[df['status'] == 'COMPLETED']['count'].sum()),
        'cancelled': int(df[df['status'] == 'CANCELLED']['count'].sum()),
    }
```

### How it works

1. **Request arrives** → FastAPI route is async
2. **`await asyncio.to_thread(sync_read)` call** → task sends `sync_read()` to the thread pool
3. **Event loop remains free** → handles other incoming requests while the thread executes pandas
4. **Thread finishes** → returns the DataFrame, `await` unblocks and resumes processing
5. **Response sent** → data reaches the client

### Advantages

- Pandas uses NumPy (C bindings) — very fast in threads
- Event loop never blocks; 100 concurrent requests work smoothly
- No changes required to pandas code (uses standard `pd.read_sql()`)

### Limitations

- Small thread pool (`pool_size=5`) — too many heavy queries may stall processing
- In-memory Pandas — large DataFrames (>1GB) can cause Out Of Memory (OOM) errors
- No caching → every statistics request re-executes the entire query

---

### Data Retention & Compliance (GDPR/CCPA)

This project implements **soft-delete-only** architecture for data retention, prioritizing compliance and auditability:

#### Retention Strategy

- **Soft Delete Only**: Records marked `is_active=false` are never physically deleted from the database
- **Audit Trail Preserved**: All changes logged in `audit_logs` table indefinitely
- **Owner Control**: Owners can remove accounts (users, professionals) via soft delete without data destruction
- **Query Filtering**: GET endpoints exclude inactive records by default; explicit `is_active=false` query required to view deleted data

#### GDPR/CCPA Compliance

**Right to be Forgotten (GDPR Article 17)**
- Soft delete allows "logical deletion"—data is hidden from normal operations
- Audit logs document the deletion action itself
- Trade-off: Complete data destruction not supported; clients requiring absolute deletion must handle via extended data policies

**Data Minimization (GDPR Article 5)**
- `is_active` filtering reduces unnecessary data exposure
- Owners can query only relevant periods using date-range filters
- Audit logs capture only fields that changed, not full records

**Accountability (GDPR Article 5.2)**
- Every data modification tracked: actor, timestamp, old/new values, IP address
- Enables compliance reporting for data access/modification audits

**Data Subject Requests**
- When a customer requests data export, query all `is_active=true` records + audit logs for that subject
- Soft-deleted records can be included if retention policy requires it

#### Limitations & Trade-offs

| Aspect | Decision | Trade-off |
|--------|----------|-----------|
| **Hard Delete** | Not supported by design | Clients needing absolute destruction must implement separately |
| **Storage Growth** | Indefinite retention | Database grows over time; consider archival strategies for 5+ year-old data |
| **Right to Erasure** | Logical deletion only | Not true GDPR erasure |
| **Performance** | `is_active` indexed | Query overhead minimal; indexes optimize filtering |

#### Recommended Practices

1. **Data Export Process**: Query `is_active=true` records + related audit logs for compliance requests
2. **Retention Window**: Consider archiving audit logs older than 7 years to optimize storage
3. **Deletion Workflows**: Document approval process for soft-deletes in your data retention policy
4. **Legal Review**: If used in production, have a GDPR/CCPA counsel review soft-delete strategy for your region

---

### Key Design Decisions & Trade-offs

#### 1. Soft Delete vs. Hard Delete

**Decision**: Soft delete only (no hard delete)

**Rationale**:
- Preserves audit trail—critical for compliance and dispute resolution
- Enables account recovery without data loss
- Supports GDPR compliance (data minimization via filtering, not destruction)
- Simple implementation: single `is_active` flag vs. cascading deletes

**Trade-off**: Database grows indefinitely; clients cannot achieve true data erasure

---

#### 2. Multi-Tenant Architecture

**Decision**: Organization as root entity; all data scoped to organization

**Rationale**:
- Enables one deployment to serve multiple businesses
- Clear data isolation at query level
- Supports OWNER-driven configuration (operating hours, cancellation policy)

**Trade-off**: Requires careful authorization checks on every route; risk of data leakage if `organization_id` validation missed

---

#### 3. Operating Weekdays as Config (Not DB Persisted)

**Decision**: `operating_weekdays` stored in `organization_settings` table (JSON)

**Rationale**:
- Rarely changes (set once, stable for months/years)
- Centralized in settings table alongside other org preferences
- Validated at availability calculation time, not at booking time

**Trade-off**: Changes to operating hours may affect already-scheduled appointments; clients must handle migration logic

---

#### 4. Appointment Status Enum (No `is_active`)

**Decision**: Use `status ENUM('SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW')` instead of `is_active`

**Rationale**:
- Semantic clarity: status describes the appointment lifecycle, not presence
- Enables business logic (cancel vs. no-show are distinct)
- Better reporting: count by status, not just active/inactive

**Trade-off**: Soft deletes require a separate `is_active` flag for users/professionals; inconsistent with appointments

---

#### 5. Distributed Locking for Overbooking Prevention

**Decision**: Redis `SET nx ex` pattern; Redlock deemed overkill

**Rationale**:
- Single-server personal project; Redlock complexity not justified
- 60-second lock timeout balances safety and user experience
- Lock key includes professional ID + timestamp → granular per-slot

**Trade-off**: Not production-ready for multi-server deployments; upgrade to Redlock or database-level locks if scaling to HA

---

#### 6. Logging: Routes vs. Services

**Decision**: Application logs + audit logs both belong in routes, not services

**Rationale**:
- Generated IDs (appointment_id, user_id) available after operation completes
- Consistent log structure across all endpoints
- Services remain stateless and testable
- Separation of concerns: services handle business logic, routes handle observability

**Trade-off**: Duplicate logging code across routes; mitigate with shared logging utilities

---

#### 7. Rate Limiting Strategy

**Decision**: Tiered rate limits by endpoint criticality (e.g. Auth: 5/min, Appointments: 20/min, Customers: 50/min)

**Rationale**:
- Brute-force protection on sensitive endpoints (login, organization creation)
- Prevents overbooking spam via appointment creation
- Balances security and usability

**Trade-off**: May frustrate legitimate bulk operations; no API key / quota system for power users

---

## Troubleshooting

### `Connection refused` on startup

Ensure MySQL and Redis are running and reachable. In the local setup, verify the values in `.env` match your running services. In Docker, the `api` container waits for health checks to pass — check container logs with:

```bash
docker compose logs api
docker compose logs db
docker compose logs redis
```

---

### `422 Unprocessable Entity` on requests

Pydantic validation failed. Check the response body for the `detail` field — it will contain the exact field and error message. Common causes:
- Missing required fields
- `min_work_time` >= `max_work_time`
- `operating_weekdays` containing values outside 1–7
- Customer with no email and no phone
- Appointment `start_at` set in the past

---

### `409 Conflict` when booking

Either the selected time slot is no longer available (already booked or falls inside a blackout/buffer), or another request acquired the Redis lock for that slot at the same time. Retry with a different time slot.

---

### `422` on appointment cancellation

The organization's `cancellation_buffer_hours` policy is being violated. The appointment cannot be cancelled within the configured buffer window before the scheduled time. Check the organization settings for the configured buffer value.

---

### `403 Forbidden` unexpectedly

Verify that:
1. Your JWT token is valid and not expired (default: 24 hours / 1440 minutes)
2. Your user account has the correct `role` for the operation
3. Your `organization_id` matches the resource you are trying to access
4. Your account `is_active` is `true`

---

### MySQL authentication errors in Docker

The Docker image installs the `cryptography` package explicitly to support MySQL 8.0's `caching_sha2_password` authentication plugin. If you see authentication errors outside Docker, ensure `cryptography` is installed in your local environment:

```bash
pip install cryptography
```

---

### Tests failing locally

Ensure a local MySQL instance and Redis are running, and that the test environment variables are set. The test suite uses the same database configured in `.env`. Alternatively, use the Docker Compose setup which mirrors the CI environment:

```bash
docker compose up db redis -d
python -m pytest tests/ -v
```

---

## License

This project is licensed under the [MIT License](LICENSE).

---

## Author

**Yahgoh**  
GitHub: [@Yahg0h](https://github.com/Yahg0h)  
Repository: [https://github.com/Yahg0h/booking-engine](https://github.com/Yahg0h/booking-engine)
