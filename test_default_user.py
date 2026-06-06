import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from fastapi.testclient import TestClient
from app.main import app
import tempfile
from pathlib import Path

client = TestClient(app)

def test_default_user():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = Path(tmp_db.name)
        old_env = os.environ.get("PM_DB_PATH")
        os.environ["PM_DB_PATH"] = str(db_path)

        try:
            # Initialize database
            from app.database import connect_db, init_db
            conn = connect_db()
            init_db()
            conn.close()

            # Test that default user can login
            response = client.post(
                "/api/auth/login",
                json={"username": "user", "password": "password"}
            )
            print(f"Login response status: {response.status_code}")
            if response.status_code != 200:
                print(f"Login response: {response.json()}")

            # Test that default user can access board
            response = client.get("/api/board", headers={"X-User": "user"})
            print(f"Board access response status: {response.status_code}")
            if response.status_code != 200:
                print(f"Board access response: {response.json()}")

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
    test_default_user()