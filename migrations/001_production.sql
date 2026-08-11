-- DEEP-Seek production migration baseline.
-- Run against PostgreSQL before starting the API.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS schema_version(version BIGINT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now());
INSERT INTO schema_version(version) VALUES (1) ON CONFLICT DO NOTHING;
CREATE INDEX IF NOT EXISTS idx_schema_version_applied ON schema_version(applied_at);
