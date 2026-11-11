"""
SQLite persistence layer for Colibri Studio.
Stores conversations, messages, model settings, and execution statistics.
"""

import sqlite3
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class StorageDatabase:
    def __init__(self, db_filepath: Optional[str] = None):
        self.is_memory = db_filepath == ":memory:"
        self._memory_conn = None

        if self.is_memory:
            self.db_path = None
        elif db_filepath:
            self.db_path = Path(db_filepath)
        else:
            base_dir = Path(__file__).parent.parent
            self.db_path = base_dir / "storage" / "studio.db"

        if self.db_path:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self.is_memory:
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:")
                self._memory_conn.row_factory = sqlite3.Row
            return self._memory_conn
        else:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                model_id TEXT,
                system_prompt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                settings TEXT
            )
        """)
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metrics TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        if not self.is_memory:
            conn.close()

    def create_conversation(self, title: str = "New Conversation", model_id: str = "", system_prompt: str = "", settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        settings_str = json.dumps(settings or {})

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (id, title, model_id, system_prompt, created_at, updated_at, settings) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (conv_id, title, model_id, system_prompt, now, now, settings_str)
        )
        conn.commit()
        if not self.is_memory:
            conn.close()

        return self.get_conversation(conv_id)

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
        row = cursor.fetchone()
        if not row:
            if not self.is_memory:
                conn.close()
            return None

        conv = dict(row)
        if not self.is_memory:
            conn.close()

        conv["settings"] = json.loads(conv["settings"]) if conv.get("settings") else {}
        conv["messages"] = self.get_messages(conv_id)
        return conv

    def list_conversations(self) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM conversations ORDER BY updated_at DESC")
        rows = cursor.fetchall()
        results = []
        for r in rows:
            c = dict(r)
            c["settings"] = json.loads(c["settings"]) if c.get("settings") else {}
            results.append(c)
        if not self.is_memory:
            conn.close()
        return results

    def update_conversation(self, conv_id: str, title: Optional[str] = None, system_prompt: Optional[str] = None, settings: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        now = datetime.now(timezone.utc).isoformat()
        updates = ["updated_at = ?"]
        params = [now]

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if system_prompt is not None:
            updates.append("system_prompt = ?")
            params.append(system_prompt)
        if settings is not None:
            updates.append("settings = ?")
            params.append(json.dumps(settings))

        params.append(conv_id)

        conn = self._get_connection()
        cursor = conn.cursor()
        query = f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, params)
        conn.commit()
        if not self.is_memory:
            conn.close()

        return self.get_conversation(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        conn.commit()
        count = cursor.rowcount
        if not self.is_memory:
            conn.close()
        return count > 0

    def add_message(self, conversation_id: str, role: str, content: str, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        metrics_str = json.dumps(metrics or {})

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at, metrics) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, conversation_id, role, content, now, metrics_str)
        )
        cursor.execute("UPDATE conversations SET updated_at = ? WHERE id = ?", (now, conversation_id))
        conn.commit()
        if not self.is_memory:
            conn.close()

        return {
            "id": msg_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "created_at": now,
            "metrics": metrics or {}
        }

    def update_message(self, message_id: str, content: str) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE messages SET content = ? WHERE id = ?", (content, message_id))
        conn.commit()
        count = cursor.rowcount
        if not self.is_memory:
            conn.close()
        return count > 0

    def delete_messages_after(self, conversation_id: str, created_at: str) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE conversation_id = ? AND created_at >= ?", (conversation_id, created_at))
        conn.commit()
        if not self.is_memory:
            conn.close()

    def get_messages(self, conversation_id: str) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC", (conversation_id,))
        rows = cursor.fetchall()
        messages = []
        for r in rows:
            m = dict(r)
            m["metrics"] = json.loads(m["metrics"]) if m.get("metrics") else {}
            messages.append(m)
        if not self.is_memory:
            conn.close()
        return messages
