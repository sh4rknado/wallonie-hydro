"""Config flow : sélection d'une station du portail hydrométrique wallon."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import (
    WallonieHydroApiConnectionError,
    WallonieHydroApiError,
    WallonieHydroClient,
    WallonieHydroStationError,
)
from .const import (
    CONF_STATION,
    CONF_UPDATE_INTERVAL,
    CONF_ALERT_LEVEL,
    CONF_WARN_LEVEL,
    CONF_HIGH_LEVEL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


async def _get_client(hass) -> WallonieHydroClient:
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    session = async_get_clientsession(hass)
    return WallonieHydroClient(session)


class WallonieHydroConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration d'une station."""

    VERSION = 1

    def __init__(self) -> None:
        self._stations: list[dict[str, Any]] = []
        self._selected: dict[str, Any] | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Étape 1 : recherche et choix de la station."""
        errors: dict[str, str] = {}

        if user_input is not None:
            station_no = str(user_input[CONF_STATION]).strip()
            try:
                client = await _get_client(self.hass)
                station = await client.async_get_station(station_no)
                if station is None:
                    errors["base"] = "invalid_station"
                else:
                    # vérifie que la station publie bien H et/ou Q
                    await client.async_find_series(station_no)
                    await self.async_set_unique_id(f"{DOMAIN}_{station_no}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"{station['station_name']} ({station_no})",
                        data={"station_no": station_no},
                    )
            except WallonieHydroStationError as err:
                # station inconnue OU sans série H/Q
                if "introuvable" in str(err):
                    errors["base"] = "invalid_station"
                else:
                    errors["base"] = "no_series"
            except WallonieHydroApiConnectionError:
                errors["base"] = "cannot_connect"
            except WallonieHydroApiError:
                errors["base"] = "api_error"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"

        # charge la liste des stations pour le datalist
        try:
            client = await _get_client(self.hass)
            self._stations = await client.async_get_stations()
        except (WallonieHydroApiError, aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Impossible de lister les stations : %s", err)

        stations_by_no = {s["station_no"]: s for s in self._stations}

        schema = vol.Schema(
            {
                vol.Required(CONF_STATION): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "nb_stations": str(len(stations_by_no)),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WallonieHydroOptionsFlow:
        return WallonieHydroOptionsFlow(config_entry)


class WallonieHydroOptionsFlow(config_entries.OptionsFlow):
    """Options : intervalle de mise à jour et seuils d'alerte (m)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            warn = user_input.get(CONF_WARN_LEVEL)
            alert = user_input.get(CONF_ALERT_LEVEL)
            high = user_input.get(CONF_HIGH_LEVEL)
            levels = [x for x in (warn, alert, high) if x is not None]
            if levels != sorted(levels):
                errors["base"] = "levels_order"
            else:
                return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options or {}
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_UPDATE_INTERVAL,
                    default=opts.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
                vol.Optional(
                    CONF_WARN_LEVEL, default=opts.get(CONF_WARN_LEVEL, 1.0)
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_ALERT_LEVEL, default=opts.get(CONF_ALERT_LEVEL, 1.5)
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_HIGH_LEVEL, default=opts.get(CONF_HIGH_LEVEL, 2.0)
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
