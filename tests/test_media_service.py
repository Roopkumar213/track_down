"""
tests/test_media_service.py - Unit tests for MediaService magic bytes validation & security.
"""

import base64
import unittest
import tempfile
from pathlib import Path
import config
from services.media_service import MediaService


class TestMediaService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.orig_upload_dir = config.UPLOAD_DIR
        config.UPLOAD_DIR = Path(self.temp_dir.name)

    def tearDown(self):
        config.UPLOAD_DIR = self.orig_upload_dir
        self.temp_dir.cleanup()

    def test_valid_jpeg(self):
        # Valid minimal JPEG magic bytes
        jpeg_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb"
        b64 = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes).decode("ascii")

        ok, msg, filename = MediaService.save_base64_image("sess123", b64)
        self.assertTrue(ok)
        self.assertTrue(filename.endswith(".jpg"))
        self.assertTrue((config.UPLOAD_DIR / filename).exists())

    def test_valid_png(self):
        # Minimal PNG header: \x89PNG\r\n\x1a\n
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b64 = base64.b64encode(png_bytes).decode("ascii")

        ok, msg, filename = MediaService.save_base64_image("sess123", b64)
        self.assertTrue(ok)
        self.assertTrue(filename.endswith(".png"))

    def test_invalid_magic_bytes_executable(self):
        # Fake image that is actually an executable (starts with MZ)
        fake_bytes = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00"
        b64 = base64.b64encode(fake_bytes).decode("ascii")

        ok, msg, filename = MediaService.save_base64_image("sess123", b64)
        self.assertFalse(ok)
        self.assertIn("Disallowed", msg)
        self.assertIsNone(filename)

    def test_oversized_payload(self):
        # Construct JPEG larger than max limit
        huge_bytes = b"\xff\xd8\xff" + (b"\x00" * (1024 * 1024))
        b64 = base64.b64encode(huge_bytes).decode("ascii")

        # Set max_size to 500 KB
        ok, msg, filename = MediaService.save_base64_image("sess123", b64, max_size=500 * 1024)
        self.assertFalse(ok)
        self.assertIn("exceeds", msg)


if __name__ == "__main__":
    unittest.main()
