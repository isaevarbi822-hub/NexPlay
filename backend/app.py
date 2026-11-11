"""NEXPLAY official Steam OpenID and Epic Account Services OAuth bridge.
No game streaming, purchases, password collection or unapproved entitlement access.
"""
import base64
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode

import requests
from flask import Flask, jsonify, make_response, redirect, request
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

app = Flask(__name__)
SITE_URL = os.getenv("SITE_URL", "https://nexplay-cloud.onrender.com").rstrip("/")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://nexplay-accounts.onrender.com").rstrip("/")
SECRET = os.getenv("NEXPLAY_AUTH_SECRET", "")
STEAM_API_KEY = os.getenv("STEAM_WEB_API_KEY", "").strip()
EPIC_CLIENT_ID = os.getenv("EPIC_CLIENT_ID", "").strip()
EPIC_CLIENT_SECRET = os.getenv("EPIC_CLIENT_SECRET", "").strip()
EPIC_DEPLOYMENT_ID = os.getenv("EPIC_DEPLOYMENT_ID", "").strip()
STEAM_OPENID = "https://steamcommunity.com/openid/login"
if not SECRET or len(SECRET) < 32:
    raise RuntimeError("Set NEXPLAY_AUTH_SECRET to a strong persistent random value")
signer = URLSafeTimedSerializer(SECRET)


def api_error(code, status=400):
    return jsonify({"ok": False, "error": code}), status


def set_state_cookie(response, provider, value):
    response.set_cookie(
        "nx_" + provider + "_state",
        signer.dumps(value, salt="nx-oauth-state"),
        secure=True, httponly=True, samesite="Lax",
        max_age=600, path="/auth/" + provider
    )
    return response


def check_state(provider):
    supplied = request.args.get("state", "")
    stored = request.cookies.get("nx_" + provider + "_state")
    if not stored or not supplied or len(supplied) > 150:
        return False
    try:
        expected = signer.loads(stored, salt="nx-oauth-state", max_age=600)
    except (BadSignature, SignatureExpired):
        return False
    return secrets.compare_digest(str(expected), supplied)


def go_back(provider, payload):
    token = signer.dumps(payload, salt="nx-account-token")
    response = make_response(redirect(SITE_URL + "/stores.html#nexplay_" + provider + "=" + token, code=302))
    response.delete_cookie("nx_" + provider + "_state", path="/auth/" + provider)
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


def error_redirect(code):
    return redirect(SITE_URL + "/stores.html#nexplay_error=" + code, code=302)


def bearer_identity(provider):
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer ") or len(header) > 5000:
        return None
    try:
        identity = signer.loads(header[7:], salt="nx-account-token", max_age=86400)
    except (BadSignature, SignatureExpired):
        return None
    if not isinstance(identity, dict) or identity.get("provider") != provider:
        return None
    return identity


@app.after_request
def response_headers(response):
    if request.path.startswith("/api/"):
        if request.headers.get("Origin") == SITE_URL:
            response.headers["Access-Control-Allow-Origin"] = SITE_URL
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "nexplay-auth"})


@app.route("/api/status")
def status():
    return jsonify({
        "ok": True, "steam_openid": True,
        "steam_library_available": bool(STEAM_API_KEY),
        "epic_oauth_available": bool(EPIC_CLIENT_ID and EPIC_CLIENT_SECRET and EPIC_DEPLOYMENT_ID),
        "cloud_streaming": False,
    })


@app.route("/api/steam/me")
def steam_me():
    data = bearer_identity("steam")
    if not data:
        return api_error("steam_not_authenticated", 401)
    return jsonify({"ok": True, "steam_id": data["steam_id"], "provider": "steam"})


@app.route("/api/steam/library")
def steam_library():
    data = bearer_identity("steam")
    if not data:
        return api_error("steam_not_authenticated", 401)
    if not STEAM_API_KEY:
        return api_error("steam_api_key_required", 503)
    try:
        r = requests.get(
            "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
            params={"key": STEAM_API_KEY, "steamid": data["steam_id"],
                    "include_appinfo": "true", "include_played_free_games": "true"},
            timeout=10, allow_redirects=False
        )
        r.raise_for_status()
        games = r.json().get("response", {}).get("games", [])
        safe_games = [{
            "appid": int(g["appid"]), "name": str(g.get("name", ""))[:180],
            "playtime_forever": int(g.get("playtime_forever", 0))
        } for g in games if isinstance(g, dict) and isinstance(g.get("appid"), int)][:2000]
        return jsonify({"ok": True, "games": safe_games, "count": len(safe_games),
                        "note": "Steam may hide private or unavailable library entries."})
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return api_error("steam_library_unavailable", 502)


