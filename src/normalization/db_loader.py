import json
import hashlib
import re
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Any
from sqlalchemy import text
from src.database import engine

DEFAULT_FIXTURE = Path("data/fixtures/hamburg_2026_parsed.json")
SOURCE_URL = (
    "https://www.hamburg.de/resource/blob/1166868/"
    "d21cbc3d6d1c7767bfb82752a3c4cb3d/"
    "d-immobilienmarktbericht-2026-data.pdf"
)

def make_stable_key(category: str, identity: dict[str, Any]) -> str:
    """Create a deterministic SHA-256 key for a database record."""
    payload = {"category": category, **identity}
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

def parse_german_date(value: str) -> date:
    """Convert a date such as 01.01.2026 into a Python date."""
    return datetime.strptime(value, "%d.%m.%Y").date()

def parse_investigation_period(value: str) -> tuple[date, date]:
    """Parse a period such as '1.1.2022 bis 1.1.2023'."""
    match = re.fullmatch(
        r"\s*(\d{1,2}\.\d{1,2}\.\d{4})\s+bis\s+(\d{1,2}\.\d{1,2}\.\d{4})\s*",
        value,
    )
    if not match:
        raise ValueError(f"Invalid investigation period: {value}")
    start = datetime.strptime(match.group(1), "%d.%m.%Y").date()
    end = datetime.strptime(match.group(2), "%d.%m.%Y").date()
    return start, end

def load_fixture(path: Path = DEFAULT_FIXTURE) -> dict[str, Any]:
    """Read the parsed Hamburg JSON fixture."""
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    for section in ("source", "metric", "dataset", "quality_metric"):
        if section not in data:
            raise ValueError(f"Missing JSON section: {section}")
    return data

