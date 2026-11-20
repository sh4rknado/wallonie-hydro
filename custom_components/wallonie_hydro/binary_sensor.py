"""Capteurs binaires d'alerte de niveau (vigilance, alerte, crue)."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ALERT_LEVEL,
    CONF_HIGH_LEVEL,
    CONF_WARN_LEVEL,
    DOMAIN,
)
from .coordinator import WallonieHydroCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les binaires d'alerte (seuils configurés dans les options)."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WallonieHydroCoordinator = data["coordinator"]

    if "H" not in coordinator.series:
        return

    opts = entry.options or {}
    async_add_entities(
        [
            LevelBinarySensor(
                coordinator, entry, "warn", opts.get(CONF_WARN_LEVEL, 1.0)
            ),
            LevelBinarySensor(
                coordinator, entry, "alert", opts.get(CONF_ALERT_LEVEL, 1.5)
            ),
            LevelBinarySensor(
                coordinator, entry, "high", opts.get(CONF_HIGH_LEVEL, 2.0)
            ),
        ]
    )


class LevelBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Vrai quand la hauteur dépasse le seuil configuré."""

    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(
        self,
        coordinator: WallonieHydroCoordinator,
        entry: ConfigEntry,
        level_key: str,
        threshold: float,
    ) -> None:
        super().__init__(coordinator)
        self._level_key = level_key
        self._threshold = threshold
        self._station_no = coordinator.station_no
        self._attr_unique_id = f"{DOMAIN}_{self._station_no}_{level_key}_level"
        self._entry = entry

    @property
    def translation_key(self) -> str:
        return f"{self._level_key}_level"

    @property
    def translation_placeholders(self) -> dict[str, str] | None:
        return {
            "station_name": self.coordinator.data.get("station_name")
            or self._station_no
        }

    @property
    def is_on(self) -> bool | None:
        value = self.coordinator.data.get("h_value")
        if value is None:
            return None
        return value >= self._threshold

    @property
    def icon(self) -> str:
        return {
            "warn": "mdi:water-alert",
            "alert": "mdi:home-flood",
            "high": "mdi:alert-octagon",
        }[self._level_key]

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "threshold_m": self._threshold,
            "current_level_m": self.coordinator.data.get("h_value"),
        }
