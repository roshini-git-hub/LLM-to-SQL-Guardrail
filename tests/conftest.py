import os

import psycopg2
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def admin():
    """A connection as the database owner, used only by tests to change GRANTs/DDL."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"), port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("ADMIN_USER") or os.getenv("USER"),
        password=os.getenv("ADMIN_PASSWORD") or None,
    )
    conn.autocommit = True
    yield conn.cursor()
    conn.close()
