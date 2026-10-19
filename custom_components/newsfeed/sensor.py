"""Sensoren: je Thema einer, plus einer für das im Dashboard gewählte Thema."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import NewsfeedCoordinator
from .entity import NewsfeedEntity
from .sources import TOPICS

if TYPE_CHECKING:
    from . import NewsfeedConfigEntry

PERIOD_LABELS = {"day": "Heute (24 h)", "week": "Diese Woche (7 Tage)"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NewsfeedConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        NewsTopicSensor(coordinator, topic) for topic in coordinator.topics
    ]
    if coordinator.topics:
        entities.append(NewsSelectedSensor(coordinator))
    async_add_entities(entities)


class _NewsSensorBase(NewsfeedEntity, SensorEntity):
    """Zustand = Anzahl Artikel; die Artikel stehen im Attribut ``articles``."""

    _attr_native_unit_of_measurement = "Artikel"
    _unrecorded_attributes = frozenset({"articles", "headline", "headline_link", "unavailable_sources"})

    def _topic(self) -> str | None:
        raise NotImplementedError

    @property
    def native_value(self) -> int:
        topic = self._topic()
        return len(self.coordinator.articles(topic)) if topic else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        topic = self._topic()
        if not topic:
            return {}
        articles = self.coordinator.articles(topic)
        return {
            "topic": TOPICS[topic].name,
            "period": self.coordinator.period,
            "period_label": PERIOD_LABELS.get(self.coordinator.period),
            "headline": articles[0].title if articles else None,
            "headline_link": articles[0].link if articles else None,
            "articles": [a.as_dict() for a in articles],
            "unavailable_sources": self.coordinator.errors.get(topic, []),
        }


class NewsTopicSensor(_NewsSensorBase):
    """Nachrichten eines festen Themas."""

    def __init__(self, coordinator: NewsfeedCoordinator, topic: str) -> None:
        super().__init__(coordinator, f"topic_{topic}")
        self._topic_key = topic
        self._attr_name = TOPICS[topic].name
        self._attr_icon = TOPICS[topic].icon

    def _topic(self) -> str:
        return self._topic_key


class NewsSelectedSensor(_NewsSensorBase):
    """Nachrichten des Themas, das über ``select.newsfeed_thema`` gewählt ist."""

    _attr_translation_key = "selected"
    _attr_icon = "mdi:newspaper-variant-outline"

    def __init__(self, coordinator: NewsfeedCoordinator) -> None:
        super().__init__(coordinator, "selected")

    def _topic(self) -> str | None:
        return self.coordinator.active_topic

    @property
    def icon(self) -> str | None:
        topic = self._topic()
        return TOPICS[topic].icon if topic else self._attr_icon
