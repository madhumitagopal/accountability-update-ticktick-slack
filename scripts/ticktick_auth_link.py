#!/usr/bin/env python3
"""Generate a TickTick OAuth authorization URL."""
from __future__ import annotations

import argparse
import os
import secrets
import sys
import urllib.parse
import webbrowser

from dotenv import load_dotenv

AUTH_URL = "https://ticktick.com/oauth/authorize"
DEFAULT_SCOPE = "tasks:read tasks:write habit:read"
DEFAULT_REDIRECT = "http://localhost:8765/callback"


def build_url(client_id: str, redirect_uri: str, scope: str, state: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "state": state,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Generate a TickTick OAuth authorization URL and optionally open it in a browser.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--client-id",
        default=os.getenv("TICKTICK_CLIENT_ID"),
        help="TickTick OAuth client ID (defaults to TICKTICK_CLIENT_ID env)",
    )
    parser.add_argument(
        "--redirect-uri",
        default=os.getenv("TICKTICK_REDIRECT_URI", DEFAULT_REDIRECT),
        help="Redirect URI registered in the TickTick developer portal",
    )
    parser.add_argument(
        "--scope",
        default=os.getenv("TICKTICK_SCOPE", DEFAULT_SCOPE),
        help="Scopes requested during authorization",
    )
    parser.add_argument(
        "--state",
        help="State parameter to guard against CSRF. Randomised when omitted.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Only print the URL; do not attempt to open a browser",
    )
    args = parser.parse_args()

    if not args.client_id:
        print("TickTick client ID is required (set TICKTICK_CLIENT_ID or use --client-id).", file=sys.stderr)
        sys.exit(1)

    state = args.state or secrets.token_urlsafe(16)
    url = build_url(args.client_id, args.redirect_uri, args.scope, state)

    print("Authorization URL:\n")
    print(url)
    print()
    print("Use this state value when exchanging the code:", state)

    if args.no_browser:
        return

    try:
        opened = webbrowser.open(url)
    except webbrowser.Error:
        opened = False

    if opened:
        print("Opened default browser. If it didn't appear, copy the URL manually.")
    else:
        print("Could not open browser automatically; copy the URL into your browser.")


if __name__ == "__main__":
    main()
