"""Intégration Home Assistant pour Hellowatt."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .api import HellowattClient, HellowattAuthError, HellowattApiError
from .const import DOMAIN, CONF_HOME_ID
from .coordinator import HellowattCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    email = entry.data[CONF_EMAIL]
    password = entry.data[CONF_PASSWORD]
    home_id = entry.data[CONF_HOME_ID]

    client = HellowattClient(email, password)

    try:
        await client.async_login()
    except HellowattAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except HellowattApiError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = HellowattCoordinator(hass, client, home_id)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: HellowattCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.close()
    return unload_ok