"""Coordinator: lädt alle Feeds und berechnet die Ranglisten je Thema."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CUSTOM_FEEDS,
    CONF_MAX_ITEMS,
    CONF_PERIOD,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    CONF_TOPICS,
    DEFAULT_MAX_ITEMS,
    DEFAULT_PERIOD,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_NEW_ARTICLE,
    FETCH_TIMEOUT,
    MAX_EVENTS_PER_UPDATE,
    PERIOD_DAY,
    PERIODS,
    USER_AGENT,
)
from .feeds import Article, FeedError, Source, custom_source, parse_feed, rank
from .sources import TOPICS

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

# data[topic][period] -> Liste der Artikel
NewsData = dict[str, dict[str, list[Article]]]


async def async_fetch_feed(hass: HomeAssistant, source: Source) -> list[Article]:
    """Einen Feed laden und parsen."""
    session = async_get_clientsession(hass)
    try:
        async with asyncio.timeout(FETCH_TIMEOUT):
            async with session.get(
                source.url, headers={"User-Agent": USER_AGENT}
            ) as resp:
                resp.raise_for_status()
                raw = await resp.read()
    except (aiohttp.ClientError, TimeoutError) as err:
        raise FeedError(f"{source.name}: {err}") from err
    return await hass.async_add_executor_job(parse_feed, raw, source)


def topic_sources(options: dict[str, Any], topic_key: str) -> list[Source]:
    """Die für ein Thema aktivierten Quellen (Katalog + eigene Feeds)."""
    topic = TOPICS.get(topic_key)
    if topic is None:
        return []
    selected = options.get(CONF_SOURCES, {}).get(topic_key, topic.default_sources)
    sources = [s for key in selected if (s := topic.source(key))]
    sources += [
        custom_source(url) for url in options.get(CONF_CUSTOM_FEEDS, {}).get(topic_key, [])
    ]
    return sources


class NewsfeedCoordinator(DataUpdateCoordinator[NewsData]):
    """Lädt die Feeds aller gewählten Themen."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        options = entry.options
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                minutes=int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            ),
        )
        self.topics: list[str] = [t for t in options.get(CONF_TOPICS, []) if t in TOPICS]
        self.max_items = int(options.get(CONF_MAX_ITEMS, DEFAULT_MAX_ITEMS))
        self.period: str = options.get(CONF_PERIOD, DEFAULT_PERIOD)
        self.active_topic: str | None = self.topics[0] if self.topics else None
        self.sources = {t: topic_sources(options, t) for t in self.topics}
        self.errors: dict[str, list[str]] = {}
        self._cache: dict[str, list[Article]] = {}
        self._seen: dict[str, set[str]] | None = None

    def articles(self, topic: str, period: str | None = None) -> list[Article]:
        """Rangliste eines Themas im gewünschten Zeitraum."""
        if not self.data:
            return []
        return self.data.get(topic, {}).get(period or self.period, [])

    async def _async_update_data(self) -> NewsData:
        all_sources = {s.key: s for srcs in self.sources.values() for s in srcs}
        results = await asyncio.gather(
            *(async_fetch_feed(self.hass, s) for s in all_sources.values()),
            return_exceptions=True,
        )

        failed: set[str] = set()
        for (key, source), result in zip(all_sources.items(), results, strict=True):
            if isinstance(result, BaseException):
                failed.add(key)
                _LOGGER.warning("Feed %s nicht abrufbar: %s", source.url, result)
            else:
                self._cache[key] = result

        if failed and len(failed) == len(all_sources) and not self._cache:
            raise UpdateFailed("Keiner der Feeds war erreichbar")

        now = dt_util.utcnow()
        data: NewsData = {}
        self.errors = {}
        for topic, sources in self.sources.items():
            feeds = [(s, self._cache.get(s.key, [])) for s in sources]
            data[topic] = {
                period: rank(feeds, window, self.max_items, now)
                for period, window in PERIODS.items()
            }
            self.errors[topic] = [s.name for s in sources if s.key in failed]

        self._fire_new_article_events(data)
        return data

    def _fire_new_article_events(self, data: NewsData) -> None:
        """Event für neue Artikel des Tages (nicht beim ersten Laden)."""
        first_run = self._seen is None
        seen = self._seen or {}
        for topic, periods in data.items():
            current = periods.get(PERIOD_DAY, [])
            known = seen.setdefault(topic, set())
            new = [a for a in current if a.key not in known]
            if len(known) > 1000:
                known.clear()
            known.update(a.key for a in current)
            if first_run:
                continue
            for art in new[:MAX_EVENTS_PER_UPDATE]:
                self.hass.bus.async_fire(
                    EVENT_NEW_ARTICLE,
                    {"topic": topic, "topic_name": TOPICS[topic].name, **art.as_dict()},
                )
        self._seen = seen
