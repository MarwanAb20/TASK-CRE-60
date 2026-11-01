# Data Provenance — TASK-CRE-60

## 1. Source Identification

- **Authority:** Gutachterausschuss für Grundstückswerte in Hamburg
- **Publication:** Immobilienmarktbericht Hamburg 2026
- **Asset focus:** Logistics real estate
- **Source format:** PDF
- **Source URL:**

  https://www.hamburg.de/resource/blob/1166868/d21cbc3d6d1c7767bfb82752a3c4cb3d/d-immobilienmarktbericht-2026-data.pdf

- **Local source file:** `data/raw/hamburg_2026.pdf`

## 2. Extraction Scope

The extraction process loaded a 214-page PDF and identified a relevant section spanning three pages.

The extracted information is stored in:

`data/fixtures/hamburg_2026_parsed.json`

The extraction focuses on the logistics-related Liegenschaftszinssatz information and associated parameters available in the source.

Exact printed-page and PDF-page references should be checked against the source document and the parsed fixture before downstream use.

## 3. Extracted Values

The extraction run produced the following values:

| Field | Extracted value |
|---|---:|
| Base rate | 4.11% |
| Location exponent | -1.4861 |
| Rent exponent | 0.0948 |
| First occupancy factor | 0.84 |
| Number of update factors | 7 |
| Sample size | 110 |
| Quality indicator | 26% |

These values are recorded as extraction results. They should be validated against the corresponding original report pages before production use.

## 4. Data Processing Flow

1. Load the original Hamburg 2026 PDF.
2. Identify the relevant logistics section.
3. Extract the required values and associated information.
4. Save the extracted structure as JSON.
5. Validate and normalize dates and numeric values.
6. Generate stable record keys.
7. Load candidate records into the `iris_staging` schema.
8. Record ingestion outcomes and counts.

## 5. Output Records

The successful ingestion produced 17 records:

| Destination table | Records |
|---|---:|
| `source_documents` | 1 |
| `appraisal_metrics` | 1 |
| `adjustment_factors` | 10 |
| `sample_statistics` | 5 |
| **Total** | **17** |

A second ingestion of the same fixture resulted in 17 unchanged records and no additional inserts.

## 6. Provenance and Traceability

The staging model retains source-document metadata and supports page-level references through fields such as:

- `source_url`
- `source_file`
- `printed_page`
- `pdf_page`
- `notes`

The original PDF should be retained alongside the parsed fixture so extracted values can be reviewed against the source.

## 7. Limitations

- This implementation currently processes the Hamburg 2026 source only.
- The extracted section covers three pages; the exact page references must be verified against the source and fixture.
- The source data processed here is tabular. No spatial geometries were extracted or fabricated.
- No additional regional values or missing observations have been inferred.
- The extracted values require source-level verification before production use.
- The official target DDL and Master Playbook were not available for final confirmation during implementation.

## 8. Reproducibility

The extraction output is stored as a JSON fixture so the normalization and ingestion stages can be tested without repeatedly parsing the original PDF.

The fixture used for the successful ingestion is:

`data/fixtures/hamburg_2026_parsed.json`
