import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "data", "chat_history.db")
)

class ChatStorage:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize the database schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Create conversations table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT,
                preview TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                messages TEXT, -- JSON array of messages
                analysis TEXT, -- JSON object for analysis data
                summary TEXT, -- JSON object for structured summary (topic + points)
                archived BOOLEAN DEFAULT 0
            )
        ''')
        
        # Migration: Add summary column if not exists
        try:
            cursor.execute('ALTER TABLE conversations ADD COLUMN summary TEXT')
        except sqlite3.OperationalError:
            pass # Column likely exists
        
        conn.commit()
        conn.close()

    def save_conversation(self, conversation_id: str, title: str, preview: str, messages: List[Dict], analysis: Optional[Dict], summary: Optional[Dict] = None):
        """Save or update a conversation with comprehensive logging and verification."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            logger.info(f"[SAVE_START] conversation_id: {conversation_id}")
            
            # Validate inputs
            if not conversation_id:
                raise ValueError("conversation_id is required")
            if not title:
                title = "محادثة جديدة"
            
            logger.debug(f"[SAVE_VALIDATE] Inputs valid - title: {title[:30]}..., messages: {len(messages)}")
            
            now = datetime.now().isoformat()
            messages_json = json.dumps(messages, ensure_ascii=False)
            analysis_json = json.dumps(analysis, ensure_ascii=False) if analysis else None
            summary_json = json.dumps(summary, ensure_ascii=False) if summary else None
            
            logger.debug(f"[SAVE_SERIALIZE] Messages serialized ({len(messages_json)} bytes), Analysis: {bool(analysis)}")
            
            # Execute insert
            cursor.execute('''
                INSERT INTO conversations (id, title, preview, updated_at, messages, analysis, summary)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    preview = excluded.preview,
                    updated_at = excluded.updated_at,
                    messages = excluded.messages,
                    analysis = excluded.analysis,
                    summary = excluded.summary
            ''', (conversation_id, title, preview, now, messages_json, analysis_json, summary_json))
            
            logger.debug(f"[SAVE_EXECUTE] SQL executed, changes: {cursor.rowcount}")
            
            # Commit transaction
            conn.commit()
            logger.debug(f"[SAVE_COMMIT] Transaction committed")
            
            # Verify the save was successful by loading back
            cursor.execute('SELECT id, title FROM conversations WHERE id = ?', (conversation_id,))
            row = cursor.fetchone()
            
            if row:
                logger.info(f"[SAVE_VERIFIED] conversation_id: {conversation_id}, title: {row[1]}")
                return True
            else:
                logger.error(f"[SAVE_VERIFY_FAILED] conversation_id not found after save")
                return False
                
        except Exception as e:
            logger.error(f"[SAVE_ERROR] Failed to save conversation {conversation_id}: {e}", exc_info=True)
            return False
        finally:
            conn.close()

    def get_all_conversations(self, limit: int = 50, offset: int = 0) -> List[Dict]:
        """Get list of conversations (metadata only) for sidebar with logging."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            logger.debug(f"[GET_ALL_START] Fetching conversations - limit: {limit}, offset: {offset}")
            
            cursor.execute('''
                SELECT id, title, preview, updated_at, archived, summary 
                FROM conversations 
                WHERE archived = 0
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            
            rows = cursor.fetchall()
            logger.debug(f"[GET_ALL_RESULT] Retrieved {len(rows)} conversations")
            
            result = []
            for row in rows:
                result.append({
                    "id": row[0],
                    "title": row[1],
                    "preview": row[2],
                    "updated_at": row[3],
                    "timestamp": row[3],
                    "archived": bool(row[4]),
                    "summary": json.loads(row[5]) if row[5] else None
                })
            
            logger.info(f"[GET_ALL_SUCCESS] Retrieved {len(result)} conversations")
            return result
        except Exception as e:
            logger.error(f"[GET_ALL_ERROR] Failed to fetch conversations: {e}", exc_info=True)
            return []
        finally:
            conn.close()

    def get_conversation(self, conversation_id: str) -> Optional[Dict]:
        """Get full conversation details with logging."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            logger.debug(f"[GET_CONV_START] Fetching conversation: {conversation_id}")
            
            cursor.execute('SELECT id, title, messages, analysis FROM conversations WHERE id = ?', (conversation_id,))
            row = cursor.fetchone()
            
            if row:
                result = {
                    "id": row[0],
                    "title": row[1],
                    "messages": json.loads(row[2]) if row[2] else [],
                    "analysis": json.loads(row[3]) if row[3] else None
                }
                logger.info(f"[GET_CONV_SUCCESS] Retrieved conversation {conversation_id}, messages: {len(result['messages'])}")
                return result
            else:
                logger.warning(f"[GET_CONV_NOTFOUND] conversation_id not found: {conversation_id}")
                return None
        except Exception as e:
            logger.error(f"[GET_CONV_ERROR] Failed to fetch conversation {conversation_id}: {e}", exc_info=True)
            return None
        finally:
            conn.close()

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM conversations WHERE id = ?', (conversation_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            return False
        finally:
            conn.close()

    def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a conversation (soft delete)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute('UPDATE conversations SET archived = 1 WHERE id = ?', (conversation_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to archive conversation {conversation_id}: {e}")
            return False
        finally:
            conn.close()

    def clear_all(self) -> bool:
        """Permanently delete all non-archived conversations."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute('DELETE FROM conversations WHERE archived = 0')
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Failed to clear history: {e}")
            return False
        finally:
            conn.close()
