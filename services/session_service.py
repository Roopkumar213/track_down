"""
services/session_service.py - Manages the lifecycle and configuration of tracking sessions.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import config
from storage.session_store import SessionStore

logger = logging.getLogger(__name__)


class SessionService:
    def __init__(self, store: SessionStore):
        self.store = store

    def create_session(
        self,
        experience: str = config.DEFAULT_EXPERIENCE,
        label: str = "",
        chat_id: str = "",
        target_url: str = "",
        expiration_hours: int = config.DEFAULT_EXPIRATION_HOURS
    ) -> Dict[str, Any]:
        """Create a new session with the specified experience and metadata."""
        token = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(hours=expiration_hours)).isoformat() if expiration_hours > 0 else None

        # Fallback to default experience if invalid
        if experience not in config.EXPERIENCES:
            logger.warning(f"Unknown experience '{experience}', falling back to default.")
            experience = config.DEFAULT_EXPERIENCE

        session_data = {
            "token": token,
            "label": label.strip(),
            "chat_id": str(chat_id) if chat_id else "",
            "experience": experience,
            "target_url": target_url.strip(),
            "status": "active",
            "created_at": now.isoformat(),
            "expires_at": expires_at,
            "events": [
                {
                    "event": "SESSION_CREATED",
                    "timestamp": now.isoformat(),
                    "metadata": {
                        "experience": experience,
                        "label": label
                    }
                }
            ],
            "visits": [],
            "telemetry": {},
            "permissions": {
                "camera": "NOT_REQUESTED",
                "location": "NOT_REQUESTED",
                "media": "NOT_REQUESTED"
            },
            "media": []
        }

        self.store.save(token, session_data)
        logger.info(f"Created session {token} [experience={experience}, chat_id={chat_id}]")
        return session_data

    def get_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve session by token with lazy expiration check."""
        session = self.store.get(token)
        if not session:
            return None

        # Check expiration
        expires_at = session.get("expires_at")
        if expires_at and session.get("status") == "active":
            now_iso = datetime.now(timezone.utc).isoformat()
            if expires_at < now_iso:
                session["status"] = "expired"
                self.store.save(token, session)
                logger.info(f"Session {token} has expired.")

        return session

    def validate_active_session(self, token: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Validate that a session exists and is currently active.
        Returns (is_valid, reason, session).
        """
        session = self.get_session(token)
        if not session:
            return False, "Session not found", None

        status = session.get("status", "active")
        if status == "stopped":
            return False, "Session has been stopped by administrator", session
        if status == "expired":
            return False, "Session has expired", session
        if status != "active":
            return False, f"Session is in '{status}' state", session

        return True, "ok", session

    def stop_session(self, token: str) -> Tuple[bool, str]:
        """Stop an active session."""
        session = self.get_session(token)
        if not session:
            return False, "Session not found"

        session["status"] = "stopped"
        session["events"].append({
            "event": "SESSION_STOPPED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": {}
        })
        self.store.save(token, session)
        logger.info(f"Session {token} stopped.")
        return True, "Session stopped successfully."

    def list_sessions(self, chat_id: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
        """List sessions, optionally filtered by chat_id."""
        all_sessions = self.store.list_all()
        if not chat_id:
            return all_sessions
        return {k: v for k, v in all_sessions.items() if str(v.get("chat_id")) == str(chat_id)}

    def record_permission_state(self, token: str, capability: str, state: str) -> bool:
        """Update permission state for capability (camera, location, media)."""
        valid_states = {"NOT_REQUESTED", "REQUESTED", "GRANTED", "DENIED", "UNAVAILABLE", "ERROR"}
        if state not in valid_states:
            logger.warning(f"Invalid permission state '{state}' for capability '{capability}'")
            return False

        session = self.get_session(token)
        if not session:
            return False

        session.setdefault("permissions", {})[capability] = state
        return self.store.save(token, session)
