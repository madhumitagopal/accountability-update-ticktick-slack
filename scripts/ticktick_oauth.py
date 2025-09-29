#!/usr/bin/env python3
"""Helper script to complete the TickTick OAuth flow and print tokens."""
import http.server
import os
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from typing import Optional

import requests
from dotenv import load_dotenv

AUTHORIZE_URL = "https://ticktick.com/oauth/authorize"
TOKEN_URL = "https://ticktick.com/oauth/token"
DEFAULT_PORT = 8765


def build_auth_url(client_id: str, redirect_uri: str, state: str, scope: str) -> str:
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
    )
    return f"{AUTHORIZE_URL}?{query}"


class OAuthCodeServer(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP server used to capture the authorization code."""

    code: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]

        if error:
            OAuthCodeServer.error = error
        elif not code:
            OAuthCodeServer.error = "Missing code in callback"
        elif state != OAuthCodeServer.state:
            OAuthCodeServer.error = "State parameter mismatch"
        else:
            OAuthCodeServer.code = code

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        if OAuthCodeServer.error:
            message = "Authorization failed. You can close this tab."
        else:
            message = "Authorization succeeded. You can close this tab."
        self.wfile.write(message.encode("utf-8"))

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - signature fixed
        # Silence default request logging for a cleaner CLI experience.
        return


def exchange_code_for_tokens(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> dict:
    response = requests.post(
        TOKEN_URL,
        data=
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    load_dotenv()
    client_id = os.getenv("TICKTICK_CLIENT_ID")
    client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
    redirect_uri = os.getenv("TICKTICK_REDIRECT_URI", f"http://localhost:{DEFAULT_PORT}/callback")
    scope = os.getenv("TICKTICK_SCOPE", "tasks:read tasks:write habit:read")

    if not client_id or not client_secret:
        print("TICKTICK_CLIENT_ID and TICKTICK_CLIENT_SECRET must be set in your environment.", file=sys.stderr)
        sys.exit(1)

    parsed_redirect = urllib.parse.urlparse(redirect_uri)
    port = parsed_redirect.port or DEFAULT_PORT

    state = secrets.token_urlsafe(16)
    OAuthCodeServer.state = state

    server = http.server.HTTPServer(("", port), OAuthCodeServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    auth_url = build_auth_url(client_id, redirect_uri, state, scope)
    print("\n1. Visit the following URL in your browser and authorize the app:\n")
    print(auth_url)

    try:
        webbrowser.open(auth_url)
    except webbrowser.Error:
        pass

    print("\n2. After authorizing, you will be redirected back here.")
    print("   This script will capture the authorization code automatically.\n")

    try:
        while OAuthCodeServer.code is None and OAuthCodeServer.error is None:
            thread.join(timeout=0.1)
    except KeyboardInterrupt:
        print("Interrupted before receiving authorization code.", file=sys.stderr)
        sys.exit(1)
    finally:
        server.shutdown()

    if OAuthCodeServer.error:
        print(f"OAuth failed: {OAuthCodeServer.error}", file=sys.stderr)
        sys.exit(1)

    tokens = exchange_code_for_tokens(client_id, client_secret, redirect_uri, OAuthCodeServer.code)

    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    expires_in = tokens.get("expires_in")

    print("\nReceived tokens:")
    if refresh_token:
        print(f"  TICKTICK_REFRESH_TOKEN={refresh_token}")
    else:
        print("  (No refresh token returned; check your app's OAuth permissions.)")
    if access_token:
        print(f"  Access token (expires in {expires_in}s): {access_token[:12]}…")

    print("\nAdd the refresh token to your .env file as TICKTICK_REFRESH_TOKEN.")


if __name__ == "__main__":
    main()
