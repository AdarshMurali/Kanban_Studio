import json
import sqlite3

import httpx
from fastapi import HTTPException

from app.config import (
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    OPENROUTER_TEMPERATURE,
    get_openrouter_api_key,
)
from app.database import get_or_create_board, ordered_ids, resequence_positions
from app.logging_config import app_logger
from app.models import (
    ChatHistoryItem,
    CreateCardAction,
    DeleteCardAction,
    MoveCardAction,
    StructuredChatOutput,
    UpdateCardAction,
    ChatAction,
)


def parse_structured_output(content: str) -> StructuredChatOutput:
    try:
        data = json.loads(content)
        app_logger.debug("Successfully parsed structured output from OpenRouter")
    except json.JSONDecodeError as exc:
        app_logger.warning(f"Initial JSON parse failed, attempting to extract JSON: {exc}")
        trimmed = content.strip()
        start = trimmed.find("{")
        end = trimmed.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                data = json.loads(trimmed[start : end + 1])
                app_logger.debug("Successfully extracted JSON from OpenRouter response")
            except json.JSONDecodeError as inner_exc:
                app_logger.error(f"Failed to extract valid JSON from OpenRouter response: {inner_exc}")
                raise HTTPException(
                    status_code=502, detail="OpenRouter returned invalid JSON"
                ) from inner_exc
        else:
            app_logger.error("OpenRouter returned invalid JSON - no JSON object found")
            raise HTTPException(status_code=502, detail="OpenRouter returned invalid JSON") from exc
    return StructuredChatOutput.model_validate(data)


def call_openrouter(messages: list[dict[str, str]]) -> tuple[str, str | None]:
    api_key = get_openrouter_api_key()
    if not api_key:
        app_logger.error("OPENROUTER_API_KEY not configured")
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not configured")

    app_logger.debug(f"Calling OpenRouter with model {OPENROUTER_MODEL}")
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": OPENROUTER_TEMPERATURE,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = httpx.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
            timeout=20,
        )
    except httpx.RequestError as exc:
        app_logger.error(f"OpenRouter request failed: {exc}")
        raise HTTPException(status_code=502, detail="OpenRouter request failed") from exc

    if response.status_code >= 400:
        app_logger.error(f"OpenRouter returned error status {response.status_code}: {response.text}")
        raise HTTPException(status_code=502, detail="OpenRouter returned an error")

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        app_logger.error("OpenRouter response missing choices")
        raise HTTPException(status_code=502, detail="OpenRouter response missing choices")
    message_data = choices[0].get("message")
    if not message_data or "content" not in message_data:
        app_logger.error("OpenRouter response missing content")
        raise HTTPException(status_code=502, detail="OpenRouter response missing content")

    content = str(message_data["content"]).strip()
    model = data.get("model")
    app_logger.debug(f"OpenRouter response received, model: {model}")
    return content, model


def build_structured_messages(
    board: dict, history: list[ChatHistoryItem], message: str
) -> list[dict[str, str]]:
    summary_parts = []
    column_titles = []
    columns = board.get("columns", [])
    cards = board.get("cards", {})
    for column in columns:
        column_titles.append(str(column.get("title")))
        card_titles = [
            cards[card_id]["title"]
            for card_id in column.get("cardIds", [])
            if card_id in cards
        ]
        summary_parts.append(
            f"{column.get('title')}: {', '.join(card_titles) if card_titles else 'No cards'}"
        )
    board_summary = " | ".join(summary_parts)
    column_summary = ", ".join(column_titles)
    schema_hint = (
        "You are a Kanban assistant. Reply only as JSON with this shape:\n"
        '{"reply": string, "actions": [action, ...]}\n'
        "Keep replies concise (1-2 sentences) unless the user requests detail.\n"
        "Board data is ALWAYS provided below. Never claim you lack board data.\n"
        "If asked to summarize the project or board, use ONLY the provided board data.\n"
        "List the columns exactly as provided and mention a few key cards. Do not invent columns or cards.\n"
        "Action types:\n"
        '- create_card: {"type": "create_card", "columnId": string, "title": string, '
        '"details": string, "position": number|null}\n'
        '- update_card: {"type": "update_card", "cardId": string, "title": string|null, '
        '"details": string|null}\n'
        '- move_card: {"type": "move_card", "cardId": string, "columnId": string, '
        '"position": number|null}\n'
        '- delete_card: {"type": "delete_card", "cardId": string}\n'
        "Do not include any extra keys or text.\n\n"
        f"Board columns (authoritative): {column_summary}\n"
        f"Board summary (authoritative): {board_summary}\n"
        f"Current board data (JSON):\n{json.dumps(board, indent=2)}"
    )
    messages_list = [{"role": "system", "content": schema_hint}]
    for item in history:
        messages_list.append({"role": item.role, "content": item.content})
    messages_list.append({"role": "user", "content": message})
    return messages_list


