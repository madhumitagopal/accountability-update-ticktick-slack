#!/usr/bin/env python3
"""Fetch TickTick habits and refresh the local habit mapping file."""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Dict

from dotenv import load_dotenv

from ticktick_client import TickTickClient

HABIT_MAPPING_PATH = "habit_id_mapping.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def build_mapping(habits: list[dict]) -> Dict[str, dict]:
    mapping: Dict[str, dict] = {}
    for habit in habits:
        habit_id = habit.get("id")
        if not habit_id:
            logger.warning("Skipping habit without id: %s", habit)
            continue
        mapping[str(habit_id)] = habit
    return mapping


def main() -> None:
    load_dotenv()
    access_token = os.getenv("TICKTICK_ACCESS_TOKEN")
    if not access_token:
        logger.error("TICKTICK_ACCESS_TOKEN is required to fetch habits.")
        sys.exit(1)

    client = TickTickClient(access_token)
    habits = client.list_habits()
    mapping = build_mapping(habits)

    with open(HABIT_MAPPING_PATH, "w", encoding="utf-8") as handle:
        json.dump(mapping, handle, ensure_ascii=False, sort_keys=True, indent=2)
        handle.write("\n")

    logger.info("Updated %s with %d habits", HABIT_MAPPING_PATH, len(mapping))
    print(json.dumps(mapping, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
