-- =============================================================================
-- DarkTrace M1 — Pod 2  |  Anil Kumar Module
-- Schema for: PostgreSQL  (PRODUCTION / UPGRADE VERSION)
-- Tables:     login, source, crawl_job
-- Flow:       login → crawl_job → source
-- =============================================================================
-- Run with:  psql -U <user> -d <dbname> -f schema_postgres.sql
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid()

-- ── 1. LOGIN ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS login (
    login_id        UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    username        VARCHAR(100)    NOT NULL UNIQUE,
    email           VARCHAR(255)    NOT NULL UNIQUE,
    password_hash   VARCHAR(255)    NOT NULL,
    role            VARCHAR(50)     NOT NULL DEFAULT 'analyst'
                        CHECK (role IN ('admin','analyst','viewer','api_service')),
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_login_username  ON login (username);
CREATE INDEX IF NOT EXISTS idx_login_email     ON login (email);
CREATE INDEX IF NOT EXISTS idx_login_role      ON login (role);
CREATE INDEX IF NOT EXISTS idx_login_is_active ON login (is_active);

COMMENT ON TABLE  login               IS 'Authenticated DarkTrace users/operators.';
COMMENT ON COLUMN login.password_hash IS 'Bcrypt/argon2 hash — NEVER store plaintext.';
COMMENT ON COLUMN login.role          IS 'admin | analyst | viewer | api_service';


-- ── 2. SOURCE ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS source (
    source_id       UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255)    NOT NULL,
    url             TEXT            NOT NULL UNIQUE,
    description     TEXT,
    source_type     VARCHAR(50)     NOT NULL DEFAULT 'web'
                        CHECK (source_type IN ('web','api','darkweb','feed','other')),
    tags            JSONB,                                      -- fast JSON queries + GIN index
    crawl_depth     SMALLINT        NOT NULL DEFAULT 1
                        CHECK (crawl_depth BETWEEN 1 AND 10),
    crawl_frequency VARCHAR(50)     NOT NULL DEFAULT 'manual'
                        CHECK (crawl_frequency IN ('manual','hourly','daily','weekly')),
    allowed_paths   JSONB,                                      -- list of allowed URL prefixes
    registered_by   UUID            NOT NULL
                        REFERENCES login (login_id) ON DELETE RESTRICT,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    last_crawled_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_source_url           ON source (url);
CREATE INDEX IF NOT EXISTS idx_source_source_type   ON source (source_type);
CREATE INDEX IF NOT EXISTS idx_source_is_active     ON source (is_active);
CREATE INDEX IF NOT EXISTS idx_source_registered_by ON source (registered_by);
CREATE INDEX IF NOT EXISTS idx_source_tags          ON source USING GIN (tags);          -- PostgreSQL-only
CREATE INDEX IF NOT EXISTS idx_source_allowed_paths ON source USING GIN (allowed_paths); -- PostgreSQL-only

COMMENT ON TABLE  source               IS 'Monitored external targets that crawl jobs visit.';
COMMENT ON COLUMN source.tags          IS 'JSONB list of labels, e.g. ["finance","threat-intel"].';
COMMENT ON COLUMN source.allowed_paths IS 'JSONB list of URL path prefixes the crawler may follow.';


-- ── 3. CRAWL_JOB ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS crawl_job (
    job_id          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    triggered_by    UUID            NOT NULL
                        REFERENCES login  (login_id)  ON DELETE RESTRICT,
    source_id       UUID            NOT NULL
                        REFERENCES source (source_id) ON DELETE RESTRICT,
    job_name        VARCHAR(255),
    description     TEXT,
    depth_used      SMALLINT        NOT NULL DEFAULT 1
                        CHECK (depth_used BETWEEN 1 AND 10),
    user_agent      VARCHAR(255),
    extra_config    JSONB,                                      -- flexible per-job settings
    status          VARCHAR(20)     NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','running','completed','failed','cancelled')),
    scheduled_at    TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    pages_crawled   INTEGER         NOT NULL DEFAULT 0  CHECK (pages_crawled >= 0),
    errors_count    INTEGER         NOT NULL DEFAULT 0  CHECK (errors_count  >= 0),
    error_details   TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_crawl_job_timing
        CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
);
CREATE INDEX IF NOT EXISTS idx_crawl_job_triggered_by ON crawl_job (triggered_by);
CREATE INDEX IF NOT EXISTS idx_crawl_job_source_id    ON crawl_job (source_id);
CREATE INDEX IF NOT EXISTS idx_crawl_job_status       ON crawl_job (status);
CREATE INDEX IF NOT EXISTS idx_crawl_job_created_at   ON crawl_job (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawl_job_scheduled_at ON crawl_job (scheduled_at);
CREATE INDEX IF NOT EXISTS idx_crawl_job_user_source  ON crawl_job (triggered_by, source_id);

COMMENT ON TABLE  crawl_job              IS 'Crawl attempts: links WHO triggered (login) to WHICH site (source).';
COMMENT ON COLUMN crawl_job.triggered_by IS 'FK → login — user who started the crawl.';
COMMENT ON COLUMN crawl_job.source_id    IS 'FK → source — target site being crawled.';
COMMENT ON COLUMN crawl_job.extra_config IS 'JSONB blob for flexible per-job crawler settings.';


-- ── 4. Auto-update updated_at trigger (PostgreSQL) ──────────────────────────
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE TRIGGER trg_login_updated_at
    BEFORE UPDATE ON login
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE OR REPLACE TRIGGER trg_source_updated_at
    BEFORE UPDATE ON source
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

CREATE OR REPLACE TRIGGER trg_crawl_job_updated_at
    BEFORE UPDATE ON crawl_job
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
