#!/usr/bin/env python3
"""Pull TickTick habit stats for a day and post them to Slack."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import pytz
import requests
import yaml
from dotenv import load_dotenv

HABITS_URL = "https://api.ticktick.com/api/v2/habits"
HABIT_CHECKINS_URL = "https://api.ticktick.com/api/v2/habits/{habit_id}/checkins"
SLACK_POST_MESSAGE_URL = "https://slack.com/api/chat.postMessage"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class HabitConfig:
    title: str
    habit_id: Optional[str] = None
    slack_channel: Optional[str] = None
    message_template: Optional[str] = None


class TickTickClient:
    """Simple wrapper for the TickTick API using a static access token."""

    def __init__(self, access_token: str) -> None:
        self.access_token = access_token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    def list_habits(self) -> List[dict]:
        response = requests.get(HABITS_URL, headers=self._headers(), timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Failed to fetch habits ({response.status_code}): {response.text}")
        return response.json()

    def fetch_checkin(self, habit_id: str, target_date: dt.date) -> Optional[dict]:
        params = {
            "from": target_date.isoformat(),
            "to": target_date.isoformat(),
        }
        url = HABIT_CHECKINS_URL.format(habit_id=habit_id)
        response = requests.get(url, headers=self._headers(), params=params, timeout=30)
        if response.status_code == 404:
            logger.warning("Habit %s not found when fetching check-ins", habit_id)
            return None
        if response.status_code != 200:
            raise RuntimeError(
                f"Failed to fetch check-ins for {habit_id} ({response.status_code}): {response.text}"
            )
        data = response.json()
        # API usually returns {"checkins": [...]} but fall back if structure changes.
        checkins = data.get("checkins") or data.get("data") or []
        for entry in checkins:
            if entry.get("date") == target_date.isoformat():
                return entry
        # Nothing matched; return first entry if available for visibility.
        return checkins[0] if checkins else None


class SlackPoster:
    def __init__(self, token: str, dry_run: bool = False) -> None:
        self.token = token
        self.dry_run = dry_run

    def post_message(self, channel: str, text: str, blocks: Optional[List[dict]] = None) -> None:
        payload: Dict[str, Any] = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks

        if self.dry_run:
            logger.info("[dry-run] Would post to %s: %s", channel, json.dumps(payload, ensure_ascii=False))
            return

        response = requests.post(
            SLACK_POST_MESSAGE_URL,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=payload,
            timeout=30,
        )
        data = response.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error for channel {channel}: {data}")
        logger.info("Posted habit update to %s", channel)


def load_habit_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    habits = data.get("habits", [])
    if not isinstance(habits, list):
        raise ValueError("habits entry in config must be a list")
    parsed = []
    for raw in habits:
        if not isinstance(raw, dict) or "title" not in raw:
            raise ValueError("Each habit entry must include at least a title")
        parsed.append(HabitConfig(**raw))
    default_template = data.get("default_template", "*{title}*: {status}")
    return {"habits": parsed, "default_template": default_template}


def choose_habit(habits: Iterable[dict], config: HabitConfig) -> Optional[dict]:
    """Resolve the TickTick habit entry for this config."""
    if config.habit_id:
        for habit in habits:
            if str(habit.get("id")) == str(config.habit_id):
                return habit
    title_lower = config.title.strip().lower()
    matches = [habit for habit in habits if habit.get("title", "").lower() == title_lower]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        logger.warning("Multiple habits matched title '%s'; specify habit_id in config", config.title)
        return matches[0]
    logger.warning("No habit matched title '%s'", config.title)
    return None


def interpret_status(checkin: Optional[dict]) -> Dict[str, Any]:
    if not checkin:
        return {"status": "No entry", "value": None, "raw": None}

    status_code = checkin.get("status")
    status_map = {
        0: "Not completed",
        1: "Partial",
        2: "Completed",
        3: "Skipped",
    }
    status_text = status_map.get(status_code, f"Status {status_code}")
    value = checkin.get("value")
    unit = checkin.get("unit")
    if value is not None and unit:
        value_text = f"{value} {unit}"
    elif value is not None:
        value_text = str(value)
    else:
        value_text = ""
    streak = checkin.get("chainLength") or checkin.get("currentChain")
    metadata = {
        "status": status_text,
        "status_code": status_code,
        "value": value_text,
        "raw": checkin,
        "streak": streak,
    }
    return metadata


def format_message(template: str, context: Dict[str, Any]) -> str:
    try:
        return template.format(**context)
    except KeyError as err:
        missing = err.args[0]
        raise KeyError(f"Template placeholder '{{{missing}}}' is not available in context: {context}") from err


def build_context(config: HabitConfig, habit: Optional[dict], checkin_summary: Dict[str, Any]) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "title": config.title,
        "status": checkin_summary.get("status"),
        "status_code": checkin_summary.get("status_code"),
        "value": checkin_summary.get("value"),
        "streak": checkin_summary.get("streak"),
        "raw_checkin": json.dumps(checkin_summary.get("raw"), ensure_ascii=False) if checkin_summary.get("raw") else "",
    }
    if habit:
        context.update(
            {
                "habit_id": habit.get("id"),
                "goal": habit.get("goal"),
                "goal_type": habit.get("goalType"),
            }
        )
    return context


def determine_target_date(tz_name: str, override: Optional[str]) -> dt.date:
    tz = pytz.timezone(tz_name)
    if override:
        return dt.date.fromisoformat(override)
    now = dt.datetime.now(tz)
    return now.date()


def list_habits(client: TickTickClient) -> None:
    habits = client.list_habits()
    for habit in habits:
        habit_id = habit.get("id")
        title = habit.get("title")
        goal = habit.get("goal")
        print(f"{title} -> {habit_id}")
        if goal:
            print(f"  goal: {goal}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send TickTick habit updates to Slack")
    parser.add_argument("--date", help="ISO date (YYYY-MM-DD). Defaults to today in the configured timezone.")
    parser.add_argument("--dry-run", action="store_true", help="Print Slack payload instead of sending.")
    parser.add_argument("--list-habits", action="store_true", help="List TickTick habits and exit.")
    parser.add_argument("--config", help="Override habit config path from HABIT_CONFIG_PATH env.")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    access_token = os.getenv("TICKTICK_ACCESS_TOKEN")
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    timezone_name = os.getenv("TIMEZONE", "Asia/Kolkata")
    config_path = args.config or os.getenv("HABIT_CONFIG_PATH", "config/habits.yaml")

    if not access_token:
        logger.error("TICKTICK_ACCESS_TOKEN is required. Provide a valid TickTick access token.")
        sys.exit(1)
    if not slack_token and not args.list_habits:
        logger.error("SLACK_BOT_TOKEN is required unless you are using --list-habits.")
        sys.exit(1)

    client = TickTickClient(access_token)

    if args.list_habits:
        list_habits(client)
        return

    target_date = determine_target_date(timezone_name, args.date)
    logger.info("Preparing habit updates for %s", target_date.isoformat())

    try:
        config_data = load_habit_config(config_path)
    except FileNotFoundError:
        logger.error("Habit config file not found at %s", config_path)
        sys.exit(1)

    habits = client.list_habits()
    slack = SlackPoster(slack_token, dry_run=args.dry_run)
    default_channel = os.getenv("SLACK_DEFAULT_CHANNEL")
    default_template = config_data["default_template"]

    for habit_config in config_data["habits"]:
        habit = choose_habit(habits, habit_config)
        if not habit:
            logger.warning("Skipping habit '%s' due to unresolved mapping", habit_config.title)
            continue

        checkin = client.fetch_checkin(str(habit.get("id")), target_date)
        summary = interpret_status(checkin)
        context = build_context(habit_config, habit, summary)
        template = habit_config.message_template or default_template
        message = format_message(template, context)

        channel = habit_config.slack_channel or default_channel
        if not channel:
            logger.error(
                "No Slack channel configured for habit '%s' and SLACK_DEFAULT_CHANNEL is not set",
                habit_config.title,
            )
            continue

        slack.post_message(channel, message)


if __name__ == "__main__":
    main()
