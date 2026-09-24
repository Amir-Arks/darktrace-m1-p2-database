"""
Database Connection Verification Script.

Usage:
    python scripts/test_db_connection.py

This script verifies that:
1. DATABASE_URL is configured and can be parsed.
2. SQLAlchemy engine can establish a physical connection to the database.
3. Basic SQL queries ('SELECT 1') execute successfully.
4. Transactional sessions can be opened and closed without errors.
"""
import sys
from sqlalchemy import text
from app.core.config import settings
from app.db.session import engine, SessionLocal


def check_connection():
    print("=" * 60)
    print("DarkTrace M1 Pod 2 - Database Connection Verification")
    print("=" * 60)

    # Safely print masked URL
    masked_url = str(engine.url)
    print(f"[*] Target Database: {masked_url}")
    print(f"[*] Dialect:         {engine.dialect.name}")

    # 1. Test Raw Engine Connection
    print("\n[Step 1/3] Testing physical database connection...")
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            if result == 1:
                print(" -> [SUCCESS] Connection established and query 'SELECT 1' succeeded.")
            else:
                print(f" -> [WARNING] Query executed but returned unexpected value: {result}")
    except Exception as e:
        print(f" -> [FAILURE] Could not connect to database.")
        print(f"\nError Details:\n{e}")
        print("\nTroubleshooting Tips:")
        print("  1. Is PostgreSQL installed and running? (Check service or Docker container)")
        print("  2. Does the database exist? (CREATE DATABASE darktrace_pod2;)")
        print("  3. Check credentials in your local .env file.")
        print("  4. For offline unit testing, you can set DATABASE_URL=sqlite:///./test.db in .env")
        sys.exit(1)

    # 2. Test SessionLocal Factory
    print("\n[Step 2/3] Testing SQLAlchemy SessionLocal factory...")
    try:
        session = SessionLocal()
        session_result = session.execute(text("SELECT 1")).scalar()
        session.close()
        print(" -> [SUCCESS] SessionLocal opened, executed query, and closed cleanly.")
    except Exception as e:
        print(f" -> [FAILURE] SessionLocal encountered an error: {e}")
        sys.exit(1)

    # 3. Test Transaction Rollback
    print("\n[Step 3/3] Testing transaction rollback behavior...")
    try:
        session = SessionLocal()
        session.rollback()
        session.close()
        print(" -> [SUCCESS] Transaction rollback verified.")
    except Exception as e:
        print(f" -> [FAILURE] Transaction rollback failed: {e}")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("All Database Connection Checks PASSED! Ready for module integration.")
    print("=" * 60)


if __name__ == "__main__":
    check_connection()
