-- db_readonly_role_setup.sql
-- SECURE PRODUCTION SETUP
-- Creates a limited user that allows the Application to READ data but NEVER modify it.
-- This is the "Truth Layer" protection.

-- 1. Create Role (Password will be injected by provision script)
DO
$do$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles
      WHERE  rolname = 'readonly_user') THEN
      CREATE ROLE readonly_user LOGIN PASSWORD '${READONLY_PASSWORD}';
   END IF;
END
$do$;

-- 2. Grant Connection
GRANT CONNECT ON DATABASE postgres TO readonly_user; -- Note: Supabase default DB is 'postgres'

-- 3. Grant Usage on Public Schema
GRANT USAGE ON SCHEMA public TO readonly_user;

-- 4. Grant Select on All Existing Tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;

-- 5. Ensure Future Tables are also Read-Only (Safety for updates)
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_user;

-- 6. REVOKE dangerous privileges just in case
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM readonly_user;
