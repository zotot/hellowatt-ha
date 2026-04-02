"""Client API pour Hellowatt."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .const import BASE_URL, API_VERSION

_LOGGER = logging.getLogger(__name__)

LOGIN_PAGE_URL = "https://www.hellowatt.fr/mon-compte/me-connecter"
LOGIN_POST_URL = "https://www.hellowatt.fr/accounts/login/"
TZ_PARIS = ZoneInfo("Europe/Paris")


def _fmt_date(d: date) -> str:
    dt = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=TZ_PARIS)
    offset = dt.strftime("%z")
    return f"{d.isoformat()}T00:00:00{offset[:3]}:{offset[3:]}"


class HellowattAuthError(Exception):
    pass


class HellowattApiError(Exception):
    pass


class HellowattClient:
    def __init__(self, email: str, password: str) -> None:
        self._email = email
        self._password = password
        self._session: aiohttp.ClientSession | None = None
        self._csrf_token: str = ""

    def _headers(self) -> dict:
        return {
            "accept": f"application/json; version={API_VERSION}",
            "content-type": "application/json",
            "is-on-native-app": "false",
            "x-csrftoken": self._csrf_token,
            "x-requested-with": "XMLHttpRequest",
            "x-app-version": "",
            "origin": "https://www.hellowatt.fr",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
            "referer": "https://www.hellowatt.fr/mon-compte/",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                cookie_jar=aiohttp.CookieJar(unsafe=True)
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def async_login(self) -> None:
        session = await self._get_session()
        async with session.get(
            f"{BASE_URL}/user",
            headers={
                "accept": f"application/json; version={API_VERSION}",
                "content-type": "application/json",
                "is-on-native-app": "false",
                "x-csrftoken": "",
                "user-agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/146.0.0.0 Safari/537.36"
                ),
                "referer": "https://www.hellowatt.fr/mon-compte/",
            }
        ) as resp:
            _LOGGER.debug("GET /api/user status: %s", resp.status)
            csrf = session.cookie_jar.filter_cookies(
                "https://www.hellowatt.fr"
            ).get("csrftoken")
            if csrf:
                self._csrf_token = csrf.value
                _LOGGER.debug("CSRF depuis cookie : %s…", self._csrf_token[:10])
            else:
                _LOGGER.warning("CSRF token introuvable")

        form_headers = {
            "content-type": "application/x-www-form-urlencoded",
            "accept": f"application/json; version={API_VERSION}",
            "x-csrftoken": self._csrf_token,
            "x-requested-with": "XMLHttpRequest",
            "x-app-version": "",
            "origin": "https://www.hellowatt.fr",
            "referer": LOGIN_PAGE_URL,
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/146.0.0.0 Safari/537.36"
            ),
        }

        async with session.post(
            LOGIN_POST_URL,
            data={"login": self._email, "password": self._password},
            headers=form_headers,
        ) as resp:
            body = await resp.text()
            _LOGGER.debug("Login status: %s, body: %s", resp.status, body[:200])
            if resp.status == 401:
                raise HellowattAuthError("Email ou mot de passe incorrect")
            if resp.status not in (200, 201):
                raise HellowattAuthError(f"Échec login HTTP {resp.status}")
            if '"value": null' in body and '"errors": []' in body:
                raise HellowattAuthError("Email ou mot de passe incorrect")
            csrf = session.cookie_jar.filter_cookies(
                "https://www.hellowatt.fr"
            ).get("csrftoken")
            if csrf:
                self._csrf_token = csrf.value
            _LOGGER.debug("Connexion Hellowatt réussie")

    async def _async_get(self, endpoint: str, params: dict | None = None) -> Any:
        session = await self._get_session()
        url = f"{BASE_URL}{endpoint}"
        try:
            async with session.get(url, headers=self._headers(), params=params) as resp:
                if resp.status == 401:
                    await self.async_login()
                    async with session.get(url, headers=self._headers(), params=params) as resp2:
                        resp2.raise_for_status()
                        return await resp2.json()
                resp.raise_for_status()
                return await resp.json()
        except aiohttp.ClientError as err:
            raise HellowattApiError(f"Erreur réseau {url}: {err}") from err

    async def async_get_user(self) -> dict:
        return await self._async_get("/user")

    async def async_get_homes(self) -> list[dict]:
        return await self._async_get("/homes")

    async def async_get_contracts(self, home_id: int) -> list[dict]:
        return await self._async_get(f"/homes/{home_id}/contracts")

    async def async_get_elec_conso_daily(self, home_id: int, start: date) -> Any:
        params = {"startDate": _fmt_date(start)}
        return await self._async_get(
            f"/homes/{home_id}/sge_measures/conso_daily", params=params
        )

    async def async_get_elec_courbe(
        self, home_id: int, start: date, end: date
    ) -> Any:
        """Courbe de charge 30 min pour une plage de dates."""
        params = {
            "startDate": _fmt_date(start),
            "endDate": _fmt_date(end),
        }
        return await self._async_get(
            f"/homes/{home_id}/sge_measures/courbe", params=params
        )