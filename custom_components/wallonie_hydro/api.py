"""Client pour l'API KIWIS (Kisters) du portail hydrométrique wallon.

Utilise le même service que https://hydrometrie.wallonie.be :
https://hydrometrie.wallonie.be/services/KiWIS/KiWIS
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://hydrometrie.wallonie.be/services/KiWIS/KiWIS"
PORTAL_URL = "https://hydrometrie.wallonie.be"

# Groupes de séries officiels utilisés par le portail (topic H-hr / Q-hr)
GROUP_H = 1962373      # WEBPortal_ESurf-Hauteur
GROUP_Q = 1962340      # WEBPortal_ESurf-Debit
GROUP_H_TENDENCY = 1962392  # WEBPortal_ESurf-HauteurTendency
GROUP_Q_TENDENCY = 1962354  # WEBPortal_ESurf-DebitTendency
STATION_GROUP_ACTIVE = 3617241  # WEBPortal_ESurf-StationsActives

DEFAULT_TIMEOUT = 30


class WallonieHydroApiError(Exception):
    """Erreur renvoyée par le service KIWIS."""


class WallonieHydroApiConnectionError(WallonieHydroApiError):
    """Impossible de joindre le service."""


class WallonieHydroStationError(WallonieHydroApiError):
    """Station inconnue ou sans série H/Q."""


def _kiwis_params(request: str, **extra: Any) -> dict[str, str]:
    """Construit les paramètres communs d'une requête KIWIS."""
    params = {
        "request": request,
        "service": "kisters",
        "type": "queryServices",
        "datasource": "0",
        "format": "json",
    }
    params.update({k: str(v) for k, v in extra.items() if v is not None})
    return params


