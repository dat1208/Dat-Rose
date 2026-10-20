#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""API: routes, JSON shape and loopback-origin guard."""

import json
import unittest
import urllib.error
import urllib.request

from api import ApiContext, ApiServer


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Port 0 lets the OS pick a free port, so tests never collide.
        cls.server = ApiServer(ApiContext(), port=0)
        cls.server.start()
        cls.base = f"http://127.0.0.1:{cls.server.port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.stop()

    def _get(self, path, origin=None):
        request = urllib.request.Request(self.base + path)
        if origin:
            request.add_header("Origin", origin)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    def test_status_reports_app(self):
        status, data = self._get("/api/status")
        self.assertEqual(status, 200)
        self.assertEqual(data["app"], "D-Changer")
        self.assertFalse(data["engine_ready"])

    def test_unknown_route_404(self):
        status, _ = self._get("/api/nope")
        self.assertEqual(status, 404)

    def test_non_loopback_origin_blocked(self):
        status, data = self._get("/api/status", origin="https://evil.example")
        self.assertEqual(status, 403)
        self.assertIn("error", data)

    def test_loopback_origin_allowed(self):
        status, _ = self._get("/api/status", origin="http://localhost:1420")
        self.assertEqual(status, 200)

    def test_profiles_route_lists(self):
        status, data = self._get("/api/profiles")
        self.assertEqual(status, 200)
        self.assertIn("profiles", data)

    def test_account_without_engine_is_empty(self):
        status, data = self._get("/api/account")
        self.assertEqual(status, 200)
        self.assertIsNone(data["puuid"])
        self.assertIsNone(data["name"])

    def test_diagnostics_route(self):
        status, data = self._get("/api/diagnostics")
        self.assertEqual(status, 200)
        self.assertIn("issues", data)
        self.assertIsInstance(data["issues"], list)

    def test_options_preflight_allowed(self):
        request = urllib.request.Request(self.base + "/api/profiles/save", method="OPTIONS")
        request.add_header("Origin", "http://localhost:1420")
        request.add_header("Access-Control-Request-Method", "POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 204)
            self.assertEqual(response.headers["Access-Control-Allow-Origin"], "http://localhost:1420")
            self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])

    def test_shutdown_without_state_reports_not_stopping(self):
        request = urllib.request.Request(
            self.base + "/api/shutdown",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            data = json.loads(response.read().decode("utf-8"))
        self.assertFalse(data["stopping"])

    def test_shutdown_sets_state_stop(self):
        class FakeState:
            stop = False

        state = FakeState()
        server = ApiServer(ApiContext(state=state), port=0)
        server.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.port}/api/shutdown",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            self.assertTrue(data["stopping"])
            self.assertTrue(state.stop)
        finally:
            server.stop()


if __name__ == "__main__":
    unittest.main()
