# Schema Mapping — TASK-CRE-60

## 1. Purpose

This document describes how the extracted Hamburg 2026 logistics valuation data is represented in the provisional PostgreSQL staging model.

All candidate records are stored under:

`iris_staging`

The schema is an implementation-level model and must be reconciled with the official target DDL when it becomes available.

## 2. Entity Relationship Overview

The staging model contains five tables:

- `source_documents`
- `appraisal_metrics`
- `adjustment_factors`
- `sample_statistics`
- `ingestion_runs`

The main relationships are:

- One source document can be associated with multiple appraisal metrics.
- One appraisal metric can have multiple adjustment factors.
- One appraisal metric can have multiple sample statistics.
- An ingestion run may reference the source document processed during that run.

## 3. Table Mapping

### 3.1 source_documents

**Purpose:** Stores source publication metadata and provenance.

| Column | Description |
|---|---|
| `source_id` | Generated primary key |
| `authority` | Publishing authority |
| `report_year` | Publication year |
| `source_url` | Original source URL |
| `source_file` | Local source filename |
| `printed_pages` | Printed page references |
| `pdf_pages` | PDF page references |
| `notes` | Additional provenance information |
| `created_at` | Record creation timestamp |

**Uniqueness:** `(authority, report_year, source_url)`.

### 3.2 appraisal_metrics

**Purpose:** Stores the main extracted valuation metric.

| Column | Description |
|---|---|
| `metric_id` | Generated primary key |
| `source_id` | Foreign key to `source_documents` |
| `region` | Geographic region |
| `asset_class` | Asset category |
| `metric_name` | Metric name |
| `reference_year` | Reference year |
| `value` | Numeric metric value |
| `unit` | Measurement unit |
| `value_type` | Type or interpretation of the value |
| `formula` | Associated formula, if available |
| `geographic_scope` | Geographic scope |
| `printed_page` | Printed page reference |
| `pdf_page` | PDF page reference |
| `notes` | Additional context |
| `stable_key` | SHA-256 identity key |
| `created_at` | Record creation timestamp |

**Uniqueness:** `stable_key`.

### 3.3 adjustment_factors

**Purpose:** Stores formula parameters, conditional factors, and time update factors.

| Column | Description |
|---|---|
| `factor_id` | Generated primary key |
| `metric_id` | Foreign key to `appraisal_metrics` |
| `factor_type` | Factor category |
| `factor_name` | Factor name |
| `value` | Numeric factor value |
| `exponent` | Formula exponent |
| `reference_variable` | Related reference variable |
| `reference_value` | Reference value |
| `unit` | Measurement unit |
| `condition_description` | Applicable condition |
| `investigation_period_start` | Investigation period start date |
| `investigation_period_end` | Investigation period end date |
| `valuation_date` | Valuation date |
| `printed_page` | Printed page reference |
| `pdf_page` | PDF page reference |
| `notes` | Additional context |
| `stable_key` | SHA-256 identity key |
| `created_at` | Record creation timestamp |

Supported factor types:

- `formula_parameter`
- `conditional_factor`
- `time_update_factor`

**Uniqueness:** `stable_key`.

### 3.4 sample_statistics

**Purpose:** Stores sample information and quality indicators.

| Column | Description |
|---|---|
| `statistic_id` | Generated primary key |
| `metric_id` | Foreign key to `appraisal_metrics` |
| `statistic_type` | Statistic category |
| `statistic_name` | Statistic name |
| `minimum_value` | Minimum observed value |
| `maximum_value` | Maximum observed value |
| `mean_value` | Mean value |
| `observed_value` | Reported observed value |
| `sample_size` | Number of observations |
| `unit` | Measurement unit |
| `printed_page` | Printed page reference |
| `pdf_page` | PDF page reference |
| `notes` | Additional context |
| `stable_key` | SHA-256 identity key |
| `created_at` | Record creation timestamp |

Supported statistic types:

- `sample_statistic`
- `quality_indicator`

**Uniqueness:** `stable_key`.

### 3.5 ingestion_runs

**Purpose:** Tracks ingestion execution history and operational counters.

| Column | Description |
|---|---|
| `run_id` | Generated primary key |
| `source_id` | Optional source document reference |
| `started_at` | Ingestion start timestamp |
| `finished_at` | Ingestion completion timestamp |
| `status` | Execution status |
| `processed_count` | Number of processed records |
| `inserted_count` | Number of inserted records |
| `updated_count` | Number of updated records |
| `unchanged_count` | Number of unchanged records |
| `failed_count` | Number of failed records |
| `error_summary` | Failure details, if applicable |

Supported statuses:

- `running`
- `completed`
- `failed`

## 4. Normalization and Identity

The ingestion process uses deterministic SHA-256 stable keys.

The key is generated from canonicalized JSON identity data using:

- Sorted JSON keys
- UTF-8 encoding
- Consistent JSON separators
- A category identifier

Unique constraints on stable keys protect against duplicate metric, factor, and statistic records.

## 5. Data Relationships

```text
source_documents
       |
       | 1-to-many
       v
appraisal_metrics
       |
       |----------------------|
       |                      |
       v                      v
adjustment_factors     sample_statistics

ingestion_runs
       |
       └── optional reference to source_documents
```

## 6. Observed Ingestion Mapping

The successful Hamburg fixture ingestion produced:

| Table | Inserted records |
|---|---:|
| `source_documents` | 1 |
| `appraisal_metrics` | 1 |
| `adjustment_factors` | 10 |
| `sample_statistics` | 5 |
| **Total** | **17** |

The second execution processed the same 17 records and classified all of them as unchanged.

## 7. Spatial Considerations

The current Hamburg fixture contains tabular valuation data and does not provide geometry records for these metrics.

No geometry columns or spatial features are fabricated in this mapping.

If spatial data is introduced later, the implementation must verify its source CRS, transform it to EPSG:25832 where required, and validate geometries before staging ingestion.

## 8. Outstanding Confirmation

The following items require confirmation against the official project documentation:

- Final target table and column names.
- Official DDL and data types.
- Required foreign-key and uniqueness constraints.
- Expected source and metric classification values.
- Whether spatial geometry is required for other source datasets.

Until confirmed, this document describes the provisional staging implementation only.