class WallonieHydroClient:
    """Client asynchrone minimal pour le service KIWIS wallon."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str = BASE_URL,
    ) -> None:
        self._session = session
        self._base_url = base_url

    async def _get(self, params: dict[str, str]) -> Any:
        """Exécute une requête KIWIS et décode la réponse JSON."""
        try:
            async with self._session.get(
                self._base_url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT),
                headers={"User-Agent": "home-assistant wallonie_hydro/1.0"},
            ) as resp:
                if resp.status != 200:
                    raise WallonieHydroApiConnectionError(
                        f"HTTP {resp.status} du service KIWIS"
                    )
                data = await resp.json(content_type=None)
        except (TimeoutError, asyncio.TimeoutError) as err:
            raise WallonieHydroApiConnectionError(
                "Délai dépassé en joignant hydrometrie.wallonie.be"
            ) from err
        except aiohttp.ClientError as err:
            raise WallonieHydroApiConnectionError(
                f"Erreur de connexion : {err}"
            ) from err

        if isinstance(data, dict) and data.get("type") == "error":
            raise WallonieHydroApiError(
                f"KIWIS: {data.get('code')} - {data.get('message')}"
            )
        return data

    # ------------------------------------------------------------------
    # Référentiel
    # ------------------------------------------------------------------

    async def async_get_stations(self) -> list[dict[str, Any]]:
        """Liste des stations actives (eaux de surface) avec rivière et position."""
        data = await self._get(
            _kiwis_params(
                "GetStationList",
                stationgroup_id=STATION_GROUP_ACTIVE,
                returnfields="station_no,station_name,river_name,"
                "station_latitude,station_longitude",
            )
        )
        if not isinstance(data, list) or len(data) < 2:
            return []
        header, rows = data[0], data[1:]
        return [dict(zip(header, row)) for row in rows]

    async def async_get_station(self, station_no: str) -> dict[str, Any] | None:
        """Détail d'une station par son numéro (ex. L6710).

        Lève WallonieHydroStationError si le numéro est inconnu
        (le service renvoie alors une liste vide, sans ligne de données).
        """
        data = await self._get(
            _kiwis_params(
                "GetStationList",
                station_no=station_no,
                returnfields="station_no,station_name,river_name,"
                "station_latitude,station_longitude",
            )
        )
        if not isinstance(data, list) or len(data) < 2:
            raise WallonieHydroStationError(
                f"Station « {station_no} » introuvable sur hydrometrie.wallonie.be. "
                "Vérifiez le numéro dans l'URL du portail après avoir cliqué "
                "la station sur la carte."
            )
        header, rows = data[0], data[1:]
        for row in rows:
            return dict(zip(header, row))
        raise WallonieHydroStationError(f"Station « {station_no} » introuvable.")

    async def async_find_series(self, station_no: str) -> dict[str, dict[str, Any]]:
        """Résout les séries officielles H / Q / tendances d'une station.

        Retourne {"H": {...}, "Q": {...}, "H_tendency": {...}, "Q_tendency": {...}}
        (clés absentes si la station ne mesure pas la grandeur).
        """
        result: dict[str, dict[str, Any]] = {}
        tasks = {
            "H": GROUP_H,
            "Q": GROUP_Q,
            "H_tendency": GROUP_H_TENDENCY,
            "Q_tendency": GROUP_Q_TENDENCY,
        }
        for key, group in tasks.items():
            try:
                data = await self._get(
                    _kiwis_params(
                        "GetTimeseriesList",
                        station_no=station_no,
                        timeseriesgroup_id=group,
                        returnfields="ts_id,ts_path,ts_name,"
                        "parametertype_name,ts_unitsymbol",
                    )
                )
            except WallonieHydroApiError:
                continue
            if isinstance(data, list) and len(data) >= 2:
                header, rows = data[0], data[1:]
                for row in rows:
                    entry = dict(zip(header, row))
                    entry["ts_id"] = str(entry["ts_id"])
                    result[key] = entry
                    break
        if "H" not in result and "Q" not in result:
            raise WallonieHydroStationError(
                f"La station {station_no} ne publie pas de série hauteur/débit "
                "sur le portail (elle est peut-être inactive ou pluvio seulement)."
            )
        return result

    # ------------------------------------------------------------------
    # Observations
    # ------------------------------------------------------------------

    async def async_get_timeseries_values(
        self,
        ts_id: str,
        period: str = "PT48H",
        metadata: bool = True,
    ) -> dict[str, Any]:
        """Récupère les valeurs d'une série.

        Le service n'accepte que `Timestamp,Value` dans returnfields ;
        les métadonnées (unité, nom) sont renvoyées automatiquement via
        metadata=true.

        Retourne {"data": [(datetime, float), ...], "unit": "m", "name": ...}
        """
        params = _kiwis_params(
            "GetTimeseriesValues",
            ts_id=ts_id,
            period=period,
            returnfields="Timestamp,Value",
            metadata="true" if metadata else "false",
        )
        data = await self._get(params)
        return self._parse_timeseries_response(data, metadata)

    async def async_get_timeseries_values_multi(
        self,
        ts_ids: list[str],
        period: str = "P2D",
    ) -> dict[str, list[tuple[datetime, float]]]:
        """Récupère plusieurs séries en une requête (ts_id séparés par virgule).

        Retourne {ts_id: [(datetime, float), ...], ...}
        """
        params = _kiwis_params(
            "GetTimeseriesValues",
            ts_id=",".join(ts_ids),
            period=period,
            returnfields="Timestamp,Value",
            metadata="false",
        )
        data = await self._get(params)
        result: dict[str, list[tuple[datetime, float]]] = {}
        if not isinstance(data, list):
            return result
        for tsv in data:
            ts_id = str(tsv.get("ts_id", ""))
            points: list[tuple[datetime, float]] = []
            for row in tsv.get("data", []):
                if row[1] is None:
                    continue
                try:
                    ts = datetime.fromisoformat(row[0])
                except ValueError:
                    continue
                points.append((ts, float(row[1])))
            result[ts_id] = points
        return result

    @staticmethod
    def _parse_timeseries_response(
        data: Any, metadata: bool
    ) -> dict[str, Any]:
        if not isinstance(data, list) or not data:
            return {"data": [], "unit": None, "name": None}
        tsv = data[0]
        points: list[tuple[datetime, float]] = []
        for row in tsv.get("data", []):
            if row[1] is None:
                continue
            try:
                ts = datetime.fromisoformat(row[0])
            except ValueError:
                continue
            points.append((ts, float(row[1])))
        return {
            "data": points,
            "unit": tsv.get("ts_unitsymbol") if metadata else None,
            "name": tsv.get("ts_name") if metadata else None,
        }

    async def async_get_latest(self, ts_id: str) -> tuple[datetime, float] | None:
        """Dernière valeur d'une série (dernier point non nul)."""
        res = await self.async_get_timeseries_values(ts_id, period="P1D")
        return res["data"][-1] if res["data"] else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_period_hours(period: str) -> int:
    """Convertit une durée ISO-8601 simple (PT48H, P2D...) en heures."""
    import re

    m = re.fullmatch(r"P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?)?", period)
    if not m:
        return 48
    days = int(m.group(1) or 0)
    hours = int(m.group(2) or 0)
    minutes = int(m.group(3) or 0)
    return days * 24 + hours + minutes // 60


def period_for_hours(hours: int) -> str:
    """Convertit des heures en durée ISO-8601 (PTxH)."""
    return f"PT{int(hours)}H"
