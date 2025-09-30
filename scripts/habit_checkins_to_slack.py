#!/usr/bin/env python3
"""Query TickTick habit check-ins and post value/goal summaries to Slack."""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

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

TICKTICK_HEADERS = {
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

# Map each habit ID to the Slack channel that should receive updates.
HABIT_SLACK_CHANNELS: Dict[str, str] = {
    "637ef6118a908f20373d81dc": "#habit-updates",
    "640ffd278a908f61790f00d0": "#habit-updates",
    "641940bd8a908f2bab1e575b": "#habit-updates",
    "641b30e98a908f1dd7ac8bc1": "#habit-updates",
    "67bc796e23391102791e4af7": "#habit-updates",
    "67cee3aa2a5f5f4562f2fc2e": "#habit-updates",
    "681867482a5f5f6857cf655c": "#habit-updates",
    "6818675a2a5f5f6857cf65c6": "#habit-updates",
    "6821ebbce3e69114f9f0879e": "#habit-updates",
    "6821ec20ee96d114f9f087e0": "#habit-updates",
    "6824adc64201510b3c8b1dcc": "#habit-updates",
    "682df3d57592515e6eefdc73": "#habit-updates",
    "686632312a5f5f3a83557f7c": "#habit-updates",
    "68d0df32bc58174aaad4b482": "#habit-updates",
    "68d0df56bc58174aaad4b575": "#habit-updates",
    "68da4ee8bc5817419d344d05": "#habit-updates",
}

SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_checkins() -> Dict[str, List[dict]]:
    payload = {"habitIds": HABIT_IDS, "afterStamp": AFTER_STAMP}
    logger.info("Querying TickTick for %d habits", len(HABIT_IDS))
    response = requests.post(TICKTICK_URL, headers=TICKTICK_HEADERS, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    checkins = data.get("checkins")
    if not isinstance(checkins, dict):
        raise ValueError("Unexpected response format: missing 'checkins' object")
    return checkins


def build_summary(checkins: Dict[str, List[dict]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for habit_id, entries in checkins.items():
        values: List[Dict[str, Any]] = []
        if isinstance(entries, list):
            for entry in entries:
                value = entry.get("value")
                goal = entry.get("goal")
                checkin_stamp = entry.get("checkinStamp")
                if value is None and goal is None:
                    continue
                values.append(
                    {
                        "checkinStamp": checkin_stamp,
                        "value": value,
                        "goal": goal,
                    }
                )
        summary[habit_id] = values
    return summary


def post_to_slack(token: str, channel: str, habit_id: str, summary: List[Dict[str, Any]]) -> None:
    text = f"*Habit* `{habit_id}`\n```{json.dumps(summary, ensure_ascii=False, indent=2)}```"
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
    logger.info("Posted summary for %s to %s", habit_id, channel)


def main() -> None:
    load_dotenv()
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        logger.error("SLACK_BOT_TOKEN is required to send updates to Slack")
        sys.exit(1)

    checkins = fetch_checkins()
    summary = build_summary(checkins)
    for habit_id, entries in summary.items():
        channel = HABIT_SLACK_CHANNELS.get(habit_id)
        if not channel:
            logger.warning("No Slack channel mapped for habit %s; skipping", habit_id)
            continue
        post_to_slack(slack_token, channel, habit_id, entries)

    # Also print the aggregated summary for reference.
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
