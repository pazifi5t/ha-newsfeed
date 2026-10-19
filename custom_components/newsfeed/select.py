"""Auswahl im Dashboard: Zeitraum (Tag/Woche) und angezeigtes Thema."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import PERIODS
from .coordinator import NewsfeedCoordinator
from .entity import NewsfeedEntity
from .sources import TOPICS

if TYPE_CHECKING:
    from . import NewsfeedConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NewsfeedConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    entities: list[SelectEntity] = [PeriodSelect(coordinator)]
    if coordinator.topics:
        entities.append(TopicSelect(coordinator))
    async_add_entities(entities)


class PeriodSelect(NewsfeedEntity, SelectEntity, RestoreEntity):
    """Tagesaktuell oder wochenaktuell – wirkt auf alle Newsfeed-Sensoren."""

    _attr_translation_key = "period"
    _attr_icon = "mdi:calendar-range"
    _attr_options = list(PERIODS)

    def __init__(self, coordinator: NewsfeedCoordinator) -> None:
        super().__init__(coordinator, "period")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in PERIODS:
            self.coordinator.period = last.state
            self.coordinator.async_update_listeners()

    @property
    def current_option(self) -> str:
        return self.coordinator.period

    async def async_select_option(self, option: str) -> None:
        self.coordinator.period = option
        self.coordinator.async_update_listeners()


class TopicSelect(NewsfeedEntity, SelectEntity, RestoreEntity):
    """Welches Thema der Sensor „Ausgewählte News“ zeigt."""

    _attr_translation_key = "topic"
    _attr_icon = "mdi:format-list-bulleted-type"

    def __init__(self, coordinator: NewsfeedCoordinator) -> None:
        super().__init__(coordinator, "topic")
        self._by_name = {TOPICS[t].name: t for t in coordinator.topics}
        self._attr_options = list(self._by_name)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in self._by_name:
            self.coordinator.active_topic = self._by_name[last.state]
            self.coordinator.async_update_listeners()

    @property
    def current_option(self) -> str | None:
        topic = self.coordinator.active_topic
        return TOPICS[topic].name if topic else None

    async def async_select_option(self, option: str) -> None:
        self.coordinator.active_topic = self._by_name[option]
        self.coordinator.async_update_listeners()
