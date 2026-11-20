"""Capteurs hauteur, débit et tendance d'une station."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SOURCE_NAME
from .coordinator import WallonieHydroCoordinator

_LOGGER = logging.getLogger(__name__)

ICON_H = "mdi:waves"
ICON_Q = "mdi:water-pump"
ICON_TEND = "mdi:trending-up"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Crée les capteurs de l'entrée."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: WallonieHydroCoordinator = data["coordinator"]
    entities: list[SensorEntity] = []

    if "H" in coordinator.series:
        entities.append(WallonieHydroSensor(coordinator, entry, "h"))
        if "H_tendency" in coordinator.series:
            entities.append(WallonieHydroTendencySensor(coordinator, entry, "h"))
    if "Q" in coordinator.series:
        entities.append(WallonieHydroSensor(coordinator, entry, "q"))
        if "Q_tendency" in coordinator.series:
            entities.append(WallonieHydroTendencySensor(coordinator, entry, "q"))

    async_add_entities(entities)


class WallonieHydroSensorBase(CoordinatorEntity, SensorEntity):
    """Base commune : device, disponibilité."""

    def __init__(
        self,
        coordinator: WallonieHydroCoordinator,
        entry: ConfigEntry,
        kind: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._kind = kind  # "h" ou "q"
        self._station_no = coordinator.station_no
        self._attr_unique_id = f"{DOMAIN}_{self._station_no}_{kind}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._station_no)},
            name=f"{coordinator.data.get('station_name', self._station_no)}"
            f" ({self._station_no})",
            manufacturer=MANUFACTURER,
            model="Station hydrométrique",
            configuration_url=f"{SOURCE_NAME.replace('https://', 'https://')}"
            f"/home/observations/hauteur.html?mode=graph&station="
            f"{self._station_no}&topic=H-hr",
        )


class WallonieHydroSensor(WallonieHydroSensorBase):
    """Hauteur d'eau (m) ou débit (m³/s) — valeur temps réel 10 min."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def translation_key(self) -> str:
        return "water_level" if self._kind == "h" else "discharge"

    @property
    def translation_placeholders(self) -> dict[str, str] | None:
        return {
            "station_name": self.coordinator.data.get("station_name")
            or self._station_no
        }

    @property
    def native_value(self) -> float | None:
        key = f"{self._kind}_value"
        return self.coordinator.data.get(key)

    @property
    def native_unit_of_measurement(self) -> str | None:
        return self.coordinator.data.get(f"{self._kind}_unit")

    @property
    def device_class(self) -> SensorDeviceClass | None:
        if self._kind == "h":
            return SensorDeviceClass.DISTANCE
        return None  # débit : pas de device_class standard adapté

    @property
    def icon(self) -> str:
        return ICON_H if self._kind == "h" else ICON_Q

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data
        attrs = {
            "station_no": self._station_no,
            "station_name": data.get("station_name"),
            "river_name": data.get("river_name"),
            "last_measurement": data.get(f"{self._kind}_timestamp"),
            "ts_path": data.get(f"{self._kind}_ts_path"),
            "attribution": "Données : SPW Wallonie — hydrometrie.wallonie.be",
        }
        # variation 1 h / 24 h à partir de l'historique 48 h
        history = data.get(f"history_{self._kind}") or []
        if history:
            latest_t, latest_v = history[-1]
            if isinstance(latest_t, str):
                latest_t = datetime.fromisoformat(latest_t)
            for label, hours in (("change_1h", 1), ("change_24h", 24)):
                threshold = latest_t - timedelta(hours=hours)
                ref = None
                for t, v in history:
                    if isinstance(t, str):
                        t = datetime.fromisoformat(t)
                    if t >= threshold:
                        ref = v
                        break
                if ref is not None:
                    attrs[f"{label}_value"] = round(latest_v - ref, 3)
                    attrs[f"{label}_pct"] = (
                        round((latest_v - ref) / ref * 100, 1) if ref else None
                    )
        return attrs


class WallonieHydroTendencySensor(WallonieHydroSensorBase):
    """Tendance officielle (m/h ou m³/s/h) calculée par le SPW."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, kind: str) -> None:
        super().__init__(coordinator, entry, f"{kind}_tendency")
        self._base_kind = kind

    @property
    def translation_key(self) -> str:
        return "water_level_tendency" if self._base_kind == "h" else "discharge_tendency"

    @property
    def translation_placeholders(self) -> dict[str, str] | None:
        return {
            "station_name": self.coordinator.data.get("station_name")
            or self._station_no
        }

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get(f"{self._base_kind}_tendency_value")

    @property
    def native_unit_of_measurement(self) -> str | None:
        base = self.coordinator.data.get(f"{self._base_kind}_unit") or ""
        return f"{base}/h"

    @property
    def icon(self) -> str:
        value = self.native_value
        if value is None:
            return "mdi:trending-neutral"
        if value > 0.001:
            return "mdi:trending-up"
        if value < -0.001:
            return "mdi:trending-down"
        return "mdi:trending-neutral"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "last_measurement": self.coordinator.data.get(
                f"{self._base_kind}_tendency_timestamp"
            ),
        }
