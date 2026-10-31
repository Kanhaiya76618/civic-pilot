-- Paste this whole file into the Supabase SQL Editor
-- CivicPilot Unified Civic Governance Platform Schema

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- 1. USERS & ROLES
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    role TEXT NOT NULL DEFAULT 'citizen', -- 'citizen', 'admin'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. CIVIC REPORTS / GRIEVANCES
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    category TEXT NOT NULL, -- 'roads_potholes', 'garbage', 'water', 'streetlights', 'drainage', 'other'
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'SUBMITTED', -- 'SUBMITTED', 'TRIAGED', 'ACKNOWLEDGED', 'ASSIGNED', 'IN_PROGRESS', 'RESOLVED', 'REJECTED'
    severity TEXT NOT NULL DEFAULT 'P3', -- 'P1', 'P2', 'P3', 'P4'
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    ward_id TEXT NOT NULL,
    ward_name TEXT,
    city TEXT NOT NULL,
    evidence_urls JSONB DEFAULT '[]'::jsonb,
    poi_distance_m DOUBLE PRECISION,
    poi_multiplier DOUBLE PRECISION DEFAULT 1.0,
    sla_deadline TIMESTAMPTZ,
    assigned_to TEXT,
    resolution_proof_url TEXT,
    resolution_notes TEXT,
    duplicate_of UUID REFERENCES reports(id) ON DELETE SET NULL,
    upvotes INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. AUDITABLE REPORT EVENTS
CREATE TABLE IF NOT EXISTS report_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'CREATED', 'TRIAGED', 'ACKNOWLEDGED', 'ASSIGNED', 'RESOLVED', 'UPVOTED', 'DISPUTED'
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    actor_role TEXT NOT NULL DEFAULT 'system', -- 'citizen', 'admin', 'system'
    actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. VERIFIABLE RECEIPTS & HASH-CHAINED LEDGER
CREATE TABLE IF NOT EXISTS receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id TEXT UNIQUE NOT NULL,
    report_id UUID REFERENCES reports(id) ON DELETE SET NULL,
    confirmation_number TEXT NOT NULL,
    portal_name TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    receipt_url TEXT,
    signature TEXT NOT NULL,
    public_key TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    ticket_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. AGENT EXECUTION RUNS
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    service TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running', -- 'running', 'success', 'failed', 'waiting_human'
    task_input JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. AGENT RUN STEPS
CREATE TABLE IF NOT EXISTS agent_run_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    action TEXT NOT NULL,
    target TEXT,
    status TEXT NOT NULL,
    screenshot_url TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. SCHEMES KNOWLEDGE BASE
CREATE TABLE IF NOT EXISTS schemes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    ministry TEXT NOT NULL,
    description TEXT NOT NULL,
    eligibility_criteria JSONB NOT NULL DEFAULT '{}'::jsonb,
    benefits TEXT NOT NULL,
    application_url TEXT,
    embedding vector(1536),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 8. PORTAL REGISTRY
CREATE TABLE IF NOT EXISTS portal_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portal_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    base_url TEXT NOT NULL,
    route_manifest JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- INDEXES FOR PERFORMANCE
CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_ward_id ON reports(ward_id);
CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_receipts_task_id ON receipts(task_id);
CREATE INDEX IF NOT EXISTS idx_receipts_report_id ON receipts(report_id);
CREATE INDEX IF NOT EXISTS idx_report_events_report_id ON report_events(report_id);
CREATE INDEX IF NOT EXISTS idx_agent_steps_run_id ON agent_run_steps(run_id);
