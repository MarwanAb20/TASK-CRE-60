from sqlalchemy import text
from src.database import engine


def check_staging_schema():
    query = text("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name = 'iris_staging'
    """)

    with engine.connect() as connection:
        result = connection.execute(query).scalar_one_or_none()

    if result is None:
        raise RuntimeError("iris_staging schema does not exist")

    print("Staging schema exists:", result)


if __name__ == "__main__":
    check_staging_schema()
    engine.dispose()
