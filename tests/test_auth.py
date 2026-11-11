import os
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse, parse_qs

os.environ.setdefault("NEXPLAY_AUTH_SECRET", "unit-test-only-" + "x" * 40)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app import app, PUBLIC_BASE_URL, STEAM_OPENID


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_health(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["status"], "ok")

    def test_status_does_not_expose_secrets(self):
        res = self.client.get("/api/status")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json["steam_openid"])
        self.assertFalse(res.json["cloud_streaming"])
        self.assertNotIn("secret", repr(res.json).lower())

    def test_steam_requires_valid_token(self):
        res = self.client.get("/api/steam/me")
        self.assertEqual(res.status_code, 401)
        res2 = self.client.get("/api/steam/library", headers={"Authorization": "Bearer fake"})
        self.assertEqual(res2.status_code, 401)

    def test_epic_requires_valid_token(self):
        self.assertEqual(self.client.get("/api/epic/me").status_code, 401)

    def test_cors_is_restricted(self):
        res = self.client.get("/api/status", headers={"Origin": "https://evil.example"})
        self.assertNotIn("Access-Control-Allow-Origin", res.headers)
        res2 = self.client.get("/api/status", headers={"Origin": "https://nexplay-cloud.onrender.com"})
        self.assertEqual(res2.headers.get("Access-Control-Allow-Origin"), "https://nexplay-cloud.onrender.com")

    def test_steam_login_has_csrf_cookie(self):
        res = self.client.get("/auth/steam/start")
        self.assertEqual(res.status_code, 302)
        self.assertTrue(res.location.startswith(STEAM_OPENID))
        q = parse_qs(urlparse(res.location).query)
        self.assertEqual(q["openid.realm"][0], PUBLIC_BASE_URL + "/")
        self.assertIn("nx_steam_state", res.headers.get("Set-Cookie", ""))
        self.assertIn("HttpOnly", res.headers.get("Set-Cookie", ""))

    def test_bad_steam_callback_rejected(self):
        res = self.client.get("/auth/steam/callback?state=invalid")
        self.assertEqual(res.status_code, 302)
        self.assertIn("nexplay_error=steam_invalid_state", res.location)

if __name__ == "__main__":
    unittest.main()
