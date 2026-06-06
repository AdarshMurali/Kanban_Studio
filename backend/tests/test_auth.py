import os
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.database import init_db, connect_db

client = TestClient(app)


def test_register_user():
    # Use a temporary database for testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = Path(tmp_db.name)
        os.environ["PM_DB_PATH"] = str(db_path)

        try:
            # Initialize database tables
            conn = connect_db()
            init_db()
            conn.close()

            # Test user registration
            response = client.post(
                "/api/auth/register",
                json={"username": "testuser", "password": "testpass"}
            )
            assert response.status_code == 201
            data = response.json()
            assert "message" in data
            assert data["message"] == "User created successfully"
            assert "user_id" in data
            assert isinstance(data["user_id"], int)

            # Test duplicate user registration
            response = client.post(
                "/api/auth/register",
                json={"username": "testuser", "password": "testpass2"}
            )
            assert response.status_code == 409
            data = response.json()
            assert "detail" in data
            assert data["detail"] == "Username already registered"

            # Test login with correct credentials
            response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpass"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert data["message"] == "Login successful"
            assert "user_id" in data

            # Test login with incorrect password
            response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "wrongpass"}
            )
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
            assert data["detail"] == "Invalid username or password"

            # Test login with non-existent user
            response = client.post(
                "/api/auth/login",
                json={"username": "nonexistent", "password": "anypass"}
            )
            assert response.status_code == 401
            data = response.json()
            assert "detail" in data
            assert data["detail"] == "Invalid username or password"

            # Test logout endpoint
            response = client.post("/api/auth/logout")
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert data["message"] == "Logout successful"

            # Test get current user (requires authentication header)
            # First login to establish the user context via header in a real scenario
            # For testing, we'll directly test the endpoint with a username that exists
            response = client.get("/api/auth/me", headers={"X-User": "testuser"})
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "username" in data
            assert data["username"] == "testuser"

            # Test get current user for non-existent user
            response = client.get("/api/auth/me", headers={"X-User": "nonexistent"})
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert data["detail"] == "User not found"

        finally:
            # Clean up
            if "PM_DB_PATH" in os.environ:
                del os.environ["PM_DB_PATH"]
            # Close any connections before deleting
            try:
                if db_path.exists():
                    db_path.unlink()
            except PermissionError:
                # On Windows, sometimes the file is locked, try again after a brief moment
                import time
                time.sleep(0.1)
                if db_path.exists():
                    db_path.unlink()


def test_default_user_still_works():
    # Test that the default user still works for backward compatibility
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = Path(tmp_db.name)
        os.environ["PM_DB_PATH"] = str(db_path)

        try:
            # Initialize database tables
            conn = connect_db()
            init_db()
            conn.close()

            # Test login with default user credentials
            response = client.post(
                "/api/auth/login",
                json={"username": "user", "password": "password"}
            )
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert data["message"] == "Login successful"
            assert "user_id" in data

            # Test that we can access the board with default user
            response = client.get("/api/board", headers={"X-User": "user"})
            assert response.status_code == 200
            data = response.json()
            assert "board" in data
            assert "columns" in data
            assert "cards" in data

        finally:
            # Clean up
            if "PM_DB_PATH" in os.environ:
                del os.environ["PM_DB_PATH"]
            # Close any connections before deleting
            try:
                if db_path.exists():
                    db_path.unlink()
            except PermissionError:
                # On Windows, sometimes the file is locked, try again after a brief moment
                import time
                time.sleep(0.1)
                if db_path.exists():
                    db_path.unlink()