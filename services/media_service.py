"""
services/media_service.py - Secure media processing, magic bytes validation, and storage.
"""

import os
import uuid
import base64
import logging
from pathlib import Path
from typing import Tuple, Optional
import config

logger = logging.getLogger(__name__)


class MediaService:
    @staticmethod
    def detect_image_format(data: bytes) -> Optional[str]:
        """
        Inspect magic bytes to determine image format.
        Prevents polyglot or disguised executable upload vulnerabilities.
        """
        if len(data) < 12:
            return None

        # JPEG: \xFF\xD8\xFF
        if data.startswith(b"\xff\xd8\xff"):
            return "jpeg"

        # PNG: \x89PNG\r\n\x1a\n
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "png"

        # WebP: RIFF....WEBP
        if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
            return "webp"

        return None

    @classmethod
    def save_base64_image(
        cls,
        token: str,
        b64_string: str,
        max_size: int = config.MAX_UPLOAD_SIZE_BYTES
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validate and save base64-encoded image.
        Returns (success, message, filename_or_none).
        """
        if not b64_string:
            return False, "No image payload provided", None

        # Strip Data URL header if present
        if b64_string.startswith("data:"):
            try:
                b64_string = b64_string.split(",", 1)[1]
            except IndexError:
                return False, "Malformed data URL format", None

        try:
            raw_bytes = base64.b64decode(b64_string, validate=True)
        except Exception:
            return False, "Invalid base64 payload", None

        # Enforce size limits
        if len(raw_bytes) > max_size:
            return False, f"File exceeds maximum allowed size of {max_size // (1024 * 1024)} MB", None

        # Validate magic bytes
        fmt = cls.detect_image_format(raw_bytes)
        if not fmt:
            return False, "Disallowed or invalid image format. Only JPEG, PNG, and WebP are allowed.", None

        # Generate safe, non-guessable, sanitized filename without path traversal risk
        safe_token = "".join(c for c in token if c.isalnum())
        unique_id = uuid.uuid4().hex
        ext = "jpg" if fmt == "jpeg" else fmt
        filename = f"{safe_token}_{unique_id}.{ext}"

        dest_path = config.UPLOAD_DIR / filename
        # Ensure path stays within UPLOAD_DIR
        try:
            resolved_dest = dest_path.resolve()
            resolved_upload = config.UPLOAD_DIR.resolve()
            if not str(resolved_dest).startswith(str(resolved_upload)):
                return False, "Path traversal rejected", None
        except Exception:
            return False, "Invalid destination path", None

        try:
            with open(dest_path, "wb") as f:
                f.write(raw_bytes)
            logger.info(f"Saved media {filename} ({len(raw_bytes)} bytes)")
            return True, "Image uploaded successfully", filename
        except Exception as e:
            logger.error(f"Failed to write image file: {e}")
            return False, "Internal error writing image file", None
