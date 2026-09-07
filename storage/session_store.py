"""
storage/session_store.py - Abstract Base Class for session storage.
Enables pluggable backends (JSON, SQLite, PostgreSQL).
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


class SessionStore(ABC):
    """Abstract interface for session persistence."""

    @abstractmethod
    def get(self, token: str) -> Optional[Dict[str, Any]]:
        """Retrieve a session by its token. Returns None if not found."""
        pass

    @abstractmethod
    def save(self, token: str, data: Dict[str, Any]) -> bool:
        """Create or update a session by token."""
        pass

    @abstractmethod
    def list_all(self) -> Dict[str, Dict[str, Any]]:
        """Return all sessions."""
        pass

    @abstractmethod
    def delete(self, token: str) -> bool:
        """Delete a session by token."""
        pass

    @abstractmethod
    def cleanup_expired(self) -> int:
        """Purge or mark expired sessions. Returns count of purged sessions."""
        pass
