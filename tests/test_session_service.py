"""
tests/test_session_service.py - Unit tests for SessionService lifecycle and validation.
"""

import unittest
import tempfile
from pathlib import Path
from storage.json_store import JsonSessionStore
from services.session_service import SessionService


class TestSessionService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_dir.name) / "test_sessions.json"
        self.store = JsonSessionStore(self.file_path)
        self.service = SessionService(self.store)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_create_session(self):
        session = self.service.create_session(
            experience="tictactoe",
            label="Match 1",
            chat_id="123456"
        )
        token = session["token"]
        self.assertTrue(len(token) > 10)
        self.assertEqual(session["experience"], "tictactoe")
        self.assertEqual(session["label"], "Match 1")
        self.assertEqual(session["status"], "active")

        # Validate active session
        valid, reason, retrieved = self.service.validate_active_session(token)
        self.assertTrue(valid)
        self.assertEqual(reason, "ok")
        self.assertEqual(retrieved["token"], token)

    def test_stop_session(self):
        session = self.service.create_session(experience="reaction_game")
        token = session["token"]

        ok, msg = self.service.stop_session(token)
        self.assertTrue(ok)

        valid, reason, _ = self.service.validate_active_session(token)
        self.assertFalse(valid)
        self.assertIn("stopped", reason)

    def test_invalid_token(self):
        valid, reason, sess = self.service.validate_active_session("nonexistent_token")
        self.assertFalse(valid)
        self.assertEqual(reason, "Session not found")
        self.assertIsNone(sess)


if __name__ == "__main__":
    unittest.main()
