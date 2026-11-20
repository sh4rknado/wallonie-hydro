"""Constantes de l'intégration Wallonie Hydro."""

from __future__ import annotations

import logging

DOMAIN = "wallonie_hydro"
PLATFORMS = ["sensor", "binary_sensor"]

CONF_STATION = "station_no"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_WARN_LEVEL = "warn_level"
CONF_ALERT_LEVEL = "alert_level"
CONF_HIGH_LEVEL = "high_level"

DEFAULT_UPDATE_INTERVAL = 10  # minutes

MANUFACTURER = "SPW Wallonie (hydrometrie.wallonie.be)"
SOURCE_NAME = "hydrometrie.wallonie.be"

LOGGER = logging.getLogger(__package__)
