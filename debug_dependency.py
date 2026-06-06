import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from fastapi import Header
from app.database import connect_db
from app.config import DEFAULT_USER

def get_username(x_user: str | None = Header(default=None)) -> str:
    username = x_user or DEFAULT_USER

    # Validate that the user exists in the database
    # This ensures that only registered users can access the system
    conn = connect_db()
    try:
        user_exists = conn.execute(
            "SELECT 1 FROM users WHERE username = ?",
            (username,)
        ).fetchone()
        if not user_exists:
            from fastapi import HTTPException, status
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
    finally:
        conn.close()

    return username

def test_dependency():
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = Path(tmp_db.name)
        old_env = os.environ.get("PM_DB_PATH")
        os.environ["PM_DB_PATH"] = str(db_path)

        try:
            from app.database import init_db, connect_db, get_or_create_user
            from app.config import DEFAULT_USER, DEFAULT_PASSWORD

            # Initialize database and create default user
            conn = connect_db()
            init_db()
            # Explicitly create the default user to ensure it exists
            get_or_create_user(conn, DEFAULT_USER, DEFAULT_PASSWORD)
            conn.commit()
            conn.close()

            # Test with no header (should default to DEFAULT_USER)
            print("Testing get_username with no header:")
            try:
                result = get_username(None)  # Simulate no header
                print(f"Result: {result}")
            except Exception as e:
                print(f"Exception: {e}")

            # Test with explicit default user header
            print("\nTesting get_username with default user header:")
            try:
                result = get_username("user")  # Simulate X-User: user header
                print(f"Result: {result}")
            except Exception as e:
                print(f"Exception: {e}")

            # Test with non-existent user
            print("\nTesting get_username with non-existent user:")
            try:
                result = get_username("nonexistent")  # Simulate X-User: nonexistent header
                print(f"Result: {result}")
            except Exception as e:
                print(f"Exception: {e}")

        finally:
            if old_env is not None:
                os.environ["PM_DB_PATH"] = old_env
            elif "PM_DB_PATH" in os.environ:
                del os.environ["PM_DB_PATH"]
            try:
                if db_path.exists():
                    db_path.unlink()
            except PermissionError:
                import time
                time.sleep(0.1)
                if db_path.exists():
                    db_path.unlink()

if __name__ == "__main__":
    test_dependency()