import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.database import connect_db, init_db, get_or_create_user
from app.config import DEFAULT_USER, DEFAULT_PASSWORD
import bcrypt

def debug_default_user():
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_db:
        db_path = Path(tmp_db.name)
        old_env = os.environ.get("PM_DB_PATH")
        os.environ["PM_DB_PATH"] = str(db_path)

        try:
            # Initialize database
            conn = connect_db()
            init_db()

            # Check what's in the users table
            rows = conn.execute("SELECT id, username, password_hash FROM users").fetchall()
            print(f"Users in DB after init: {len(rows)}")
            for row in rows:
                print(f"  id={row['id']}, username={row['username']}, hash={row['password_hash']}")

            # Test get_or_create_user for default user
            print(f"\nTesting get_or_create_user for default user:")
            print(f"DEFAULT_USER = '{DEFAULT_USER}'")
            print(f"DEFAULT_PASSWORD = '{DEFAULT_PASSWORD}'")

            user_id = get_or_create_user(conn, DEFAULT_USER, DEFAULT_PASSWORD)
            print(f"get_or_create_user returned: {user_id}")

            # Check what's in the users table now
            rows = conn.execute("SELECT id, username, password_hash FROM users").fetchall()
            print(f"Users in DB after get_or_create_user: {len(rows)}")
            for row in rows:
                print(f"  id={row['id']}, username={row['username']}, hash={row['password_hash']}")

                # Test password verification
                if row['username'] == DEFAULT_USER:
                    print(f"  Testing password verification for default user:")
                    password_bytes = DEFAULT_PASSWORD.encode('utf-8')
                    hash_bytes = row['password_hash'].encode('utf-8')
                    verify_result = bcrypt.checkpw(password_bytes, hash_bytes)
                    print(f"    Password: {DEFAULT_PASSWORD}")
                    print(f"    Stored hash: {row['password_hash']}")
                    print(f"    Verification result: {verify_result}")

            conn.commit()
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

if __name__ == "__main__":
    debug_default_user()