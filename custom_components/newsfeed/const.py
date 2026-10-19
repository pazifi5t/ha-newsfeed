"""Konstanten für die Newsfeed-Integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "newsfeed"

CONF_TOPICS = "topics"
CONF_SOURCES = "sources"
CONF_CUSTOM_FEEDS = "custom_feeds"
CONF_PERIOD = "period"
CONF_MAX_ITEMS = "max_items"
CONF_SCAN_INTERVAL = "scan_interval"

PERIOD_DAY = "day"
PERIOD_WEEK = "week"
PERIODS: dict[str, timedelta] = {
    PERIOD_DAY: timedelta(hours=24),
    PERIOD_WEEK: timedelta(days=7),
}

DEFAULT_PERIOD = PERIOD_DAY
DEFAULT_MAX_ITEMS = 10
DEFAULT_SCAN_INTERVAL = 30  # Minuten

FETCH_TIMEOUT = 20  # Sekunden
USER_AGENT = "HomeAssistant-Newsfeed/1.0 (+https://github.com/pazifi5t/ha-newsfeed)"

EVENT_NEW_ARTICLE = f"{DOMAIN}_new_article"
MAX_EVENTS_PER_UPDATE = 5
