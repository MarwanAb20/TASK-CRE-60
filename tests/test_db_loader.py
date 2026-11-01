
import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

import src.normalization.db_loader as db_loader


TEST_FIXTURE = Path("data/fixtures/hamburg_2026_parsed.json")

TABLES = """
TRUNCATE TABLE
    iris_staging.ingestion_runs,
    iris_staging.sample_statistics,
    iris_staging.adjustment_factors,
    iris_staging.appraisal_metrics,
    iris_staging.source_documents
RESTART IDENTITY CASCADE
"""


@pytest.fixture
def test_engine(monkeypatch):
    """
    Use only the dedicated iris_test database.
    Never allow this test suite to run against iris_dev.
    """
    test_db_uri = os.getenv("TEST_DB_URI")

    if not test_db_uri:
        pytest.fail("TEST_DB_URI is missing from the .env file")

    engine = create_engine(test_db_uri, pool_pre_ping=True)

    with engine.connect() as connection:
        database_name = connection.execute(
            text("SELECT current_database()")
        ).scalar_one()

    if database_name != "iris_test":
        engine.dispose()
        pytest.fail(
            f"Unsafe test database: {database_name}. Expected iris_test."
        )

    # Clear only the dedicated test database.
    with engine.begin() as connection:
        connection.execute(text(TABLES))

    monkeypatch.setattr(db_loader, "engine", engine)

    yield engine

    engine.dispose()


def read_run_counts(engine):
    with engine.connect() as connection:
        return connection.execute(
            text("""
                SELECT
                    processed_count,
                    inserted_count,
                    updated_count,
                    unchanged_count,
                    failed_count,
                    status
                FROM iris_staging.ingestion_runs
                ORDER BY run_id DESC
                LIMIT 1
            """)
        ).mappings().one()


def test_first_ingestion_inserts_17_records(test_engine):
    result = db_loader.ingest_hamburg_fixture(TEST_FIXTURE)

    assert result == {
        "processed": 17,
        "inserted": 17,
        "updated": 0,
        "unchanged": 0,
        "failed": 0,
    }

    run = read_run_counts(test_engine)

    assert run["status"] == "completed"
    assert run["inserted_count"] == 17

    with test_engine.connect() as connection:
        metric_count = connection.execute(
            text("SELECT COUNT(*) FROM iris_staging.appraisal_metrics")
        ).scalar_one()

        factor_count = connection.execute(
            text("SELECT COUNT(*) FROM iris_staging.adjustment_factors")
        ).scalar_one()

        statistic_count = connection.execute(
            text("SELECT COUNT(*) FROM iris_staging.sample_statistics")
        ).scalar_one()

    assert metric_count == 1
    assert factor_count == 10
    assert statistic_count == 5


def test_second_ingestion_does_not_duplicate_records(test_engine):
    db_loader.ingest_hamburg_fixture(TEST_FIXTURE)

    result = db_loader.ingest_hamburg_fixture(TEST_FIXTURE)

    assert result == {
        "processed": 17,
        "inserted": 0,
        "updated": 0,
        "unchanged": 17,
        "failed": 0,
    }

    with test_engine.connect() as connection:
        source_count = connection.execute(
            text("SELECT COUNT(*) FROM iris_staging.source_documents")
        ).scalar_one()

        metric_count = connection.execute(
            text("SELECT COUNT(*) FROM iris_staging.appraisal_metrics")
        ).scalar_one()

    assert source_count == 1
    assert metric_count == 1


def test_changed_metric_is_updated(test_engine, tmp_path):
    db_loader.ingest_hamburg_fixture(TEST_FIXTURE)

    modified_data = json.loads(
        TEST_FIXTURE.read_text(encoding="utf-8")
    )

    modified_data["metric"]["base_rate_percent"] = "4.12"

    modified_fixture = tmp_path / TEST_FIXTURE.name
    modified_fixture.write_text(
        json.dumps(modified_data, ensure_ascii=False),
        encoding="utf-8",
    )

    result = db_loader.ingest_hamburg_fixture(modified_fixture)

    assert result == {
        "processed": 17,
        "inserted": 0,
        "updated": 1,
        "unchanged": 16,
        "failed": 0,
    }

    with test_engine.connect() as connection:
        stored_value = connection.execute(
            text("""
                SELECT value
                FROM iris_staging.appraisal_metrics
            """)
        ).scalar_one()

    assert float(stored_value) == pytest.approx(4.12)


def test_failed_ingestion_rolls_back_partial_data(test_engine, tmp_path):
    modified_data = json.loads(
        TEST_FIXTURE.read_text(encoding="utf-8")
    )

    # Force an invalid date after the source and metric
    # have been processed inside the transaction.
    modified_data["dataset"]["update_factors"][0][
        "valuation_date"
    ] = "invalid-date"

    invalid_fixture = tmp_path / "invalid_hamburg.json"
    invalid_fixture.write_text(
        json.dumps(modified_data, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="time data"):
        db_loader.ingest_hamburg_fixture(invalid_fixture)

    with test_engine.connect() as connection:
        source_count = connection.execute(
            text("SELECT COUNT(*) FROM iris_staging.source_documents")
        ).scalar_one()

        metric_count = connection.execute(
            text("SELECT COUNT(*) FROM iris_staging.appraisal_metrics")
        ).scalar_one()

        failed_runs = connection.execute(
            text("""
                SELECT COUNT(*)
                FROM iris_staging.ingestion_runs
                WHERE status = 'failed'
            """)
        ).scalar_one()

        failed_source_id = connection.execute(
            text("""
                SELECT source_id
                FROM iris_staging.ingestion_runs
                WHERE status = 'failed'
                ORDER BY run_id DESC
                LIMIT 1
            """)
        ).scalar_one()

    assert source_count == 0
    assert metric_count == 0
    assert failed_runs == 1
    assert failed_source_id is None
