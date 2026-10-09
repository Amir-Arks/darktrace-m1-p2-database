-- Example workflow: add a new version and move the current-version pointer.
-- Run after the migration and seed script. Existing versions are not overwritten.

BEGIN;

WITH next_number AS (
    SELECT COALESCE(MAX(version_number), 0) + 1 AS version_number
    FROM watchlist_version
    WHERE watchlist_id = 1001
),
inserted_version AS (
    INSERT INTO watchlist_version (
        watchlist_id, version_number, expression, scope, severity, created_by
    )
    SELECT
        1001,
        next_number.version_number,
        'failed_login_count >= 10 within 5 minutes OR login_from_new_country = true',
        'Authentication logs from production systems',
        'high',
        'nikhil.kalokhe'
    FROM next_number
    RETURNING watchlist_id, version_id
)
UPDATE watchlist AS w
SET current_version_id = i.version_id
FROM inserted_version AS i
WHERE w.watchlist_id = i.watchlist_id;

COMMIT;

-- Verify history:
SELECT version_number, expression, scope, severity,
       (version_id = w.current_version_id) AS is_current
FROM watchlist_version AS v
JOIN watchlist AS w ON w.watchlist_id = v.watchlist_id
WHERE v.watchlist_id = 1001
ORDER BY version_number;
