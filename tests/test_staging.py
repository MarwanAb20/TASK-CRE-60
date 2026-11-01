
from sqlalchemy import text
from src.database import engine


EXPECTED_TABLES = {
    "source_documents",
    "appraisal_metrics",
    "adjustment_factors",
    "sample_statistics",
    "ingestion_runs",
}


def test_staging_schema_exists():
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT schema_name
                FROM information_schema.schemata
                WHERE schema_name = 'iris_staging'
            """)
        ).scalar_one_or_none()

    assert result == "iris_staging"


def test_all_staging_tables_exist():
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'iris_staging'
            """)
        )

        actual_tables = {row[0] for row in result}

    assert EXPECTED_TABLES.issubset(actual_tables)


def test_unchanged_count_column_exists():
    with engine.connect() as connection:
        result = connection.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'iris_staging'
                  AND table_name = 'ingestion_runs'
                  AND column_name = 'unchanged_count'
            """)
        ).scalar_one_or_none()

    assert result == "unchanged_count"
