"""
tests/test_api_routes.py - Integration tests for Flask endpoints and experience rendering.
"""

import unittest
import json
import tempfile
from pathlib import Path
import config
from storage.json_store import JsonSessionStore
from services.session_service import SessionService
from server import app, session_service as global_session_service


class TestApiRoutes(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()

    def test_index_route(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["status"], "online")
        self.assertTrue(data["available_experiences"] >= 14)

    def test_session_lifecycle_and_experience_render(self):
        # Create session with reaction_game
        sess = global_session_service.create_session(experience="reaction_game", label="UnitTest")
        token = sess["token"]

        # GET /s/<token>
        resp = self.client.get(f"/s/{token}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Reaction Time", resp.data)

        # GET /session_config/<token>
        cfg_resp = self.client.get(f"/session_config/{token}")
        self.assertEqual(cfg_resp.status_code, 200)
        cfg_data = cfg_resp.get_json()
        self.assertEqual(cfg_data["experience"], "reaction_game")
        self.assertEqual(cfg_data["status"], "active")

        # POST /upload_info/<token>
        info_resp = self.client.post(
            f"/upload_info/{token}",
            json={
                "battery": {"level": 0.9, "charging": False},
                "details": {"cpuCores": 4}
            }
        )
        self.assertEqual(info_resp.status_code, 200)

        # POST /event/<token>
        event_resp = self.client.post(
            f"/event/{token}",
            json={"event": "TEST_EVENT", "metadata": {"foo": "bar"}}
        )
        self.assertEqual(event_resp.status_code, 200)

        # Stop session
        global_session_service.stop_session(token)

        # Subsequent visit should be rejected with 403
        stopped_resp = self.client.get(f"/s/{token}")
        self.assertEqual(stopped_resp.status_code, 403)

    def test_nonexistent_session(self):
        resp = self.client.get("/s/non_existent_token_999")
        self.assertEqual(resp.status_code, 404)

    def test_wrapper_experience(self):
        sess = global_session_service.create_session(
            experience="wrapped_website",
            target_url="https://example.com"
        )
        token = sess["token"]

        resp = self.client.get(f"/w/{token}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"https://example.com", resp.data)
        self.assertIn(b"siteFrame", resp.data)


    def test_all_14_experiences_render(self):
        """Verify that each of the 14 supported experiences renders cleanly without Jinja template errors."""
        for exp_id, meta in config.EXPERIENCES.items():
            sess = global_session_service.create_session(
                experience=exp_id,
                target_url="https://example.com" if exp_id == "wrapped_website" else ""
            )
            token = sess["token"]
            url = f"/w/{token}" if exp_id == "wrapped_website" else f"/s/{token}"
            resp = self.client.get(url)
            self.assertEqual(
                resp.status_code,
                200,
                f"Experience '{exp_id}' failed to render. Status: {resp.status_code}"
            )
            if exp_id != "wrapped_website":
                import html
                self.assertIn(html.escape(meta["name"]).encode("utf-8"), resp.data)


if __name__ == "__main__":
    unittest.main()
