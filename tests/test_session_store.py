"""
tests/test_session_store.py - Unit tests for JsonSessionStore with concurrency checks.
"""

import os
import unittest
import tempfile
import threading
from pathlib import Path
from storage.json_store import JsonSessionStore


class TestJsonSessionStore(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.file_path = Path(self.temp_dir.name) / "test_sessions.json"
        self.store = JsonSessionStore(self.file_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_save_and_get(self):
        data = {
            "label": "Test Session",
            "experience": "reaction_game",
            "status": "active"
        }
        self.assertTrue(self.store.save("token123", data))
        loaded = self.store.get("token123")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["label"], "Test Session")
        self.assertEqual(loaded["experience"], "reaction_game")
        self.assertEqual(loaded["status"], "active")
        # Ensure schema normalization occurred
        self.assertIn("permissions", loaded)
        self.assertIn("events", loaded)

    def test_delete(self):
        self.store.save("token1", {"label": "One"})
        self.assertTrue(self.store.delete("token1"))
        self.assertIsNone(self.store.get("token1"))

    def test_concurrent_writes(self):
        """Verify atomic writes withstand high concurrent thread access."""
        def worker(worker_id):
            for i in range(10):
                token = f"worker_{worker_id}_token_{i}"
                self.store.save(token, {"worker": worker_id, "idx": i})

        threads = []
        for w in range(5):
            t = threading.Thread(target=worker, args=(w,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        all_sessions = self.store.list_all()
        self.assertEqual(len(all_sessions), 50)


if __name__ == "__main__":
    unittest.main()
