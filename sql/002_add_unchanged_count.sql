ALTER TABLE iris_staging.ingestion_runs
ADD COLUMN IF NOT EXISTS unchanged_count INTEGER NOT NULL DEFAULT 0;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'chk_ingestion_unchanged_count'
          AND conrelid = 'iris_staging.ingestion_runs'::regclass
    ) THEN
        ALTER TABLE iris_staging.ingestion_runs
        ADD CONSTRAINT chk_ingestion_unchanged_count
        CHECK (unchanged_count >= 0);
    END IF;
END
$$;