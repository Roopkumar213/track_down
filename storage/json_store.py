"""
storage/json_store.py - Thread-safe, atomic JSON-based session storage.
"""

import os
import json
import logging
import threading
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from .session_store import SessionStore

logger = logging.getLogger(__name__)


class JsonSessionStore(SessionStore):
    """
    Thread-safe session store that persists sessions to a JSON file.
    Uses atomic file replacement to prevent corruption from abrupt stops.
    """

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self._lock = threading.RLock()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load_from_disk()

    def _normalize_session_schema(self, token: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure session has all required fields according to current schema."""
        now_iso = datetime.now(timezone.utc).isoformat()
        normalized = dict(data)
        normalized.setdefault("token", token)
        normalized.setdefault("label", "")
        normalized.setdefault("chat_id", "")
        normalized.setdefault("experience", "wrapped_website" if normalized.get("wrap") else "reaction_game")
        normalized.setdefault("target_url", normalized.get("target_url", ""))
        normalized.setdefault("status", "active")
        normalized.setdefault("created_at", now_iso)
        normalized.setdefault("expires_at", None)
        normalized.setdefault("events", [])
        normalized.setdefault("visits", normalized.get("visits", []))
        normalized.setdefault("telemetry", {})
        normalized.setdefault("permissions", {
            "camera": "NOT_REQUESTED",
            "location": "NOT_REQUESTED",
            "media": "NOT_REQUESTED"
        })
        normalized.setdefault("media", normalized.get("files", []))
        return normalized

    def _load_from_disk(self) -> None:
        """Load sessions from disk with legacy migration and error recovery."""
        with self._lock:
            if not self.file_path.exists():
                self._cache = {}
                self._write_to_disk_atomic()
                return

            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    if not isinstance(raw, dict):
                        logger.warning("Session file content was not a dict, resetting.")
                        raw = {}
                    # Normalize each session
                    self._cache = {
                        token: self._normalize_session_schema(token, sess)
                        for token, sess in raw.items()
                        if isinstance(sess, dict)
                    }
            except Exception as e:
                logger.error(f"Failed to load sessions from {self.file_path}: {e}")
                # Create backup of corrupted file
                backup_path = self.file_path.with_suffix(f".corrupt.{int(datetime.now().timestamp())}.json")
                try:
                    os.replace(self.file_path, backup_path)
                    logger.info(f"Backed up corrupted session file to {backup_path}")
                except Exception as bkp_err:
                    logger.error(f"Failed to backup corrupted session file: {bkp_err}")
                self._cache = {}

    def _write_to_disk_atomic(self) -> bool:
        """Atomically write self._cache to disk using a temporary file."""
        with self._lock:
            parent_dir = self.file_path.parent
            os.makedirs(parent_dir, exist_ok=True)
            
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=str(parent_dir),
                    delete=False,
                    encoding="utf-8",
                    suffix=".tmp"
                ) as tf:
                    temp_file = tf.name
                    json.dump(self._cache, tf, indent=2, ensure_ascii=False)
                    tf.flush()
                    os.fsync(tf.fileno())

                # Windows / OneDrive file lock resilience: retry replace up to 5 times
                replaced = False
                for attempt in range(5):
                    try:
                        os.replace(temp_file, str(self.file_path))
                        replaced = True
                        break
                    except (PermissionError, OSError):
                        import time
                        time.sleep(0.03 * (attempt + 1))

                if not replaced:
                    # If external locking process (e.g. OneDrive) persists, write directly
                    with open(self.file_path, "w", encoding="utf-8") as f:
                        json.dump(self._cache, f, indent=2, ensure_ascii=False)
                    try:
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                    except Exception:
                        pass

                return True
            except Exception as e:
                logger.error(f"Failed to write sessions: {e}")
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass
                return False

    def get(self, token: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            session = self._cache.get(token)
            if not session:
                return None
            return dict(session)

    def save(self, token: str, data: Dict[str, Any]) -> bool:
        with self._lock:
            normalized = self._normalize_session_schema(token, data)
            self._cache[token] = normalized
            return self._write_to_disk_atomic()

    def list_all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {k: dict(v) for k, v in self._cache.items()}

    def delete(self, token: str) -> bool:
        with self._lock:
            if token in self._cache:
                del self._cache[token]
                return self._write_to_disk_atomic()
            return False

    def cleanup_expired(self) -> int:
        with self._lock:
            now_iso = datetime.now(timezone.utc).isoformat()
            changed = False
            count = 0
            for token, session in self._cache.items():
                expires_at = session.get("expires_at")
                if expires_at and expires_at < now_iso and session.get("status") == "active":
                    session["status"] = "expired"
                    changed = True
                    count += 1
            if changed:
                self._write_to_disk_atomic()
            return count
