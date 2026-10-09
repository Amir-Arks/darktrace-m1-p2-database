-- Lightweight SQL verification for the example dataset.
-- Run after migration and seed scripts. Tests are read-only and raise an error on failure.

DO $$
DECLARE
    version_count INTEGER;
    current_version INTEGER;
    old_expression TEXT;
BEGIN
    -- Test 1: the watchlist exists.
    IF NOT EXISTS (
        SELECT 1 FROM watchlist WHERE watchlist_id = 1001
    ) THEN
        RAISE EXCEPTION 'FAIL: expected watchlist 1001 to exist';
    END IF;

    -- Test 2: two versions exist for the same watchlist.
    SELECT COUNT(*) INTO version_count
    FROM watchlist_version
    WHERE watchlist_id = 1001;

    IF version_count <> 2 THEN
        RAISE EXCEPTION 'FAIL: expected 2 versions for watchlist 1001, found %', version_count;
    END IF;

    -- Test 3: current version points to version number 2.
    SELECT v.version_number INTO current_version
    FROM watchlist w
    JOIN watchlist_version v
      ON v.watchlist_id = w.watchlist_id
     AND v.version_id = w.current_version_id
    WHERE w.watchlist_id = 1001;

    IF current_version <> 2 THEN
        RAISE EXCEPTION 'FAIL: expected current version 2, found %', current_version;
    END IF;

    -- Test 4: the old version remains unchanged and retrievable.
    SELECT expression INTO old_expression
    FROM watchlist_version
    WHERE watchlist_id = 1001 AND version_number = 1;

    IF old_expression IS DISTINCT FROM 'failed_login_count >= 5 within 10 minutes' THEN
        RAISE EXCEPTION 'FAIL: version 1 expression was missing or changed';
    END IF;

    RAISE NOTICE 'PASS: watchlist creation, two versions, current version, and historical preservation';
END $$;

-- Display the history for manual review.
SELECT
    w.watchlist_id,
    w.name,
    v.version_number,
    v.expression,
    v.scope,
    v.severity,
    (v.version_id = w.current_version_id) AS is_current
FROM watchlist w
JOIN watchlist_version v ON v.watchlist_id = w.watchlist_id
WHERE w.watchlist_id = 1001
ORDER BY v.version_number;
