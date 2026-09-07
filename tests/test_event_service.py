"""
tests/test_event_service.py - Tests structured event logging and permission state synchronization.
"""

import unittest
import tempfile
from pathlib import Path
from storage.json_store import JsonSessionStore
from services.session_service import SessionService
from services.event_service import EventService


class TestEventService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_dir.name) / "test_sessions.json"
        self.store = JsonSessionStore(self.file_path)
        self.session_service = SessionService(self.store)
        self.event_service = EventService(self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_log_event(self):
        sess = self.session_service.create_session(experience="reaction_game")
        token = sess["token"]

        self.assertTrue(self.event_service.log_event(token, "GAME_STARTED", {"game": "reaction"}))

        updated = self.session_service.get_session(token)
        events = updated.get("events", [])
        self.assertTrue(any(e["event"] == "GAME_STARTED" for e in events))

    def test_permission_state_synchronization(self):
        sess = self.session_service.create_session(experience="reaction_game")
        token = sess["token"]

        self.event_service.log_event(token, "CAMERA_PERMISSION_GRANTED")
        self.event_service.log_event(token, "LOCATION_PERMISSION_DENIED")

        updated = self.session_service.get_session(token)
        perms = updated.get("permissions", {})
        self.assertEqual(perms.get("camera"), "GRANTED")
        self.assertEqual(perms.get("location"), "DENIED")


if __name__ == "__main__":
    unittest.main()
