#!/usr/bin/env python3
"""Query TickTick habit check-ins and post value/goal summaries to Slack."""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

TICKTICK_URL = "https://api.ticktick.com/api/v2/habitCheckins/query"
AFTER_STAMP = 20250923

BASE_TICKTICK_HEADERS = {
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

SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"
HABIT_MAPPING_PATH = "habit_id_mapping.json"
HABIT_CHANNELS_PATH = "config/habit_channels.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_checkins(habit_ids: List[str], cookie_header: str) -> Dict[str, List[dict]]:
    payload = {"habitIds": habit_ids, "afterStamp": AFTER_STAMP}
    logger.info("Querying TickTick for %d habits", len(habit_ids))
    headers = dict(BASE_TICKTICK_HEADERS)
    headers["Cookie"] = cookie_header
    response = requests.post(TICKTICK_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    checkins = data.get("checkins")
    if not isinstance(checkins, dict):
        raise ValueError("Unexpected response format: missing 'checkins' object")
    return checkins


def parse_stamp(raw_stamp: Any) -> Optional[int]:
    try:
        return int(raw_stamp)
    except (TypeError, ValueError):
        return None


def build_summary(checkins: Dict[str, List[dict]]) -> Dict[str, Dict[str, Any]]:
    """Return today's value (or zero) for each habit."""

    today_stamp = int(datetime.now().strftime("%Y%m%d"))
    summary: Dict[str, Dict[str, Any]] = {}

    for habit_id, entries in checkins.items():
        value: Any = 0

        if isinstance(entries, list):
            for entry in entries:
                if parse_stamp(entry.get("checkinStamp")) == today_stamp:
                    entry_value = entry.get("value")
                    value = entry_value if entry_value not in (None, "") else 0
                    break

        summary[habit_id] = {"value": value}

    return summary


def load_habit_mapping(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as err:
        raise FileNotFoundError(
            f"Habit mapping file not found at {path}. Run scripts/get_habits.py first."
        ) from err

    if not isinstance(data, dict):
        raise ValueError("habit_id_mapping.json must contain a JSON object keyed by habit id")
    return data


def load_channel_mapping(path: str) -> Dict[str, str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as err:
        raise FileNotFoundError(
            f"Habit channel mapping file not found at {path}."
        ) from err

    if not isinstance(data, dict):
        raise ValueError("habit_channels.json must contain a JSON object keyed by habit id")
    return {str(key): str(value) for key, value in data.items()}


def post_to_slack(
    token: str,
    channel: str,
    habit_name: str,
    value: Optional[float],
    goal: Optional[float],
) -> None:
    def fmt(number: Optional[float]) -> str:
        if number is None:
            return "-"
        if isinstance(number, float) and number.is_integer():
            return str(int(number))
        return str(number)

    value_text = fmt(value)
    goal_text = fmt(goal)
    text = f"{habit_name} : {value_text}/{goal_text}"
    response = requests.post(
        SLACK_POST_MESSAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        json={"channel": channel, "text": text},
        timeout=30,
    )
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error for channel {channel}: {data}")
    logger.info("Posted summary for %s to %s", habit_name, channel)


def main() -> None:
    load_dotenv()
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        logger.error("SLACK_BOT_TOKEN is required to send updates to Slack")
        sys.exit(1)

    ticktick_cookie = os.getenv("COOKIE")
    if not ticktick_cookie:
        logger.error("COOKIE environment variable is required to query TickTick")
        sys.exit(1)

    channels_path = os.getenv("HABIT_CHANNELS_PATH", HABIT_CHANNELS_PATH)
    try:
        channel_mapping = load_channel_mapping(channels_path)
    except (FileNotFoundError, ValueError) as err:
        logger.error("%s", err)
        sys.exit(1)

    habit_mapping = load_habit_mapping(HABIT_MAPPING_PATH)

    habit_ids = list(channel_mapping.keys())
    checkins = fetch_checkins(habit_ids, ticktick_cookie)
    summary = build_summary(checkins)
    for habit_id, totals in summary.items():
        channel = channel_mapping.get(habit_id)
        if not channel:
            logger.warning("No Slack channel mapped for habit %s; skipping", habit_id)
            continue

        mapping_entry = habit_mapping.get(habit_id, {})
        habit_name = mapping_entry.get("name") or habit_id

        value = totals.get("value") if isinstance(totals, dict) else 0

        goal: Any = mapping_entry.get("goal")
        if goal is None:
            goal = mapping_entry.get("step")

        if isinstance(totals, dict):
            totals["goal"] = goal

        post_to_slack(slack_token, channel, habit_name, value, goal)

    # Also print the aggregated summary for reference.
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