def apply_actions(
    conn: sqlite3.Connection, user_id: int, actions: list[ChatAction]
) -> None:
    board_id = get_or_create_board(conn, user_id)
    app_logger.info(f"Applying {len(actions)} actions for user {user_id}, board {board_id}")

    for action in actions:
        if isinstance(action, CreateCardAction):
            app_logger.debug(f"Creating card in column {action.columnId}")
            column = conn.execute(
                "SELECT id FROM columns WHERE id = ? AND board_id = ?",
                (int(action.columnId), board_id),
            ).fetchone()
            if not column:
                app_logger.warning(f"Column {action.columnId} not found for board {board_id}")
                continue

            cards = conn.execute(
                "SELECT id FROM cards WHERE column_id = ? AND archived = 0 ORDER BY position",
                (int(action.columnId),),
            ).fetchall()
            ids = ordered_ids(cards)

            insert_position = action.position
            if insert_position is None or insert_position > len(ids):
                insert_position = len(ids)
            if insert_position < 0:
                insert_position = 0

            cursor = conn.execute(
                "INSERT INTO cards (column_id, title, details, position) VALUES (?, ?, ?, ?)",
                (int(action.columnId), action.title, action.details, insert_position),
            )
            card_id = int(cursor.lastrowid)
            ids.insert(insert_position, card_id)
            resequence_positions(conn, "cards", ids, "AND column_id = ?", (int(action.columnId),))
            app_logger.info(f"Created card {card_id} in column {action.columnId}")
            continue

        if isinstance(action, UpdateCardAction):
            app_logger.debug(f"Updating card {action.cardId}")
            card_row = conn.execute(
                """
                SELECT cards.id
                FROM cards
                JOIN columns ON cards.column_id = columns.id
                WHERE cards.id = ? AND columns.board_id = ?
                """,
                (int(action.cardId), board_id),
            ).fetchone()
            if not card_row:
                app_logger.warning(f"Card {action.cardId} not found for board {board_id}")
                continue
            if action.title is not None:
                conn.execute(
                    "UPDATE cards SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (action.title, int(action.cardId)),
                )
                app_logger.debug(f"Updated title for card {action.cardId}")
            if action.details is not None:
                conn.execute(
                    "UPDATE cards SET details = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (action.details, int(action.cardId)),
                )
                app_logger.debug(f"Updated details for card {action.cardId}")
            continue

        if isinstance(action, MoveCardAction):
            app_logger.debug(f"Moving card {action.cardId} to column {action.columnId}")
            card = conn.execute(
                """
                SELECT cards.id, cards.column_id
                FROM cards
                JOIN columns ON cards.column_id = columns.id
                WHERE cards.id = ? AND columns.board_id = ?
                """,
                (int(action.cardId), board_id),
            ).fetchone()
            if not card:
                app_logger.warning(f"Card {action.cardId} not found for board {board_id}")
                continue

            target_column = conn.execute(
                "SELECT id FROM columns WHERE id = ? AND board_id = ?",
                (int(action.columnId), board_id),
            ).fetchone()
            if not target_column:
                app_logger.warning(f"Target column {action.columnId} not found for board {board_id}")
                continue

            current_column_id = int(card["column_id"])
            target_column_id = int(action.columnId)

            source_cards = conn.execute(
                "SELECT id FROM cards WHERE column_id = ? AND archived = 0 ORDER BY position",
                (current_column_id,),
            ).fetchall()
            source_ids = ordered_ids(source_cards)
            if int(action.cardId) in source_ids:
                source_ids.remove(int(action.cardId))

            target_cards = conn.execute(
                "SELECT id FROM cards WHERE column_id = ? AND archived = 0 ORDER BY position",
                (target_column_id,),
            ).fetchall()
            target_ids = ordered_ids(target_cards)

            insert_position = action.position
            if insert_position is None or insert_position > len(target_ids):
                insert_position = len(target_ids)
            if insert_position < 0:
                insert_position = 0

            target_ids.insert(insert_position, int(action.cardId))

            conn.execute(
                "UPDATE cards SET column_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (target_column_id, int(action.cardId)),
            )
            resequence_positions(conn, "cards", source_ids, "AND column_id = ?", (current_column_id,))
            resequence_positions(conn, "cards", target_ids, "AND column_id = ?", (target_column_id,))
            app_logger.info(f"Moved card {action.cardId} from column {current_column_id} to column {target_column_id}")
            continue

        if isinstance(action, DeleteCardAction):
            app_logger.debug(f"Deleting card {action.cardId}")
            card = conn.execute(
                """
                SELECT cards.id, cards.column_id
                FROM cards
                JOIN columns ON cards.column_id = columns.id
                WHERE cards.id = ? AND columns.board_id = ?
                """,
                (int(action.cardId), board_id),
            ).fetchone()
            if not card:
                app_logger.warning(f"Card {action.cardId} not found for board {board_id}")
                continue
            column_id = int(card["column_id"])
            conn.execute("DELETE FROM cards WHERE id = ?", (int(action.cardId),))
            remaining = conn.execute(
                "SELECT id FROM cards WHERE column_id = ? AND archived = 0 ORDER BY position",
                (column_id,),
            ).fetchall()
            resequence_positions(conn, "cards", ordered_ids(remaining), "AND column_id = ?", (column_id,))
            app_logger.info(f"Deleted card {action.cardId} from column {column_id}")

    conn.commit()
