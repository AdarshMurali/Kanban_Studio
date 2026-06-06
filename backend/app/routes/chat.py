import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from app.ai import apply_actions, build_structured_messages, call_openrouter, parse_structured_output
from app.database import fetch_board, get_or_create_user
from app.dependencies import get_db, get_username
from app.config import DEFAULT_PASSWORD, DEFAULT_USER
from app.models import ChatRequest, ChatResponse

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    username: str = Depends(get_username),
    conn: sqlite3.Connection = Depends(get_db),
) -> ChatResponse:
    # For backward compatibility, handle default user specially
    from app.config import DEFAULT_USER, DEFAULT_PASSWORD
    if username == DEFAULT_USER:
        # For default user, ensure they exist with the default password
        user_id = get_or_create_user(conn, username, DEFAULT_PASSWORD)
    else:
        # For all other users, they must be registered via /api/auth/register
        user_row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not user_row:
            raise HTTPException(status_code=404, detail="User not found")
        user_id = int(user_row["id"])
    board = fetch_board(conn, user_id)
    messages = build_structured_messages(board, payload.history, payload.message)
    content, model = call_openrouter(messages)
    structured = parse_structured_output(content)

    if payload.apply_updates and structured.actions:
        apply_actions(conn, user_id, structured.actions)
        board = fetch_board(conn, user_id)

    return ChatResponse(
        response=structured.reply,
        actions=structured.actions,
        board=board,
        model=model,
    )
