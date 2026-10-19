"""Einrichtungs- und Options-Dialog: Themen wählen, dann Quellen je Thema."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
)

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
    PERIOD_DAY,
    PERIOD_WEEK,
)
from .coordinator import async_fetch_feed
from .feeds import FeedError, custom_source
from .sources import TOPICS


def _general_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_TOPICS, default=defaults.get(CONF_TOPICS, list(TOPICS))
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=t.key, label=t.name) for t in TOPICS.values()
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Required(
                CONF_PERIOD, default=defaults.get(CONF_PERIOD, DEFAULT_PERIOD)
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=PERIOD_DAY, label="Tagesaktuell (24 Stunden)"),
                        SelectOptionDict(value=PERIOD_WEEK, label="Wochenaktuell (7 Tage)"),
                    ],
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
            vol.Required(
                CONF_MAX_ITEMS, default=defaults.get(CONF_MAX_ITEMS, DEFAULT_MAX_ITEMS)
            ): NumberSelector(
                NumberSelectorConfig(min=3, max=50, step=1, mode=NumberSelectorMode.BOX)
            ),
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=10,
                    max=240,
                    step=5,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _sources_schema(topic_key: str, defaults: dict[str, Any]) -> vol.Schema:
    topic = TOPICS[topic_key]
    selected = defaults.get(CONF_SOURCES, {}).get(topic_key, topic.default_sources)
    custom = defaults.get(CONF_CUSTOM_FEEDS, {}).get(topic_key, [])
    return vol.Schema(
        {
            vol.Optional(CONF_SOURCES, default=selected): SelectSelector(
                SelectSelectorConfig(
                    options=[
                        SelectOptionDict(value=s.key, label=s.name) for s in topic.sources
                    ],
                    multiple=True,
                    mode=SelectSelectorMode.LIST,
                )
            ),
            vol.Optional(CONF_CUSTOM_FEEDS, default="\n".join(custom)): TextSelector(
                TextSelectorConfig(multiline=True)
            ),
        }
    )


def _split_urls(value: str) -> list[str]:
    return [u.strip() for u in (value or "").replace(",", "\n").splitlines() if u.strip()]


class _NewsfeedFlowMixin:
    """Gemeinsame Schritte für Einrichtung und Optionen."""

    hass: Any
    _options: dict[str, Any]
    _defaults: dict[str, Any]
    _pending: list[str]

    def _start(self, user_input: dict[str, Any]) -> None:
        self._options = {
            CONF_TOPICS: [t for t in TOPICS if t in user_input[CONF_TOPICS]],
            CONF_PERIOD: user_input[CONF_PERIOD],
            CONF_MAX_ITEMS: int(user_input[CONF_MAX_ITEMS]),
            CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
            CONF_SOURCES: {},
            CONF_CUSTOM_FEEDS: {},
        }
        self._pending = list(self._options[CONF_TOPICS])

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Quellen für das nächste Thema wählen."""
        topic_key = self._pending[0]
        errors: dict[str, str] = {}
        defaults = self._defaults

        if user_input is not None:
            selected = list(user_input.get(CONF_SOURCES, []))
            urls = _split_urls(user_input.get(CONF_CUSTOM_FEEDS, ""))
            topic = TOPICS[topic_key]
            real = [k for k in selected if (s := topic.source(k)) and not s.boost_only]
            if not real and not urls:
                errors["base"] = "no_sources"
            for url in urls:
                if not url.startswith(("http://", "https://")):
                    errors[CONF_CUSTOM_FEEDS] = "invalid_url"
                    break
                try:
                    await async_fetch_feed(self.hass, custom_source(url))
                except FeedError:
                    errors[CONF_CUSTOM_FEEDS] = "invalid_feed"
                    break
            if not errors:
                self._options[CONF_SOURCES][topic_key] = selected
                self._options[CONF_CUSTOM_FEEDS][topic_key] = urls
                self._pending.pop(0)
                if not self._pending:
                    return self._finish()
                return await self.async_step_sources()
            defaults = {
                CONF_SOURCES: {topic_key: selected},
                CONF_CUSTOM_FEEDS: {topic_key: urls},
            }

        return self.async_show_form(  # type: ignore[attr-defined]
            step_id="sources",
            data_schema=_sources_schema(topic_key, defaults),
            description_placeholders={"topic": TOPICS[topic_key].name},
            errors=errors,
            last_step=len(self._pending) == 1,
        )

    def _finish(self) -> ConfigFlowResult:
        raise NotImplementedError


class NewsfeedConfigFlow(_NewsfeedFlowMixin, ConfigFlow, domain=DOMAIN):
    """Einrichtung der Newsfeed-Integration."""

    VERSION = 1

    def __init__(self) -> None:
        self._options = {}
        self._defaults = {}
        self._pending = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_TOPICS):
                errors["base"] = "no_topics"
            else:
                self._start(user_input)
                return await self.async_step_sources()
        return self.async_show_form(
            step_id="user",
            data_schema=_general_schema(user_input or {}),
            errors=errors,
        )

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(title="Newsfeed", data={}, options=self._options)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NewsfeedOptionsFlow()


class NewsfeedOptionsFlow(_NewsfeedFlowMixin, OptionsFlow):
    """Themen und Quellen nachträglich ändern."""

    def __init__(self) -> None:
        self._options = {}
        self._pending = []

    @property
    def _defaults(self) -> dict[str, Any]:  # type: ignore[override]
        return dict(self.config_entry.options)

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input.get(CONF_TOPICS):
                errors["base"] = "no_topics"
            else:
                self._start(user_input)
                return await self.async_step_sources()
        return self.async_show_form(
            step_id="init",
            data_schema=_general_schema(user_input or self._defaults),
            errors=errors,
        )

    def _finish(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._options)
