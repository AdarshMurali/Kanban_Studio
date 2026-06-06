from fastapi import APIRouter, Depends, HTTPException, status
from fastapi import Header
from pydantic import BaseModel
import bcrypt

from app.dependencies import get_db
from app.database import get_or_create_user, verify_password

router = APIRouter()

class UserRegister(BaseModel):
    username: str
    password: str

class UserLogin(BaseModel):
    username: str
    password: str

@router.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(user: UserRegister, conn = Depends(get_db)):
    # Check if user already exists
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (user.username,)).fetchone()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered"
        )

    # Create user - get_or_create_user will handle password hashing
    user_id = get_or_create_user(conn, user.username, user.password)
    return {"message": "User created successfully", "user_id": user_id}

@router.post("/api/auth/login")
def login_user(user: UserLogin, conn = Depends(get_db)):
    # Get user by username
    row = conn.execute("SELECT id, password_hash FROM users WHERE username = ?", (user.username,)).fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Verify password
    if not verify_password(user.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    return {"message": "Login successful", "user_id": row["id"]}

@router.post("/api/auth/logout")
def logout_user():
    # For header-based auth, logout is client-side
    # If we implement sessions/tokens, this would invalidate them
    return {"message": "Logout successful"}

@router.get("/api/auth/me")
def get_current_user(x_user: str | None = Header(default=None), conn = Depends(get_db)):
    username = x_user
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User header required"
        )

    row = conn.execute("SELECT id, username FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"id": row["id"], "username": row["username"]}