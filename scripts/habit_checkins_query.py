#!/usr/bin/env python3
"""Query TickTick habit check-ins and extract value totals."""
from __future__ import annotations

import json
import logging
from typing import Dict, List

import requests

TICKTICK_URL = "https://api.ticktick.com/api/v2/habitCheckins/query"
HABIT_IDS = [
    "637ef6118a908f20373d81dc",
    "640ffd278a908f61790f00d0",
    "641940bd8a908f2bab1e575b",
    "641b30e98a908f1dd7ac8bc1",
    "67bc796e23391102791e4af7",
    "67cee3aa2a5f5f4562f2fc2e",
    "681867482a5f5f6857cf655c",
    "6818675a2a5f5f6857cf65c6",
    "6821ebbce3e69114f9f0879e",
    "6821ec20ee96d114f9f087e0",
    "6824adc64201510b3c8b1dcc",
    "682df3d57592515e6eefdc73",
    "686632312a5f5f3a83557f7c",
    "68d0df32bc58174aaad4b482",
    "68d0df56bc58174aaad4b575",
    "68da4ee8bc5817419d344d05",
]
AFTER_STAMP = 20250923

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://ticktick.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
    ),
    "Cookie": (
        "tt_distid=help-68da95c7b98ce051e421fd48; "
        "t=0CAB80045A64122BADC09F597C27C63936AB438A5226B8D9B08FE894CC03043742A3818C7FF69F9B2CAF14D923F0D3DA1B263BFD942D3374D9C4BD4C7D153AFC9D94C290994417C272B5ADB49788099DA96445986C05FDCF3219CC42FC1C7A2FEBDD19E1F9A47A01ECFABBF7504359D4711F9CAEDB90785858CAD9E5CECB0A9EEBDD19E1F9A47A01C5727C5DD292B81F11DB04AB803AC01103CED2597B0727F88E540B0C0633D20F2C4A454D958D049DFE2EDA4C4A6B5CD0;"
    ),
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def extract_values(checkins: Dict[str, List[dict]]) -> Dict[str, List[float]]:
    """Return a mapping of habitId -> list of numeric values."""
    result: Dict[str, List[float]] = {}
    for habit_id, entries in checkins.items():
        values = []
        if isinstance(entries, list):
            for entry in entries:
                value = entry.get("value")
                if isinstance(value, (int, float)):
                    values.append(float(value))
        result[habit_id] = values
    return result


def main() -> None:
    payload = {"habitIds": HABIT_IDS, "afterStamp": AFTER_STAMP}
    logger.info("Querying TickTick habit check-ins for %d habits", len(HABIT_IDS))

    response = requests.post(TICKTICK_URL, headers=HEADERS, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    checkins = data.get("checkins")
    if not isinstance(checkins, dict):
        raise ValueError("Unexpected response format; 'checkins' object missing")

    values_by_habit = extract_values(checkins)
    print(json.dumps(values_by_habit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
