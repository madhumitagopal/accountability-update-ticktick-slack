#!/usr/bin/env python3
"""Query TickTick habit check-ins and extract value totals."""
from __future__ import annotations

import json
import logging
import os
from typing import Dict, List

import requests

TICKTICK_URL = "https://api.ticktick.com/api/v2/habitCheckins/query"
AFTER_STAMP = 20250923
HABIT_CHANNELS_PATH = "config/habit_channels.json"

BASE_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://ticktick.com",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
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


def load_channel_mapping(path: str) -> Dict[str, str]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("habit_channels.json must contain a JSON object keyed by habit id")
    return {str(key): str(value) for key, value in data.items()}


def main() -> None:
    ticktick_cookie = os.getenv("COOKIE")
    if not ticktick_cookie:
        raise RuntimeError("Set COOKIE in the environment before running this script.")

    channels_path = os.getenv("HABIT_CHANNELS_PATH", HABIT_CHANNELS_PATH)
    habit_ids = list(load_channel_mapping(channels_path).keys())
    payload = {"habitIds": habit_ids, "afterStamp": AFTER_STAMP}
    headers = dict(BASE_HEADERS)
    headers["Cookie"] = ticktick_cookie

    logger.info("Querying TickTick habit check-ins for %d habits", len(habit_ids))

    response = requests.post(TICKTICK_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    checkins = data.get("checkins")
    if not isinstance(checkins, dict):
        raise ValueError("Unexpected response format; 'checkins' object missing")

    values_by_habit = extract_values(checkins)
    print(json.dumps(values_by_habit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
