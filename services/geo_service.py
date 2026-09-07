"""
services/geo_service.py - Resilient IP Geolocation and GPS Reverse Geocoding.
"""

import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class GeoService:
    _geoip_cache: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def lookup_ip(cls, ip: str) -> Optional[Dict[str, Any]]:
        """
        Query ipapi.co for GeoIP info with internal memory cache.
        Returns parsed dict or None on any failure.
        """
        if not ip or ip in ("unknown", "127.0.0.1", "localhost", "::1"):
            return None

        if ip in cls._geoip_cache:
            return cls._geoip_cache[ip]

        try:
            resp = requests.get(
                f"https://ipapi.co/{ip}/json/",
                headers={"User-Agent": "device-telemetry-server/2.0"},
                timeout=3.0
            )
            if resp.ok:
                data = resp.json()
                if not data.get("error"):
                    result = {
                        "city": data.get("city") or "Unknown",
                        "region": data.get("region") or data.get("region_code") or "Unknown",
                        "country": data.get("country_name") or data.get("country") or "Unknown",
                        "isp": data.get("org") or data.get("asn") or "Unknown",
                        "latitude": data.get("latitude"),
                        "longitude": data.get("longitude")
                    }
                    cls._geoip_cache[ip] = result
                    return result
            logger.warning(f"GeoIP response non-ok for {ip}: status {resp.status_code}")
        except Exception as e:
            logger.warning(f"GeoIP lookup failed for {ip}: {e}")

        return None

    @classmethod
    def reverse_geocode(cls, lat: float, lon: float) -> Optional[str]:
        """
        Query OpenStreetMap Nominatim for street address from GPS coordinates.
        Returns human-readable address string or None.
        """
        try:
            resp = requests.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={"lat": lat, "lon": lon, "format": "jsonv2"},
                headers={"User-Agent": "device-telemetry-server/2.0 (contact: admin@local.test)"},
                timeout=3.0
            )
            if resp.ok:
                data = resp.json()
                return data.get("display_name")
            logger.warning(f"Reverse geocoding non-ok: status {resp.status_code}")
        except Exception as e:
            logger.warning(f"Reverse geocoding error: {e}")

        return None
