"""Coordonnateur de données pour l'intégration Wallonie Hydro."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WallonieHydroClient

_LOGGER = logging.getLogger(__name__)

HISTORY_HOURS = 48  # profondeur d'historique conservée pour la carte


class WallonieHydroCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Met à jour hauteur, débit, tendances et historique 48 h d'une station."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: WallonieHydroClient,
        station_no: str,
        update_interval: int = 10,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"wallonie_hydro_{station_no}",
            update_interval=timedelta(minutes=update_interval),
        )
        self.client = client
        self.station_no = station_no
        self.series: dict[str, dict[str, Any]] = {}

    async def _async_setup(self) -> None:
        """Résout les séries officielles de la station une seule fois."""
        self.series = await self.client.async_find_series(self.station_no)
        _LOGGER.debug(
            "Séries résolues pour %s : %s",
            self.station_no,
            {k: v.get("ts_path") for k, v in self.series.items()},
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if not self.series:
                await self._async_setup()

            data: dict[str, Any] = {
                "station_no": self.station_no,
                "updated_at": datetime.now().isoformat(),
            }

            # Historique 48 h (hauteur + débit) — une seule requête combinée
            ts_ids = []
            if "H" in self.series:
                ts_ids.append(self.series["H"]["ts_id"])
            if "Q" in self.series:
                ts_ids.append(self.series["Q"]["ts_id"])

            if ts_ids:
                combined = await self.client.async_get_timeseries_values_multi(
                    ts_ids, period=f"PT{HISTORY_HOURS}H"
                )
                if "H" in self.series:
                    data["history_h"] = combined.get(self.series["H"]["ts_id"], [])
                if "Q" in self.series:
                    data["history_q"] = combined.get(self.series["Q"]["ts_id"], [])

            # Valeurs courantes + tendances
            for key in ("H", "Q", "H_tendency", "Q_tendency"):
                if key in self.series:
                    latest = await self.client.async_get_latest(
                        self.series[key]["ts_id"]
                    )
                    if latest is not None:
                        data[f"{key.lower()}_value"] = latest[1]
                        data[f"{key.lower()}_timestamp"] = latest[0].isoformat()
                        if key in ("H", "Q"):
                            data[f"{key.lower()}_unit"] = self.series[key].get(
                                "ts_unitsymbol"
                            )
                            data[f"{key.lower()}_ts_path"] = self.series[key].get(
                                "ts_path"
                            )

            # Métadonnées de station (nom, rivière) — mises en cache
            station = await self.client.async_get_station(self.station_no)
            if station:
                data["station_name"] = station.get("station_name")
                data["river_name"] = station.get("river_name")
                data["latitude"] = station.get("station_latitude")
                data["longitude"] = station.get("station_longitude")

            return data
        except Exception as err:
            raise UpdateFailed(f"Erreur de mise à jour : {err}") from err
