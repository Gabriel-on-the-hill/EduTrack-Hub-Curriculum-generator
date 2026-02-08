-- 03_db_readonly_role_setup.sql
-- Run this as ADMIN (postgres or service_role)
-- This script creates a read-only role and user for the Application Runner.

-- 1. Create the Read-Only Role
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'app_readonly') THEN
    CREATE ROLE app_readonly;
  END IF;
END
$$;

-- 2. Grant Connection and Usage
GRANT USAGE ON SCHEMA public TO app_readonly;
GRANT CONNECT ON DATABASE postgres TO app_readonly; -- Adjust 'postgres' if your DB name differs

-- 3. Grant Select on All Existing Tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO app_readonly;

-- 4. Ensure Future Tables are Readable
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO app_readonly;

-- 5. Create the Specific User (User should change 'change_me_to_strong_password' immediately)
-- Note: In a real prod setup, you might manage users separately, but this is for the 'readonly_user' specified in the plan.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'readonly_user') THEN
    CREATE USER readonly_user WITH PASSWORD 'change_me_to_strong_password';
  END IF;
END
$$;

-- 6. Assign Role to User
GRANT app_readonly TO readonly_user;

-- 7. Explicit Security: Revoke Write Access (Just to be double sure, though they shouldn't have it)
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM app_readonly;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM readonly_user;

-- Verify
-- SELECT * FROM information_schema.role_table_grants WHERE grantee = 'readonly_user';
