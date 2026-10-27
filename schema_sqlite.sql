-- =============================================================================
-- DarkTrace M1 — Pod 2  |  Anil Kumar Module
-- Schema for: SQLite  (DEVELOPMENT / TESTING)
-- Tables:     login, source, crawl_job
-- Flow:       login → crawl_job → source
-- =============================================================================
-- Run with:  sqlite3 darktrace.db < schema_sqlite.sql
-- =============================================================================

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous   = NORMAL;

-- 1. LOGIN
CREATE TABLE IF NOT EXISTS login (
    login_id        TEXT        PRIMARY KEY,                    -- UUID as TEXT
    username        TEXT        NOT NULL UNIQUE,
    email           TEXT        NOT NULL UNIQUE,
    password_hash   TEXT        NOT NULL,
    role            TEXT        NOT NULL DEFAULT 'analyst'
                        CHECK (role IN ('admin','analyst','viewer','api_service')),
    is_active       INTEGER     NOT NULL DEFAULT 1
                        CHECK (is_active IN (0,1)),             -- 1=TRUE, 0=FALSE
    last_login_at   TEXT,                                       -- ISO-8601
    created_at      TEXT        NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT        NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_login_username  ON login (username);
CREATE INDEX IF NOT EXISTS idx_login_email     ON login (email);
CREATE INDEX IF NOT EXISTS idx_login_role      ON login (role);
CREATE INDEX IF NOT EXISTS idx_login_is_active ON login (is_active);

CREATE TRIGGER IF NOT EXISTS trg_login_updated_at
    AFTER UPDATE ON login FOR EACH ROW
BEGIN
    UPDATE login SET updated_at = datetime('now') WHERE login_id = NEW.login_id;
END;


-- 2. SOURCE
CREATE TABLE IF NOT EXISTS source (
    source_id       TEXT        PRIMARY KEY,
    name            TEXT        NOT NULL,
    url             TEXT        NOT NULL UNIQUE,
    description     TEXT,
    source_type     TEXT        NOT NULL DEFAULT 'web'
                        CHECK (source_type IN ('web','api','darkweb','feed','other')),
    tags            TEXT,                                       -- JSON array as TEXT
    crawl_depth     INTEGER     NOT NULL DEFAULT 1
                        CHECK (crawl_depth BETWEEN 1 AND 10),
    crawl_frequency TEXT        NOT NULL DEFAULT 'manual'
                        CHECK (crawl_frequency IN ('manual','hourly','daily','weekly')),
    allowed_paths   TEXT,                                       -- JSON array as TEXT
    registered_by   TEXT        NOT NULL
                        REFERENCES login (login_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    is_active       INTEGER     NOT NULL DEFAULT 1
                        CHECK (is_active IN (0,1)),
    last_crawled_at TEXT,
    created_at      TEXT        NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT        NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_source_url           ON source (url);
CREATE INDEX IF NOT EXISTS idx_source_source_type   ON source (source_type);
CREATE INDEX IF NOT EXISTS idx_source_is_active     ON source (is_active);
CREATE INDEX IF NOT EXISTS idx_source_registered_by ON source (registered_by);

CREATE TRIGGER IF NOT EXISTS trg_source_updated_at
    AFTER UPDATE ON source FOR EACH ROW
BEGIN
    UPDATE source SET updated_at = datetime('now') WHERE source_id = NEW.source_id;
END;


-- 3. CRAWL_JOB
CREATE TABLE IF NOT EXISTS crawl_job (
    job_id          TEXT        PRIMARY KEY,
    triggered_by    TEXT        NOT NULL
                        REFERENCES login  (login_id)  ON DELETE RESTRICT ON UPDATE CASCADE,
    source_id       TEXT        NOT NULL
                        REFERENCES source (source_id) ON DELETE RESTRICT ON UPDATE CASCADE,
    job_name        TEXT,
    description     TEXT,
    depth_used      INTEGER     NOT NULL DEFAULT 1
                        CHECK (depth_used BETWEEN 1 AND 10),
    user_agent      TEXT,
    extra_config    TEXT,                                       -- JSON blob
    status          TEXT        NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','running','completed','failed','cancelled')),
    scheduled_at    TEXT,
    started_at      TEXT,
    completed_at    TEXT,
    pages_crawled   INTEGER     NOT NULL DEFAULT 0  CHECK (pages_crawled >= 0),
    errors_count    INTEGER     NOT NULL DEFAULT 0  CHECK (errors_count  >= 0),
    error_details   TEXT,
    created_at      TEXT        NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT        NOT NULL DEFAULT (datetime('now')),
    CHECK (completed_at IS NULL OR started_at IS NULL OR completed_at >= started_at)
);
CREATE INDEX IF NOT EXISTS idx_crawl_job_triggered_by ON crawl_job (triggered_by);
CREATE INDEX IF NOT EXISTS idx_crawl_job_source_id    ON crawl_job (source_id);
CREATE INDEX IF NOT EXISTS idx_crawl_job_status       ON crawl_job (status);
CREATE INDEX IF NOT EXISTS idx_crawl_job_created_at   ON crawl_job (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_crawl_job_user_source  ON crawl_job (triggered_by, source_id);

CREATE TRIGGER IF NOT EXISTS trg_crawl_job_updated_at
    AFTER UPDATE ON crawl_job FOR EACH ROW
BEGIN
    UPDATE crawl_job SET updated_at = datetime('now') WHERE job_id = NEW.job_id;
END;
