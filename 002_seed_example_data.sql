-- Example data: one watchlist with two versions.
-- Run after migrations/001_create_watchlist_tables.sql on a fresh database.

BEGIN;

INSERT INTO watchlist (
    watchlist_id, name, description, owner_id, current_version_id
) VALUES (
    1001, 'Suspicious Login Activity',
    'Detects potentially suspicious authentication activity.',
    'security-team', NULL
);

INSERT INTO watchlist_version (
    version_id, watchlist_id, version_number, expression, scope, severity, created_by
) VALUES
(
    2001, 1001, 1,
    'failed_login_count >= 5 within 10 minutes',
    'Authentication logs from production systems',
    'medium', 'nikhil.kalokhe'
),
(
    2002, 1001, 2,
    'failed_login_count >= 8 within 5 minutes OR login_from_new_country = true',
    'Authentication logs from production systems',
    'high', 'nikhil.kalokhe'
);

UPDATE watchlist
SET current_version_id = 2002
WHERE watchlist_id = 1001;

COMMIT;

-- Expected: watchlist 1001 has version 1 and version 2; version 2 is current.
