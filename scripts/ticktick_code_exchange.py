#!/usr/bin/env python3
"""Exchange a TickTick authorization code for access/refresh tokens."""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Dict

import requests
from dotenv import load_dotenv

TOKEN_URL = "https://ticktick.com/oauth/token"


def parse_args() -> argparse.Namespace:
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="Exchange a TickTick OAuth authorization code for tokens.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("code", help="Authorization code captured from the redirect")
    parser.add_argument(
        "--client-id",
        default=os.getenv("TICKTICK_CLIENT_ID"),
        help="TickTick OAuth client ID (defaults to TICKTICK_CLIENT_ID env)",
    )
    parser.add_argument(
        "--client-secret",
        default=os.getenv("TICKTICK_CLIENT_SECRET"),
        help="TickTick OAuth client secret (defaults to TICKTICK_CLIENT_SECRET env)",
    )
    parser.add_argument(
        "--redirect-uri",
        default=os.getenv("TICKTICK_REDIRECT_URI", "http://localhost:8765/callback"),
        help="Redirect URI used when requesting the authorization code",
    )
    parser.add_argument(
        "--scope",
        default=os.getenv("TICKTICK_SCOPE", "tasks:read tasks:write habit:read"),
        help="Scope used during authorization (optional; for reference only)",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Output raw JSON instead of friendly instructions.",
    )
    return parser.parse_args()


def exchange_code(args: argparse.Namespace) -> Dict[str, str]:
    if not args.client_id or not args.client_secret:
        print("TickTick client ID and secret are required.", file=sys.stderr)
        sys.exit(1)

    response = requests.post(
        TOKEN_URL,
        data=
        {
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "grant_type": "authorization_code",
            "redirect_uri": args.redirect_uri,
            "code": args.code,
        },
        timeout=30,
    )

    try:
        response.raise_for_status()
    except requests.HTTPError as err:
        print(
            f"Token request failed ({response.status_code}): {response.text}",
            file=sys.stderr,
        )
        raise SystemExit(1) from err

    return response.json()


def main() -> None:
    args = parse_args()
    payload = exchange_code(args)

    if args.raw:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    access_token = payload.get("access_token")
    refresh_token = payload.get("refresh_token")
    expires_in = payload.get("expires_in")

    print("Exchange successful. Add the following to your .env if needed:\n")
    if access_token:
        print(f"TICKTICK_ACCESS_TOKEN={access_token}")
    if refresh_token:
        print(f"# Optional: refresh token (not used by the automation script)")
        print(f"TICKTICK_REFRESH_TOKEN={refresh_token}")
    if expires_in:
        print(f"\nAccess token expires in roughly {expires_in} seconds.")
    if payload.get("token_type"):
        print(f"Token type: {payload['token_type']}")


if __name__ == "__main__":
    main()
