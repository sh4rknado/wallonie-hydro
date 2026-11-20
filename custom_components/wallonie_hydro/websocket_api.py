"""Service WebSocket : expose l'historique 48 h aux cartes Lovelace.

Message type: wallonie_hydro/history
Payload: {"station_no": "L6710", "hours": 48}
Réponse: {"history_h": [[iso, val], ...], "history_q": [...], "unit_h": "m", ...}
"""

from __future__ import annotations

import logging

import voluptuous as vol

import homeassistant.components.websocket_api as ws
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

WS_TYPE_HISTORY = "wallonie_hydro/history"


@ws.websocket_command(
    {
        vol.Required("type"): WS_TYPE_HISTORY,
        vol.Required("station_no"): str,
        vol.Optional("hours", default=48): int,
    }
)
@ws.async_response
async def websocket_history(
    hass: HomeAssistant,
    connection: ws.ActiveConnection,
    msg: dict,
) -> None:
    """Renvoie l'historique d'une station depuis le coordinateur (cache)."""
    station_no = msg["station_no"]
    hours = max(1, min(int(msg["hours"]), 48))

    for entry_data in hass.data.get(DOMAIN, {}).values():
        coordinator = entry_data["coordinator"]
        if coordinator.station_no != station_no:
            continue

        history_h = _window(coordinator.data.get("history_h"), hours)
        history_q = _window(coordinator.data.get("history_q"), hours)
        connection.send_result(
            msg["id"],
            {
                "station_no": station_no,
                "station_name": coordinator.data.get("station_name"),
                "river_name": coordinator.data.get("river_name"),
                "history_h": history_h,
                "history_q": history_q,
                "unit_h": coordinator.data.get("h_unit"),
                "unit_q": coordinator.data.get("q_unit"),
                "h_ts_path": coordinator.data.get("h_ts_path"),
                "q_ts_path": coordinator.data.get("q_ts_path"),
                "last_updated": coordinator.data.get("updated_at"),
            },
        )
        return

    connection.send_error(msg["id"], "station_not_found", f"Station {station_no} inconnue")


def _window(history, hours: int):
    """Garde les points plus récents que `hours` heures (iso-serialisés).

    Gère les timestamps ISO avec ou sans fuseau (naïf vs averti).
    """
    if not history:
        return []
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    out = []
    for point in history:
        t, v = point
        if isinstance(t, str):
            t = datetime.fromisoformat(t)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        elif t.tzinfo is not None:
            t = t.astimezone(timezone.utc)
        if t >= cutoff:
            out.append([t.isoformat(), round(v, 4)])
    return out


async def async_setup(hass: HomeAssistant) -> None:
    """Enregistre les commandes WebSocket."""
    ws.async_register_command(hass, websocket_history)
