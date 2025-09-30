"""Shared TickTick client helpers."""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, List, Optional

import requests

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
)
TICKTICK_COOKIE = (
    "tt_distid=help-68da95c7b98ce051e421fd48; "
    "t=0CAB80045A64122BADC09F597C27C63936AB438A5226B8D9B08FE894CC03043742A3818C7FF69F9B2CAF14D923F0D3DA1B263BFD942D3374D9C4BD4C7D153AFC9D94C290994417C272B5ADB49788099DA96445986C05FDCF3219CC42FC1C7A2FEBDD19E1F9A47A01ECFABBF7504359D4711F9CAEDB90785858CAD9E5CECB0A9EEBDD19E1F9A47A01C5727C5DD292B81F11DB04AB803AC01103CED2597B0727F88E540B0C0633D20F2C4A454D958D049DFE2EDA4C4A6B5CD0;"
)
HABITS_URL = "https://api.ticktick.com/api/v2/habits"
HABIT_CHECKINS_URL = "https://api.ticktick.com/api/v2/habits/{habit_id}/checkins"
HABIT_CHECKINS_QUERY_URL = "https://api.ticktick.com/api/v2/habitCheckins/query"


class TickTickClient:
    """Simple wrapper for the TickTick API using a static access token."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://ticktick.com",
            "User-Agent": BROWSER_USER_AGENT,
            "Cookie": TICKTICK_COOKIE,
        }

    def list_habits(self) -> List[dict]:
        response = requests.get(HABITS_URL, headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_checkin(self, habit_id: str, target_date: dt.date) -> Optional[dict]:
        params = {
            "from": target_date.isoformat(),
            "to": target_date.isoformat(),
        }
        url = HABIT_CHECKINS_URL.format(habit_id=habit_id)
        response = requests.get(url, headers=self._headers(), params=params, timeout=30)
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        checkins = data.get("checkins") or data.get("data") or []
        for entry in checkins:
            if entry.get("date") == target_date.isoformat():
                return entry
        return checkins[0] if checkins else None

    def query_checkins(self, habit_ids: List[str], after_stamp: int) -> Dict[str, List[dict]]:
        payload = {"habitIds": habit_ids, "afterStamp": after_stamp}
        headers = self._headers()
        headers.update(
            {
                "Content-Type": "application/json;charset=UTF-8",
            }
        )
        response = requests.post(
            HABIT_CHECKINS_QUERY_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        checkins = data.get("checkins")
        if not isinstance(checkins, dict):
            raise ValueError("Unexpected response shape from habitCheckins/query")
        return {str(habit_id): entries or [] for habit_id, entries in checkins.items()}
