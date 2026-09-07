"""
tests/test_telemetry_service.py - Unit tests for TelemetryService parsing and detection.
"""

import unittest
from services.telemetry_service import TelemetryService


class TestTelemetryService(unittest.TestCase):
    def test_extract_client_ip(self):
        self.assertEqual(
            TelemetryService.extract_client_ip("203.0.113.195, 70.41.3.18, 150.172.238.178"),
            "203.0.113.195"
        )
        self.assertEqual(TelemetryService.extract_client_ip("192.168.1.5"), "192.168.1.5")
        self.assertEqual(TelemetryService.extract_client_ip(None), "unknown")

    def test_guess_os_name(self):
        android_ua = "Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 Chrome/112.0 Mobile Safari/537.36"
        ios_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1"
        win_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/114.0 Safari/537.36"

        self.assertEqual(TelemetryService.guess_os_name(android_ua, "Linux armv8l"), "Android")
        self.assertEqual(TelemetryService.guess_os_name(ios_ua, "iPhone"), "iOS")
        self.assertEqual(TelemetryService.guess_os_name(win_ua, "Win32"), "Windows")

    def test_guess_device_model(self):
        android_ua = "Mozilla/5.0 (Linux; Android 12; Pixel 6 Build/SD2A.220105.001.A1) AppleWebKit/537.36"
        model = TelemetryService.guess_device_model(android_ua)
        self.assertIn("Pixel 6", model)

    def test_process_telemetry(self):
        payload = {
            "battery": {"level": 0.854, "charging": True},
            "coords": {"lat": 37.7749, "lon": -122.4194, "accuracy": 15},
            "details": {
                "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                "cpuCores": 8,
                "ramGB": 16,
                "screen": {"w": 1920, "h": 1080, "ratio": 1}
            }
        }
        res = TelemetryService.process_telemetry(payload, "198.51.100.42")
        self.assertEqual(res["ip"], "198.51.100.42")
        self.assertEqual(res["battery"]["level"], 85)
        self.assertTrue(res["battery"]["charging"])
        self.assertEqual(res["coords"]["lat"], 37.7749)
        self.assertEqual(res["cpu_cores"], 8)
        self.assertEqual(res["os"], "Windows")


if __name__ == "__main__":
    unittest.main()