def ingest_hamburg_fixture(path: Path = DEFAULT_FIXTURE) -> dict[str, int]:
    """
    Load Hamburg appraisal data into iris_staging.
    All database writes are performed in one transaction.
    Repeated executions update existing records instead of duplicating them.
    """
    data = load_fixture(path)
    source = data["source"]
    metric_data = data["metric"]
    dataset = data["dataset"]
    counts = {"processed": 0, "inserted": 0, "updated": 0, "unchanged": 0, "failed": 0}
    source_id = None

    try:
        with engine.begin() as connection:
            # 1. Insert or update the source document
            source_identity = {
                "authority": source["authority"],
                "report_year": source["report_year"],
                "source_url": SOURCE_URL,
            }
            existing_source = connection.execute(
                text("""
                    SELECT source_id FROM iris_staging.source_documents
                    WHERE authority = :authority AND report_year = :report_year AND source_url = :source_url
                """),
                source_identity,
            ).scalar_one_or_none()

            source_result = connection.execute(
                text("""
                    INSERT INTO iris_staging.source_documents (
                        authority, report_year, source_url, source_file, printed_pages, pdf_pages, notes
                    ) VALUES (
                        :authority, :report_year, :source_url, :source_file, :printed_pages, :pdf_pages, :notes
                    )
                    ON CONFLICT (authority, report_year, source_url)
                    DO UPDATE SET
                        source_file = EXCLUDED.source_file,
                        printed_pages = EXCLUDED.printed_pages,
                        pdf_pages = EXCLUDED.pdf_pages,
                        notes = EXCLUDED.notes
                    WHERE
                        source_documents.source_file IS DISTINCT FROM EXCLUDED.source_file
                        OR source_documents.printed_pages IS DISTINCT FROM EXCLUDED.printed_pages
                        OR source_documents.pdf_pages IS DISTINCT FROM EXCLUDED.pdf_pages
                        OR source_documents.notes IS DISTINCT FROM EXCLUDED.notes
                    RETURNING source_id
                """),
                {
                    **source_identity,
                    "source_file": path.name,
                    "printed_pages": source["printed_pages"],
                    "pdf_pages": source["pdf_pages"],
                    "notes": "; ".join(data.get("limitations", [])),
                },
            )
            source_id = source_result.scalar_one_or_none()
            if source_id is None:
                source_id = existing_source
                counts["unchanged"] += 1
            elif existing_source is None:
                counts["inserted"] += 1
            else:
                counts["updated"] += 1
            counts["processed"] += 1

            # 2. Insert or update the main appraisal metric
            metric_identity = {
                "region": "Hamburg",
                "asset_class": metric_data["asset_class"],
                "metric_name": metric_data["name"],
                "reference_year": source["report_year"],
                "value_type": metric_data["value_type"],
                "source_url": SOURCE_URL,
            }
            metric_key = make_stable_key("appraisal_metric", metric_identity)

            existing_metric = connection.execute(
                text("SELECT metric_id FROM iris_staging.appraisal_metrics WHERE stable_key = :stable_key"),
                {"stable_key": metric_key},
            ).scalar_one_or_none()

            metric_result = connection.execute(
                text("""
                    INSERT INTO iris_staging.appraisal_metrics (
                        source_id, region, asset_class, metric_name, reference_year, value,
                        unit, value_type, formula, geographic_scope, printed_page, pdf_page, notes, stable_key
                    ) VALUES (
                        :source_id, :region, :asset_class, :metric_name, :reference_year, :value,
                        :unit, :value_type, :formula, :geographic_scope, :printed_page, :pdf_page, :notes, :stable_key
                    )
                    ON CONFLICT (stable_key)
                    DO UPDATE SET
                        source_id = EXCLUDED.source_id,
                        value = EXCLUDED.value,
                        formula = EXCLUDED.formula,
                        geographic_scope = EXCLUDED.geographic_scope,
                        notes = EXCLUDED.notes
                    WHERE
                        appraisal_metrics.source_id IS DISTINCT FROM EXCLUDED.source_id
                        OR appraisal_metrics.value IS DISTINCT FROM EXCLUDED.value
                        OR appraisal_metrics.formula IS DISTINCT FROM EXCLUDED.formula
                        OR appraisal_metrics.geographic_scope IS DISTINCT FROM EXCLUDED.geographic_scope
                        OR appraisal_metrics.notes IS DISTINCT FROM EXCLUDED.notes
                    RETURNING metric_id
                """),
                {
                    "source_id": source_id,
                    "region": "Hamburg",
                    "asset_class": metric_data["asset_class"],
                    "metric_name": metric_data["name"],
                    "reference_year": source["report_year"],
                    "value": Decimal(metric_data["base_rate_percent"]),
                    "unit": metric_data["unit"],
                    "value_type": metric_data["value_type"],
                    "formula": metric_data["formula"],
                    "geographic_scope": "Hamburg, excluding Neuwerk",
                    "printed_page": source["printed_pages"][0],
                    "pdf_page": source["pdf_pages"][0],
                    "notes": "Base rate; not a final property-specific rate.",
                    "stable_key": metric_key,
                },
            )
            metric_id = metric_result.scalar_one_or_none()
            if metric_id is None:
                metric_id = existing_metric
                counts["unchanged"] += 1
            elif existing_metric is None:
                counts["inserted"] += 1
            else:
                counts["updated"] += 1
            counts["processed"] += 1

            # 3. Prepare formula and adjustment factors
            factors = [
                {
                    "factor_type": "formula_parameter",
                    "factor_name": "location_factor",
                    "value": None,
                    "exponent": Decimal(metric_data["location_factor"]["exponent"]),
                    "reference_variable": metric_data["location_factor"]["base_land_value"],
                    "reference_value": Decimal(metric_data["location_factor"]["reference_value"]),
                    "unit": None,
                    "condition_description": None,
                    "investigation_period_start": None,
                    "investigation_period_end": None,
                    "valuation_date": None,
                    "printed_page": source["printed_pages"][0],
                    "pdf_page": source["pdf_pages"][0],
                },
                {
                    "factor_type": "formula_parameter",
                    "factor_name": "rent_factor",
                    "value": None,
                    "exponent": Decimal(metric_data["rent_factor"]["exponent"]),
                    "reference_variable": (
                        metric_data["rent_factor"]["market_rent"]
                        + "/"
                        + metric_data["rent_factor"]["reference_rent"]
                    ),
                    "reference_value": None,
                    "unit": None,
                    "condition_description": None,
                    "investigation_period_start": None,
                    "investigation_period_end": None,
                    "valuation_date": None,
                    "printed_page": source["printed_pages"][0],
                    "pdf_page": source["pdf_pages"][0],
                },
                {
                    "factor_type": "conditional_factor",
                    "factor_name": "first_occupancy_factor",
                    "value": Decimal(metric_data["first_occupancy_factor"]),
                    "exponent": None,
                    "reference_variable": None,
                    "reference_value": None,
                    "unit": None,
                    "condition_description": (
                        "Applies if the building year is the valuation year or one of the previous three years."
                    ),
                    "investigation_period_start": None,
                    "investigation_period_end": None,
                    "valuation_date": None,
                    "printed_page": source["printed_pages"][0],
                    "pdf_page": source["pdf_pages"][0],
                },
            ]

            # Add the seven date-specific update factors.
            for item in dataset["update_factors"]:
                period_start, period_end = parse_investigation_period(item["investigation_period"])
                factors.append({
                    "factor_type": "time_update_factor",
                    "factor_name": "update_factor",
                    "value": Decimal(item["value"]),
                    "exponent": None,
                    "reference_variable": None,
                    "reference_value": None,
                    "unit": None,
                    "condition_description": None,
                    "investigation_period_start": period_start,
                    "investigation_period_end": period_end,
                    "valuation_date": parse_german_date(item["valuation_date"]),
                    "printed_page": source["printed_pages"][1],
                    "pdf_page": source["pdf_pages"][1],
                })

            # 4. Insert or update adjustment factors
            for factor in factors:
                factor_identity = {
                    "metric_key": metric_key,
                    "factor_type": factor["factor_type"],
                    "factor_name": factor["factor_name"],
                    "reference_variable": factor["reference_variable"],
                    "valuation_date": (
                        factor["valuation_date"].isoformat() if factor["valuation_date"] else None
                    ),
                    "investigation_period_start": (
                        factor["investigation_period_start"].isoformat()
                        if factor["investigation_period_start"] else None
                    ),
                    "investigation_period_end": (
                        factor["investigation_period_end"].isoformat()
                        if factor["investigation_period_end"] else None
                    ),
                }
                factor_key = make_stable_key("adjustment_factor", factor_identity)

                existing = connection.execute(
                    text("SELECT factor_id FROM iris_staging.adjustment_factors WHERE stable_key = :stable_key"),
                    {"stable_key": factor_key},
                ).scalar_one_or_none()

                factor_result = connection.execute(
                    text("""
                        INSERT INTO iris_staging.adjustment_factors (
                            metric_id, factor_type, factor_name, value, exponent,
                            reference_variable, reference_value, unit, condition_description,
                            investigation_period_start, investigation_period_end, valuation_date,
                            printed_page, pdf_page, stable_key
                        ) VALUES (
                            :metric_id, :factor_type, :factor_name, :value, :exponent,
                            :reference_variable, :reference_value, :unit, :condition_description,
                            :investigation_period_start, :investigation_period_end, :valuation_date,
                            :printed_page, :pdf_page, :stable_key
                        )
                        ON CONFLICT (stable_key)
                        DO UPDATE SET
                            metric_id = EXCLUDED.metric_id,
                            value = EXCLUDED.value,
                            exponent = EXCLUDED.exponent,
                            reference_value = EXCLUDED.reference_value,
                            condition_description = EXCLUDED.condition_description,
                            investigation_period_start = EXCLUDED.investigation_period_start,
                            investigation_period_end = EXCLUDED.investigation_period_end,
                            valuation_date = EXCLUDED.valuation_date
                        WHERE
                            adjustment_factors.metric_id IS DISTINCT FROM EXCLUDED.metric_id
                            OR adjustment_factors.value IS DISTINCT FROM EXCLUDED.value
                            OR adjustment_factors.exponent IS DISTINCT FROM EXCLUDED.exponent
                            OR adjustment_factors.reference_value IS DISTINCT FROM EXCLUDED.reference_value
                            OR adjustment_factors.condition_description IS DISTINCT FROM EXCLUDED.condition_description
                            OR adjustment_factors.investigation_period_start IS DISTINCT FROM EXCLUDED.investigation_period_start
                            OR adjustment_factors.investigation_period_end IS DISTINCT FROM EXCLUDED.investigation_period_end
                            OR adjustment_factors.valuation_date IS DISTINCT FROM EXCLUDED.valuation_date
                        RETURNING factor_id
                    """),
                    {**factor, "metric_id": metric_id, "stable_key": factor_key},
                )
                factor_id = factor_result.scalar_one_or_none()
                if factor_id is None:
                    counts["unchanged"] += 1
                elif existing is None:
                    counts["inserted"] += 1
                else:
                    counts["updated"] += 1
                counts["processed"] += 1

            # 5. Insert or update sample statistics
            statistics = []
            for name, values in dataset["sample_statistics"].items():
                statistics.append({
                    "statistic_type": "sample_statistic",
                    "statistic_name": name,
                    "minimum_value": Decimal(values["minimum"]),
                    "maximum_value": Decimal(values["maximum"]),
                    "mean_value": Decimal(values["mean"]),
                    "observed_value": None,
                    "sample_size": values["sample_size"],
                    "unit": (
                        "EUR/m2" if "EUR_per_m2" in name
                        else "m2" if name == "usable_area_m2"
                        else "year" if name == "construction_year"
                        else None
                    ),
                    "printed_page": source["printed_pages"][2],
                    "pdf_page": source["pdf_pages"][2],
                    "notes": None,
                })

            quality = data["quality_metric"]
            statistics.append({
                "statistic_type": "quality_indicator",
                "statistic_name": quality["name"],
                "minimum_value": None,
                "maximum_value": None,
                "mean_value": None,
                "observed_value": Decimal(quality["value_percent"]),
                "sample_size": None,
                "unit": "%",
                "printed_page": source["printed_pages"][2],
                "pdf_page": source["pdf_pages"][2],
                "notes": None,
            })

            for statistic in statistics:
                statistic_identity = {
                    "metric_key": metric_key,
                    "statistic_type": statistic["statistic_type"],
                    "statistic_name": statistic["statistic_name"],
                }
                statistic_key = make_stable_key("sample_statistic", statistic_identity)

                existing = connection.execute(
                    text("SELECT statistic_id FROM iris_staging.sample_statistics WHERE stable_key = :stable_key"),
                    {"stable_key": statistic_key},
                ).scalar_one_or_none()

                statistic_result = connection.execute(
                    text("""
                        INSERT INTO iris_staging.sample_statistics (
                            metric_id, statistic_type, statistic_name, minimum_value, maximum_value,
                            mean_value, observed_value, sample_size, unit, printed_page, pdf_page, notes, stable_key
                        ) VALUES (
                            :metric_id, :statistic_type, :statistic_name, :minimum_value, :maximum_value,
                            :mean_value, :observed_value, :sample_size, :unit, :printed_page, :pdf_page, :notes, :stable_key
                        )
                        ON CONFLICT (stable_key)
                        DO UPDATE SET
                            metric_id = EXCLUDED.metric_id,
                            minimum_value = EXCLUDED.minimum_value,
                            maximum_value = EXCLUDED.maximum_value,
                            mean_value = EXCLUDED.mean_value,
                            observed_value = EXCLUDED.observed_value,
                            sample_size = EXCLUDED.sample_size,
                            unit = EXCLUDED.unit,
                            notes = EXCLUDED.notes
                        WHERE
                            sample_statistics.metric_id IS DISTINCT FROM EXCLUDED.metric_id
                            OR sample_statistics.minimum_value IS DISTINCT FROM EXCLUDED.minimum_value
                            OR sample_statistics.maximum_value IS DISTINCT FROM EXCLUDED.maximum_value
                            OR sample_statistics.mean_value IS DISTINCT FROM EXCLUDED.mean_value
                            OR sample_statistics.observed_value IS DISTINCT FROM EXCLUDED.observed_value
                            OR sample_statistics.sample_size IS DISTINCT FROM EXCLUDED.sample_size
                            OR sample_statistics.unit IS DISTINCT FROM EXCLUDED.unit
                            OR sample_statistics.notes IS DISTINCT FROM EXCLUDED.notes
                        RETURNING statistic_id
                    """),
                    {**statistic, "metric_id": metric_id, "stable_key": statistic_key},
                )
                statistic_id = statistic_result.scalar_one_or_none()
                if statistic_id is None:
                    counts["unchanged"] += 1
                elif existing is None:
                    counts["inserted"] += 1
                else:
                    counts["updated"] += 1
                counts["processed"] += 1

            # 6. Record successful ingestion run
            connection.execute(
                text("""
                    INSERT INTO iris_staging.ingestion_runs (
                        source_id, finished_at, status, processed_count, inserted_count,
                        updated_count, unchanged_count, failed_count
                    ) VALUES (
                        :source_id, CURRENT_TIMESTAMP, 'completed', :processed, :inserted,
                        :updated, :unchanged, 0
                    )
                """),
                {
                    "source_id": source_id,
                    "processed": counts["processed"],
                    "inserted": counts["inserted"],
                    "updated": counts["updated"],
                    "unchanged": counts["unchanged"],
                },
            )

    
    except Exception as error:
        # The main transaction has been rolled back.
        counts["failed"] += 1

        # Record the failure independently.
        # source_id is NULL because the source row may have
        # been inserted in the rolled-back transaction.
        try:
            with engine.begin() as connection:
                connection.execute(
                    text("""
                        INSERT INTO iris_staging.ingestion_runs (
                            source_id, finished_at, status, processed_count,
                            inserted_count, updated_count, unchanged_count,
                            failed_count, error_summary
                        ) VALUES (
                            NULL, CURRENT_TIMESTAMP, 'failed', :processed,
                            0, 0, 0, :failed, :error_summary
                        )
                    """),
                    {
                        "processed": counts["processed"],
                        "failed": counts["failed"],
                        "error_summary": str(error)[:2000],
                    },
                )
        except Exception as logging_error:
            print(f"Could not record ingestion failure: {logging_error}")

        raise


    return counts

if __name__ == "__main__":
    result = ingest_hamburg_fixture()
    print("\nHamburg data ingestion completed!")
    print("---------------------------------")
    print("Processed:", result["processed"])
    print("Inserted:", result["inserted"])
    print("Updated:", result["updated"])
    print("Unchanged:", result["unchanged"])
    print("Failed:", result["failed"])
    engine.dispose()