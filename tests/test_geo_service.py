"""
tests/test_geo_service.py - Tests error isolation and resilience of GeoService.
"""

import unittest
from services.geo_service import GeoService


class TestGeoService(unittest.TestCase):
    def test_localhost_ip_returns_none(self):
        # Localhost should not trigger external queries
        self.assertIsNone(GeoService.lookup_ip("127.0.0.1"))
        self.assertIsNone(GeoService.lookup_ip("localhost"))
        self.assertIsNone(GeoService.lookup_ip("::1"))
        self.assertIsNone(GeoService.lookup_ip(""))

    def test_geo_service_error_isolation(self):
        # Querying an invalid or unreachable IP should return None without crashing
        res = GeoService.lookup_ip("240.0.0.1")  # Reserved IP space
        self.assertTrue(res is None or isinstance(res, dict))

    def test_reverse_geocode_graceful_handling(self):
        # Invalid coordinates should return None without throwing unhandled exceptions
        res = GeoService.reverse_geocode(999.0, 999.0)
        self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()
