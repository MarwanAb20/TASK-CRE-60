# TASK-CRE-60 — Gutachterausschuss Logistics Metrics ETL

## 1. Project Overview

This project extracts and normalizes logistics-related real estate valuation metrics (Liegenschaftszinssätze) from the Hamburg Immobilienmarktbericht 2026.

The pipeline extracts information from the source PDF, creates an intermediate JSON fixture, validates and normalizes the extracted values, and loads the resulting records into the PostgreSQL `iris_staging` schema.

All candidate data writes are restricted to `iris_staging`. No writes to `iris_core` or production schemas are performed.

## 2. Technology Stack

- Python 3.11+
- PostgreSQL 16
- PostGIS 3.4
- SQLAlchemy
- Psycopg 3
- PyMuPDF
- Docker and Docker Compose
- Pytest

## 3. Project Structure

```text
TASK-CRE-60/
├── data/
│   ├── raw/
│   │   └── hamburg_2026.pdf
│   └── fixtures/
│       ├── hamburg_2026_logistics.json
│       └── hamburg_2026_parsed.json
├── docs/
├── sql/
│   ├── 001_create_staging_tables.sql
│   └── 002_add_unchanged_count.sql
├── src/
│   ├── extraction/
│   │   └── pdf_extractor.py
│   ├── normalization/
│   │   ├── db_loader.py
│   │   ├── keys.py
│   │   ├── loader.py
│   │   └── models.py
│   ├── database.py
│   └── staging.py
├── tests/
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── init.sql
├── requirements.txt
└── README.md
```

## 4. Data Source

Authority: Gutachterausschuss für Grundstückswerte in Hamburg.

Document: Immobilienmarktbericht Hamburg 2026.

Source PDF:

https://www.hamburg.de/resource/blob/1166868/d21cbc3d6d1c7767bfb82752a3c4cb3d/d-immobilienmarktbericht-2026-data.pdf

The source PDF is stored locally at:

`data/raw/hamburg_2026.pdf`

The extraction process identifies the relevant section and generates:

`data/fixtures/hamburg_2026_parsed.json`

## 5. Database Design

All candidate records are stored in the `iris_staging` schema.

| Table | Purpose |
|---|---|
| `source_documents` | Source document metadata and provenance |
| `appraisal_metrics` | Main appraisal metrics |
| `adjustment_factors` | Formula parameters and adjustment factors |
| `sample_statistics` | Sample statistics and quality indicators |
| `ingestion_runs` | Ingestion execution history and counters |

The current schema is an implementation-level staging model based on the available assignment requirements. It is provisional and has not been confirmed as the official target DDL.

## 6. Setup

### Prerequisites

- Python 3.11 or later
- Docker Desktop with Docker Compose

### Configure environment variables

Create a local `.env` file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set a local development password. Never commit `.env`.

### Create and activate a Python environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Install dependencies

```powershell
pip install -r requirements.txt
```

## 7. Start PostgreSQL and PostGIS

Start the database service:

```powershell
docker compose up -d db
```

Check its status:

```powershell
docker compose ps
```

The database uses PostgreSQL 16 with PostGIS 3.4.

The initialization script enables PostGIS and creates the `iris_staging` schema. Apply the SQL files in `sql/` to create or update the staging tables when required.

## 8. Run PDF Extraction

Build the application image:

```powershell
docker compose build app
```

Run extraction:

```powershell
docker compose run --rm app python -m src.extraction.pdf_extractor
```

The parsed JSON output is written to:

`data/fixtures/hamburg_2026_parsed.json`

## 9. Run Database Ingestion

The database loader reads the parsed JSON fixture and connects using the `DB_URI` environment variable.

For Docker-based execution, the database hostname inside the Compose network is `db`, not `localhost`.

Example connection format:

```text
postgresql+psycopg://USER:PASSWORD@db:5432/DATABASE
```

Set `DB_URI` to the intended database before running the loader.

Run the loader:

```powershell
docker compose run --rm -e DB_URI app python -m src.normalization.db_loader
```

Verify the database name and target schema before ingestion. Use a dedicated development or test database. Never point the loader at production.

## 10. Run Tests

Configure `DB_URI` to point to the test database before running tests.

The test database must contain the required staging tables and PostGIS extension.

Run:

```powershell
python -m pytest -v
```

## 11. Validation Results

The following results were observed during development.

### PDF extraction

- PDF pages loaded: 214
- Relevant target section: 3 pages
- Base rate: 4.11%
- Location exponent: -1.4861
- Rent exponent: 0.0948
- First occupancy factor: 0.84
- Update factors: 7
- Sample size: 110
- Quality indicator: 26%

### Database ingestion

First successful ingestion:

| Counter | Result |
|---|---:|
| Processed | 17 |
| Inserted | 17 |
| Updated | 0 |
| Unchanged | 0 |
| Failed | 0 |

Observed database records:

| Table | Records |
|---|---:|
| `source_documents` | 1 |
| `appraisal_metrics` | 1 |
| `adjustment_factors` | 10 |
| `sample_statistics` | 5 |
| **Total** | **17** |

Second ingestion of the same fixture:

| Counter | Result |
|---|---:|
| Processed | 17 |
| Inserted | 0 |
| Updated | 0 |
| Unchanged | 17 |
| Failed | 0 |

This verifies idempotent behavior for the tested fixture and database state.

### Automated tests

**22 passed**

## 12. Idempotency and Data Integrity

Stable keys are generated using SHA-256 over canonicalized JSON identities.

Unique constraints on stable keys prevent duplicate metric, factor, and statistic records.

The loader uses database upsert logic to distinguish inserted, updated, and unchanged records.

A failed ingestion is expected to roll back partial data changes and record the failure in the ingestion history where possible.

## 13. Spatial Data Handling

The Hamburg source data processed in this implementation consists of tabular valuation metrics and adjustment factors. It does not provide geometry records for these extracted metrics.

Therefore, no geometries are fabricated.

If spatial records are supplied in a later source, their CRS must be verified and transformed to EPSG:25832 where required. Geometries should be validated, with invalid geometries handled using `shapely.make_valid()`. Empty or unusable geometries should be reported.

## 14. Limitations and Follow-up

- The Master Playbook and official target DDL were not available for final confirmation during implementation.
- The current staging schema is provisional and must be reconciled with the project team's official schema.
- The current extraction implementation covers the Hamburg 2026 source.
- Additional authorities and reports require source-specific extraction and validation.
- Spatial processing is documented but was not exercised because the processed source data is tabular.
- Extracted values should be checked against the original report pages before production use.

## 15. Safety and Scope

- Database credentials are supplied through environment variables.
- `.env` is excluded from version control and Docker build context.
- Candidate records are restricted to `iris_staging`.
- No production schema writes are part of this implementation.
- Source provenance and extraction limitations should be retained with the delivered data.
