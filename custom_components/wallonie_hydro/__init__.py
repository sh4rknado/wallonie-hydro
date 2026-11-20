"""Intégration Wallonie Hydro : hauteur et débit des cours d'eau wallons."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WallonieHydroClient
from .const import CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import WallonieHydroCoordinator

_LOGGER = logging.getLogger(__name__)

# Chemin statique servant le fichier de la carte Lovelace. Enregistré une seule
# fois : permet à HA de répondre à /wallonie_hydro/wallonie-hydro-card.js sans
# que l'utilisateur ait à copier le fichier dans config/www/.
WWW_DIR = Path(__file__).parent / "www"
CARD_FILE = WWW_DIR / "wallonie-hydro-card.js"
CARD_URL = "/wallonie_hydro/wallonie-hydro-card.js"


async def _register_static_paths(hass: HomeAssistant) -> None:
    """Enregistre le chemin statique de la carte Lovelace (idempotent)."""
    if hass.data[DOMAIN].get("static_registered"):
        return

    # Sert le fichier carte exact que la ressource Lovelace charge.
    hass.http.register_static_path(CARD_URL, str(CARD_FILE), cache_headers=False)

    hass.data[DOMAIN]["static_registered"] = True
    _LOGGER.info("Carte Lovelace servie sur %s", CARD_URL)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Configure une station depuis une entrée de configuration."""
    client = WallonieHydroClient(async_get_clientsession(hass))
    coordinator = WallonieHydroCoordinator(
        hass,
        client,
        station_no=entry.data["station_no"],
        update_interval=entry.options.get(
            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Chemin statique pour la carte Lovelace (une seule fois)
    await _register_static_paths(hass)

    # Service WebSocket pour la carte Lovelace (une seule fois)
    from . import websocket_api

    if not hass.data[DOMAIN].get("ws_registered"):
        await websocket_api.async_setup(hass)
        hass.data[DOMAIN]["ws_registered"] = True
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Décharge une entrée de configuration."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recharge l'entrée quand les options changent."""
    await hass.config_entries.async_reload(entry.entry_id)
