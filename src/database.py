
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Load environment variables
load_dotenv()

DB_URI = os.getenv("DB_URI")

if not DB_URI:
    raise ValueError("DB_URI is not configured in .env")

# Create database engine
engine = create_engine(
    DB_URI,
    pool_pre_ping=True
)


def test_connection():
    try:
        with engine.connect() as connection:

            result = connection.execute(
                text("""
                    SELECT
                        current_database(),
                        current_schema(),
                        PostGIS_Full_Version()
                """)
            )

            database, schema, postgis = result.fetchone()

            print("Database connection successful!")
            print(f"Database: {database}")
            print(f"Schema: {schema}")
            print(f"PostGIS: {postgis}")

    except SQLAlchemyError as error:
        print(f"Database connection failed: {error}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    test_connection()
