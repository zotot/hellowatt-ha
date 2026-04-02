"""Config flow pour l'intégration Hellowatt."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResult

from .api import HellowattClient, HellowattAuthError, HellowattApiError
from .const import DOMAIN, CONF_HOME_ID

_LOGGER = logging.getLogger(__name__)


class HellowattConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration pour Hellowatt."""

    VERSION = 1

    def __init__(self) -> None:
        self._email: str = ""
        self._password: str = ""
        self._homes: list[dict] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL]
            password = user_input[CONF_PASSWORD]
            client = HellowattClient(email, password)
            try:
                await client.async_login()
                homes = await client.async_get_homes()

                if not homes:
                    errors["base"] = "no_homes"
                elif len(homes) == 1:
                    home = homes[0]
                    return self.async_create_entry(
                        title=f"Hellowatt – {home.get('address', email)}",
                        data={
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            CONF_HOME_ID: home["id"],
                        },
                    )
                else:
                    self._email = email
                    self._password = password
                    self._homes = homes
                    return await self.async_step_select_home()

            except HellowattAuthError:
                errors["base"] = "invalid_auth"
            except HellowattApiError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Erreur inattendue lors de la connexion Hellowatt")
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_EMAIL): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    async def async_step_select_home(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        if user_input is not None:
            home_id = int(user_input[CONF_HOME_ID])
            home = next((h for h in self._homes if h["id"] == home_id), {})
            return self.async_create_entry(
                title=f"Hellowatt – {home.get('address', self._email)}",
                data={
                    CONF_EMAIL: self._email,
                    CONF_PASSWORD: self._password,
                    CONF_HOME_ID: home_id,
                },
            )

        home_options = {
            str(h["id"]): h.get("address", f"Logement {h['id']}")
            for h in self._homes
        }

        return self.async_show_form(
            step_id="select_home",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOME_ID): vol.In(home_options),
                }
            ),
        )