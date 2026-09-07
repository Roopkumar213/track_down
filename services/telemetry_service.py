"""
services/telemetry_service.py - Parses and normalizes client device telemetry.
"""

import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class TelemetryService:
    @staticmethod
    def extract_client_ip(raw_ip: Optional[str]) -> str:
        """Extract first real client IP from comma-separated X-Forwarded-For header."""
        if not raw_ip:
            return "unknown"
        parts = [p.strip() for p in raw_ip.split(",") if p.strip()]
        return parts[0] if parts else "unknown"

    @staticmethod
    def guess_os_name(ua: str, platform: str) -> str:
        """Heuristic detection of operating system from User-Agent and platform."""
        ua = ua or ""
        platform = platform or ""
        if "Android" in ua:
            return "Android"
        if "iPhone" in ua or "iPad" in ua or "iPod" in ua or "iOS" in ua:
            return "iOS"
        if "Windows NT" in ua:
            return "Windows"
        if "Mac OS X" in ua or "Macintosh" in ua:
            return "macOS"
        if "Linux" in ua and "Android" not in ua:
            return "Linux"
        return platform or "Unknown OS"

    @staticmethod
    def guess_device_model(ua: str) -> Optional[str]:
        """Heuristic detection of Android device model string."""
        if not ua:
            return None
        m = re.search(r"Android [^;]*; ([^;/\)]+)", ua)
        if m:
            candidate = m.group(1).strip()
            # Clean up common substrings like 'Build/...'
            candidate = re.sub(r"\s+Build.*$", "", candidate)
            return candidate if candidate else None
        return None

    @classmethod
    def process_telemetry(cls, payload: Dict[str, Any], raw_ip: str) -> Dict[str, Any]:
        """Normalize raw incoming client payload into structured telemetry."""
        ip = cls.extract_client_ip(raw_ip)
        details = payload.get("details") or {}
        battery = payload.get("battery")
        coords = payload.get("coords")

        ua = details.get("userAgent", "") or ""
        platform = details.get("platform", "") or ""
        os_name = cls.guess_os_name(ua, platform)
        device_model = cls.guess_device_model(ua)

        # Battery normalization
        normalized_battery = None
        if isinstance(battery, dict) and battery.get("level") is not None:
            try:
                raw_lvl = float(battery["level"])
                # If represented as fraction 0.0 - 1.0, convert to percentage
                if 0.0 <= raw_lvl <= 1.0:
                    raw_lvl = raw_lvl * 100
                normalized_battery = {
                    "level": int(round(raw_lvl)),
                    "charging": bool(battery.get("charging", False))
                }
            except (ValueError, TypeError):
                pass

        # GPS Coordinates normalization
        normalized_coords = None
        if isinstance(coords, dict):
            lat = coords.get("lat")
            lon = coords.get("lon")
            acc = coords.get("acc") or coords.get("accuracy")
            if lat is not None and lon is not None:
                try:
                    normalized_coords = {
                        "lat": float(lat),
                        "lon": float(lon),
                        "acc": float(acc) if acc is not None else None
                    }
                except (ValueError, TypeError):
                    pass

        # Storage normalization
        storage = details.get("storage") or {}
        quota_b = storage.get("quotaBytes")
        usage_b = storage.get("usageBytes")
        quota_gb = round(quota_b / 1e9, 2) if quota_b else None
        usage_gb = round(usage_b / 1e9, 2) if usage_b else None

        # Screen
        scr = details.get("screen") or {}

        # Network
        net = details.get("network") or {}

        # Timezone
        tz = details.get("tz") or {}

        return {
            "ip": ip,
            "os": os_name,
            "device_model": device_model,
            "user_agent": ua,
            "cpu_cores": details.get("cpuCores"),
            "ram_gb": details.get("ramGB"),
            "storage": {
                "quota_gb": quota_gb,
                "usage_gb": usage_gb
            },
            "screen": {
                "width": scr.get("w"),
                "height": scr.get("h"),
                "ratio": scr.get("ratio", 1)
            },
            "network": {
                "type": net.get("type"),
                "downlink": net.get("downlink"),
                "rtt": net.get("rtt"),
                "save_data": net.get("saveData")
            },
            "timezone": {
                "zone": tz.get("zone"),
                "offset_minutes": tz.get("offset")
            },
            "languages": details.get("languages") or [],
            "battery": normalized_battery,
            "coords": normalized_coords,
            "permissions": details.get("permissions") or {}
        }