@app.route("/auth/steam/start")
def steam_start():
    state = secrets.token_urlsafe(24)
    return_to = PUBLIC_BASE_URL + "/auth/steam/callback?state=" + state
    params = {
        "openid.ns": "http://specs.openid.net/auth/2.0",
        "openid.mode": "checkid_setup",
        "openid.return_to": return_to,
        "openid.realm": PUBLIC_BASE_URL + "/",
        "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
        "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select"
    }
    return set_state_cookie(redirect(STEAM_OPENID + "?" + urlencode(params)), "steam", state)


@app.route("/auth/steam/callback")
def steam_callback():
    if len(request.query_string) > 8192 or not check_state("steam"):
        return error_redirect("steam_invalid_state")
    vals = request.args.to_dict(flat=False)
    if any(len(v) != 1 for v in vals.values()):
        return error_redirect("steam_invalid_response")
    fields = {k: v[0] for k, v in vals.items() if k.startswith("openid.")}
    claimed = fields.get("openid.claimed_id", "")
    match = re.fullmatch(r"https?://steamcommunity\.com/openid/id/([0-9]{17})", claimed)
    signed = set(fields.get("openid.signed", "").split(","))
    required = {"claimed_id", "identity", "return_to", "response_nonce", "assoc_handle", "op_endpoint"}
    expected_url = PUBLIC_BASE_URL + "/auth/steam/callback?state=" + request.args["state"]
    if (not match or fields.get("openid.identity") != claimed or
        fields.get("openid.return_to") != expected_url or
        fields.get("openid.op_endpoint") != STEAM_OPENID or
        fields.get("openid.mode") != "id_res" or not required.issubset(signed)):
        return error_redirect("steam_invalid_response")
    if not re.match(r"^20[0-9]{2}-[0-9]{2}-[0-9]{2}T", fields.get("openid.response_nonce", "")):
        return error_redirect("steam_invalid_response")
    verify = dict(fields)
    verify["openid.mode"] = "check_authentication"
    try:
        response = requests.post(STEAM_OPENID, data=verify, timeout=10, allow_redirects=False)
        if response.status_code != 200 or "is_valid:true" not in response.text.splitlines():
            return error_redirect("steam_verification_failed")
    except requests.RequestException:
        return error_redirect("steam_verification_failed")
    return go_back("steam", {"provider": "steam", "steam_id": match.group(1), "issued_at": int(time.time())})


@app.route("/auth/epic/start")
def epic_start():
    if not all((EPIC_CLIENT_ID, EPIC_CLIENT_SECRET, EPIC_DEPLOYMENT_ID)):
        return error_redirect("epic_not_configured")
    state = secrets.token_urlsafe(24)
    callback = PUBLIC_BASE_URL + "/auth/epic/callback"
    params = {"client_id": EPIC_CLIENT_ID, "response_type": "code",
              "redirect_uri": callback, "scope": "basic_profile", "state": state}
    return set_state_cookie(
        redirect("https://www.epicgames.com/id/authorize?" + urlencode(params)),
        "epic", state
    )


@app.route("/auth/epic/callback")
def epic_callback():
    if not all((EPIC_CLIENT_ID, EPIC_CLIENT_SECRET, EPIC_DEPLOYMENT_ID)):
        return error_redirect("epic_not_configured")
    if not check_state("epic") or request.args.get("error") or not request.args.get("code"):
        return error_redirect("epic_invalid_state")
    credentials = base64.b64encode((EPIC_CLIENT_ID + ":" + EPIC_CLIENT_SECRET).encode()).decode()
    try:
        r = requests.post(
            "https://api.epicgames.dev/epic/oauth/v2/token",
            headers={"Authorization": "Basic " + credentials},
            data={"grant_type": "authorization_code", "code": request.args["code"],
                  "redirect_uri": PUBLIC_BASE_URL + "/auth/epic/callback",
                  "deployment_id": EPIC_DEPLOYMENT_ID},
            timeout=10, allow_redirects=False
        )
        r.raise_for_status()
        info = r.json()
        account_id = info.get("account_id", "")
        if not re.fullmatch("[a-fA-F0-9]{32}", account_id):
            return error_redirect("epic_verification_failed")
        return go_back("epic", {"provider": "epic", "epic_id": account_id,
                                "name": str(info.get("displayName", ""))[:80],
                                "issued_at": int(time.time())})
    except (requests.RequestException, ValueError, KeyError):
        return error_redirect("epic_verification_failed")


@app.route("/api/epic/me")
def epic_me():
    data = bearer_identity("epic")
    if not data:
        return api_error("epic_not_authenticated", 401)
    return jsonify({"ok": True, "epic_id": data["epic_id"],
                    "name": data.get("name", ""), "provider": "epic"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
