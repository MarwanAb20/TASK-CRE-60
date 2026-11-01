
CREATE SCHEMA IF NOT EXISTS iris_staging;

-- 1. Official source documents
CREATE TABLE IF NOT EXISTS iris_staging.source_documents (
    source_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    authority TEXT NOT NULL,
    report_year INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    source_file TEXT,
    printed_pages INTEGER[] NOT NULL DEFAULT '{}',
    pdf_pages INTEGER[] NOT NULL DEFAULT '{}',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_source_document
        UNIQUE (authority, report_year, source_url),

    CONSTRAINT chk_source_report_year
        CHECK (report_year BETWEEN 1900 AND 2100)
);


-- 2. Main appraisal metrics
CREATE TABLE IF NOT EXISTS iris_staging.appraisal_metrics (
    metric_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id BIGINT NOT NULL
        REFERENCES iris_staging.source_documents(source_id),

    region TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    metric_name TEXT NOT NULL,
    reference_year INTEGER NOT NULL,

    value NUMERIC(12, 6) NOT NULL,
    unit TEXT NOT NULL,
    value_type TEXT NOT NULL,
    formula TEXT,
    geographic_scope TEXT,
    printed_page INTEGER,
    pdf_page INTEGER,
    notes TEXT,

    stable_key CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_metric_reference_year
        CHECK (reference_year BETWEEN 1900 AND 2100),

    CONSTRAINT chk_metric_pages
        CHECK (
            (printed_page IS NULL OR printed_page > 0)
            AND (pdf_page IS NULL OR pdf_page > 0)
        )
);


-- 3. Formula parameters and adjustment factors
CREATE TABLE IF NOT EXISTS iris_staging.adjustment_factors (
    factor_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    metric_id BIGINT NOT NULL
        REFERENCES iris_staging.appraisal_metrics(metric_id)
        ON DELETE CASCADE,

    factor_type TEXT NOT NULL,
    factor_name TEXT NOT NULL,

    value NUMERIC(16, 8),
    exponent NUMERIC(16, 8),
    reference_variable TEXT,
    reference_value NUMERIC(16, 6),
    unit TEXT,

    condition_description TEXT,

    investigation_period_start DATE,
    investigation_period_end DATE,
    valuation_date DATE,

    printed_page INTEGER,
    pdf_page INTEGER,
    notes TEXT,

    stable_key CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_factor_type
        CHECK (
            factor_type IN (
                'formula_parameter',
                'conditional_factor',
                'time_update_factor'
            )
        ),

    CONSTRAINT chk_factor_has_value
        CHECK (value IS NOT NULL OR exponent IS NOT NULL),

    CONSTRAINT chk_investigation_period
        CHECK (
            investigation_period_start IS NULL
            OR investigation_period_end IS NULL
            OR investigation_period_start <= investigation_period_end
        ),

    CONSTRAINT chk_factor_pages
        CHECK (
            (printed_page IS NULL OR printed_page > 0)
            AND (pdf_page IS NULL OR pdf_page > 0)
        )
);


-- 4. Sample statistics and quality indicators
CREATE TABLE IF NOT EXISTS iris_staging.sample_statistics (
    statistic_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    metric_id BIGINT NOT NULL
        REFERENCES iris_staging.appraisal_metrics(metric_id)
        ON DELETE CASCADE,

    statistic_type TEXT NOT NULL,
    statistic_name TEXT NOT NULL,

    minimum_value NUMERIC(16, 6),
    maximum_value NUMERIC(16, 6),
    mean_value NUMERIC(16, 6),
    observed_value NUMERIC(16, 6),

    sample_size INTEGER,
    unit TEXT,

    printed_page INTEGER,
    pdf_page INTEGER,
    notes TEXT,

    stable_key CHAR(64) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_statistic_type
        CHECK (
            statistic_type IN (
                'sample_statistic',
                'quality_indicator'
            )
        ),

    CONSTRAINT chk_sample_size
        CHECK (sample_size IS NULL OR sample_size > 0),

    CONSTRAINT chk_statistic_range
        CHECK (
            minimum_value IS NULL
            OR maximum_value IS NULL
            OR minimum_value <= maximum_value
        )
);


-- 5. Data ingestion execution history
CREATE TABLE IF NOT EXISTS iris_staging.ingestion_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    source_id BIGINT
        REFERENCES iris_staging.source_documents(source_id),

    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMPTZ,

    status TEXT NOT NULL DEFAULT 'running',

    processed_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,

    error_summary TEXT,

    CONSTRAINT chk_ingestion_status
        CHECK (status IN ('running', 'completed', 'failed')),

    CONSTRAINT chk_ingestion_counts
        CHECK (
            processed_count >= 0
            AND inserted_count >= 0
            AND updated_count >= 0
            AND failed_count >= 0
        )
);


-- Indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_metrics_source_id
    ON iris_staging.appraisal_metrics(source_id);

CREATE INDEX IF NOT EXISTS idx_metrics_region_asset
    ON iris_staging.appraisal_metrics(region, asset_class);

CREATE INDEX IF NOT EXISTS idx_factors_metric_id
    ON iris_staging.adjustment_factors(metric_id);

CREATE INDEX IF NOT EXISTS idx_statistics_metric_id
    ON iris_staging.sample_statistics(metric_id);

CREATE INDEX IF NOT EXISTS idx_ingestion_source_id
    ON iris_staging.ingestion_runs(source_id);
