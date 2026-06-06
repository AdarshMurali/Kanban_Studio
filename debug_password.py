import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import bcrypt
import tempfile
from pathlib import Path
from app.database import connect_db, get_or_create_user

# Test password hashing and verification directly
print("Testing bcrypt directly:")
password = "testpass"
password_bytes = password.encode('utf-8')
hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
print(f"Password: {password}")
print(f"Hashed: {hashed}")

# Verify
verify_result = bcrypt.checkpw(password_bytes, hashed.encode('utf-8'))
print(f"Verification result: {verify_result}")

# Test with empty password
print("\nTesting empty password:")
empty_hash = ""
verify_empty = not ""  # Should be True for empty password
print(f"Empty password verification: {verify_empty}")

# Test database storage
print("\nTesting database storage:")
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
    db_path = Path(tmp_db.name)
    old_env = os.environ.get("PM_DB_PATH")
    os.environ["PM_DB_PATH"] = str(db_path)

    try:
        # Initialize database
        conn = connect_db()
        from app.database import init_db
        init_db()

        # Create user
        username = "testuser"
        password = "testpass"
        password_bytes = password.encode('utf-8')
        hashed_password = bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode('utf-8')
        print(f"Storing hash: {hashed_password}")

        user_id = get_or_create_user(conn, username, hashed_password)
        print(f"Created user with ID: {user_id}")

        # Retrieve user
        row = conn.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,)).fetchone()
        print(f"Retrieved user: id={row['id']}, username={row['username']}, hash={row['password_hash']}")

        # Verify password
        stored_hash = row["password_hash"]
        verify_result = bcrypt.checkpw(password_bytes, stored_hash.encode('utf-8'))
        print(f"Password verification: {verify_result}")

        conn.close()

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