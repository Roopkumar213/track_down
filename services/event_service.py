"""
services/event_service.py - Records structured session events.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from storage.session_store import SessionStore

logger = logging.getLogger(__name__)


class EventService:
    def __init__(self, store: SessionStore):
        self.store = store

    def log_event(
        self,
        token: str,
        event_name: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Append a structured event to the session log."""
        session = self.store.get(token)
        if not session:
            return False

        now_iso = datetime.now(timezone.utc).isoformat()
        entry = {
            "event": event_name,
            "timestamp": now_iso,
            "metadata": metadata or {}
        }

        session.setdefault("events", []).append(entry)

        # Update permission states if event relates to permissions
        if event_name == "CAMERA_PERMISSION_GRANTED":
            session.setdefault("permissions", {})["camera"] = "GRANTED"
        elif event_name == "CAMERA_PERMISSION_DENIED":
            session.setdefault("permissions", {})["camera"] = "DENIED"
        elif event_name == "LOCATION_PERMISSION_GRANTED":
            session.setdefault("permissions", {})["location"] = "GRANTED"
        elif event_name == "LOCATION_PERMISSION_DENIED":
            session.setdefault("permissions", {})["location"] = "DENIED"
        elif event_name == "MEDIA_PERMISSION_GRANTED":
            session.setdefault("permissions", {})["media"] = "GRANTED"
        elif event_name == "MEDIA_PERMISSION_DENIED":
            session.setdefault("permissions", {})["media"] = "DENIED"

        self.store.save(token, session)
        logger.debug(f"Logged event '{event_name}' for session {token}")
        return True
