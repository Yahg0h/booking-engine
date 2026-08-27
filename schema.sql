-- ============================================================
-- BookingEngine - MySQL Schema (simplified / compatibility-first)
-- Recommended: MySQL 8.0+, but avoids CHECK constraints and
-- newer-only collation choices where possible.
-- ============================================================

CREATE DATABASE IF NOT EXISTS booking_engine
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE booking_engine;

-- ============================================================
-- 1. ORGANIZATIONS
-- ============================================================

CREATE TABLE organizations (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    slug VARCHAR(150) NOT NULL,
    min_work_time TIME NOT NULL,
    max_work_time TIME NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_organizations_slug (slug)
) ENGINE=InnoDB;

-- ============================================================
-- 2. USERS
-- ============================================================
-- ROOT has organization_id = NULL.
-- OWNER and STAFF must have organization_id set.
-- The ROOT/OWNER/STAFF organization rule is enforced by the backend.

CREATE TABLE users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NULL,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('ROOT', 'OWNER', 'STAFF') NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_organization (organization_id),
    KEY idx_users_organization_role (organization_id, role),

    CONSTRAINT fk_users_organization
        FOREIGN KEY (organization_id)
        REFERENCES organizations (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ============================================================
-- 3. PROFESSIONALS
-- ============================================================
-- user_id is optional. If the linked User is removed, the professional
-- remains and user_id becomes NULL. Cross-organization consistency
-- (professional.organization_id == user.organization_id) is enforced
-- by the backend.

CREATE TABLE professionals (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NOT NULL,
    user_id BIGINT UNSIGNED NULL,
    name VARCHAR(150) NOT NULL,
    buffer_time_minutes SMALLINT UNSIGNED NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_professionals_user (user_id),
    KEY idx_professionals_organization (organization_id),
    KEY idx_professionals_org_active (organization_id, is_active),

    CONSTRAINT fk_professionals_organization
        FOREIGN KEY (organization_id)
        REFERENCES organizations (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_professionals_user
        FOREIGN KEY (user_id)
        REFERENCES users (id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- 4. PROCEDURES
-- ============================================================

CREATE TABLE procedures (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(150) NOT NULL,
    description TEXT NULL,
    duration_minutes SMALLINT UNSIGNED NOT NULL,
    price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_procedures_org_name (organization_id, name),
    KEY idx_procedures_organization (organization_id),
    KEY idx_procedures_org_active (organization_id, is_active),

    CONSTRAINT fk_procedures_organization
        FOREIGN KEY (organization_id)
        REFERENCES organizations (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ============================================================
-- 5. PROFESSIONAL_PROCEDURES
-- ============================================================
-- Many-to-many relation between professionals and procedures.
-- Organization consistency is enforced by the backend.

CREATE TABLE professional_procedures (
    organization_id BIGINT UNSIGNED NOT NULL,
    professional_id BIGINT UNSIGNED NOT NULL,
    procedure_id BIGINT UNSIGNED NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (professional_id, procedure_id),
    KEY idx_professional_procedures_organization (organization_id),
    KEY idx_professional_procedures_procedure (procedure_id),
    KEY idx_professional_procedures_org_active (organization_id, is_active),

    CONSTRAINT fk_professional_procedures_organization
        FOREIGN KEY (organization_id)
        REFERENCES organizations (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_professional_procedures_professional
        FOREIGN KEY (professional_id)
        REFERENCES professionals (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE,

    CONSTRAINT fk_professional_procedures_procedure
        FOREIGN KEY (procedure_id)
        REFERENCES procedures (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ============================================================
-- 6. WORKING_HOURS
-- ============================================================
-- Exactly one interval per weekday per professional is enforced
-- by UNIQUE(professional_id, weekday).
-- weekday convention: 1 = Sunday ... 7 = Saturday.

CREATE TABLE working_hours (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    professional_id BIGINT UNSIGNED NOT NULL,
    weekday TINYINT UNSIGNED NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    UNIQUE KEY uq_working_hours_professional_weekday (professional_id, weekday),
    KEY idx_working_hours_professional (professional_id),
    KEY idx_working_hours_professional_active (professional_id, is_active),

    CONSTRAINT fk_working_hours_professional
        FOREIGN KEY (professional_id)
        REFERENCES professionals (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 7. BLACKOUTS
-- ============================================================

CREATE TABLE blackouts (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    professional_id BIGINT UNSIGNED NOT NULL,
    start_at DATETIME NOT NULL,
    end_at DATETIME NOT NULL,
    reason VARCHAR(255) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_blackouts_professional (professional_id),
    KEY idx_blackouts_professional_period (professional_id, start_at, end_at),

    CONSTRAINT fk_blackouts_professional
        FOREIGN KEY (professional_id)
        REFERENCES professionals (id)
        ON UPDATE CASCADE
        ON DELETE CASCADE
) ENGINE=InnoDB;

-- ============================================================
-- 8. CUSTOMERS
-- ============================================================

CREATE TABLE customers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NOT NULL,
    name VARCHAR(150) NOT NULL,
    email VARCHAR(255) NULL,
    phone VARCHAR(30) NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_appointment_at DATETIME NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_customers_organization (organization_id),
    KEY idx_customers_org_active (organization_id, is_active),
    KEY idx_customers_org_email (organization_id, email),
    KEY idx_customers_org_phone (organization_id, phone),

    CONSTRAINT fk_customers_organization
        FOREIGN KEY (organization_id)
        REFERENCES organizations (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ============================================================
-- 9. APPOINTMENTS
-- ============================================================
-- start_at/end_at represent the procedure's actual reserved time.
-- Professional buffer is handled by the Availability/Booking logic,
-- not added to end_at.
-- Cross-organization consistency is enforced by the backend.

CREATE TABLE appointments (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NOT NULL,
    customer_id BIGINT UNSIGNED NOT NULL,
    professional_id BIGINT UNSIGNED NOT NULL,
    procedure_id BIGINT UNSIGNED NOT NULL,
    start_at DATETIME NOT NULL,
    end_at DATETIME NOT NULL,
    status ENUM('SCHEDULED', 'COMPLETED', 'CANCELLED', 'NO_SHOW') NOT NULL DEFAULT 'SCHEDULED',
    notes TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_appointments_organization (organization_id),
    KEY idx_appointments_org_date (organization_id, start_at, end_at),
    KEY idx_appointments_professional_date (professional_id, start_at, end_at),
    KEY idx_appointments_customer_date (customer_id, start_at),
    KEY idx_appointments_professional_status (professional_id, status, start_at),
    KEY idx_appointments_org_status (organization_id, status, start_at),

    CONSTRAINT fk_appointments_organization
        FOREIGN KEY (organization_id)
        REFERENCES organizations (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_appointments_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_appointments_professional
        FOREIGN KEY (professional_id)
        REFERENCES professionals (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_appointments_procedure
        FOREIGN KEY (procedure_id)
        REFERENCES procedures (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT
) ENGINE=InnoDB;

-- ============================================================
-- 10. AUDIT_LOGS
-- ============================================================
-- Append-only by application policy.
-- old_values/new_values are native MySQL JSON columns.

CREATE TABLE audit_logs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    organization_id BIGINT UNSIGNED NULL,
    actor_user_id BIGINT UNSIGNED NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(100) NOT NULL,
    entity_id BIGINT UNSIGNED NULL,
    old_values JSON NULL,
    new_values JSON NULL,
    metadata JSON NULL,
    ip_address VARCHAR(45) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (id),
    KEY idx_audit_logs_organization_created (organization_id, created_at),
    KEY idx_audit_logs_actor_created (actor_user_id, created_at),
    KEY idx_audit_logs_entity (entity_type, entity_id),
    KEY idx_audit_logs_action_created (action, created_at),

    CONSTRAINT fk_audit_logs_organization
        FOREIGN KEY (organization_id)
        REFERENCES organizations (id)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,

    CONSTRAINT fk_audit_logs_actor
        FOREIGN KEY (actor_user_id)
        REFERENCES users (id)
        ON UPDATE CASCADE
        ON DELETE SET NULL
) ENGINE=InnoDB;

-- ============================================================
-- END OF SCHEMA
-- ============================================================
