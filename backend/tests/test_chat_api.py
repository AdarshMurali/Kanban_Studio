import os
import tempfile
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, connect_db

# Create a temporary database for testing
def setup_test_db():
    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    temp_db.close()
    db_path = Path(temp_db.name)

    # Set environment variable to use our test database
    old_env = os.environ.get("PM_DB_PATH")
    os.environ["PM_DB_PATH"] = str(db_path)

    # Initialize database
    conn = connect_db()
    init_db()
    conn.close()

    return db_path, old_env

def teardown_test_db(db_path, old_env):
    # Clean up
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

client = TestClient(app)


def test_chat_missing_api_key(monkeypatch) -> None:
    # Set up test database
    db_path, old_env = setup_test_db()
    try:
        monkeypatch.setenv("OPENROUTER_API_KEY", "")
        response = client.post("/api/chat", json={"message": "2+2"})
        assert response.status_code == 500
        assert response.json() == {"detail": "OPENROUTER_API_KEY not configured"}
    finally:
        teardown_test_db(db_path, old_env)
