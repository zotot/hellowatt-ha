"""Coordinator Hellowatt."""
from __future__ import annotations

import logging
from datetime import timedelta, date

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HellowattClient, HellowattApiError, HellowattAuthError
from .const import DOMAIN, SCAN_INTERVAL_HOURS

_LOGGER = logging.getLogger(__name__)

_DATE_FIELDS = ("datetime", "date", "start_date", "time_period")


def _kwh(rec: dict) -> float | None:
    kwh_detailed = rec.get("kwhDetailed", {})
    if isinstance(kwh_detailed, dict):
        val = kwh_detailed.get("Base")
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


def _cost(rec: dict) -> float | None:
    euros = rec.get("eurosDetailed", {})
    if isinstance(euros, dict):
        base = euros.get("Base", 0) or 0
        sub = euros.get("subscription", 0) or 0
        try:
            return round(float(base) + float(sub), 4)
        except (TypeError, ValueError):
            pass
    return None


def sum_kwh(daily_records: list[dict]) -> float | None:
    if not daily_records:
        return None
    total = 0.0
    found = False
    for rec in daily_records:
        val = _kwh(rec)
        if val is not None:
            total += val
            found = True
    return round(total, 3) if found else None


def sum_cost(daily_records: list[dict]) -> float | None:
    if not daily_records:
        return None
    total = 0.0
    found = False
    for rec in daily_records:
        val = _cost(rec)
        if val is not None:
            total += val
            found = True
    return round(total, 2) if found else None


def last_day_kwh(
    daily_records: list[dict], fallback: list[dict] | None = None
) -> float | None:
    records = daily_records if daily_records else (fallback or [])
    if not records:
        return None
    val = _kwh(records[-1])
    return round(val, 3) if val is not None else None


def last_day_date(
    daily_records: list[dict], fallback: list[dict] | None = None
) -> str | None:
    records = daily_records if daily_records else (fallback or [])
    if not records:
        return None
    last = records[-1]
    for f in _DATE_FIELDS:
        v = last.get(f)
        if v:
            return str(v)
    return None


def to_list(data) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "values" in data:
            values = data["values"]
            if values:
                return values
            error = data.get("error")
            if error:
                _LOGGER.debug(
                    "Erreur API Hellowatt: %s – %s",
                    error.get("identifier", ""),
                    error.get("message", ""),
                )
            return []
        return data.get("results", data.get("data", [data]))
    return []


class HellowattCoordinator(DataUpdateCoordinator):
    def __init__(
        self, hass: HomeAssistant, client: HellowattClient, home_id: int
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=SCAN_INTERVAL_HOURS),
        )
        self.client = client
        self.home_id = home_id

    async def _async_update_data(self) -> dict:
        try:
            today = date.today()
            yesterday = today - timedelta(days=1)
            first_day_this_month = today.replace(day=1)

            if today.month == 1:
                first_day_prev = date(today.year - 1, 12, 1)
            else:
                first_day_prev = date(today.year, today.month - 1, 1)

            elec_this = await self.client.async_get_elec_conso_daily(
                self.home_id, first_day_this_month
            )
            elec_prev = await self.client.async_get_elec_conso_daily(
                self.home_id, first_day_prev
            )
            courbe_yesterday = await self.client.async_get_elec_courbe(
                self.home_id, yesterday, today
            )
            contracts = await self.client.async_get_contracts(self.home_id)

            elec_this_list = to_list(elec_this)
            elec_prev_list = to_list(elec_prev)
            courbe_yesterday_list = to_list(courbe_yesterday)

            _LOGGER.debug(
                "Élec ce mois: %d jours, mois précédent: %d jours, courbe veille: %d tranches",
                len(elec_this_list),
                len(elec_prev_list),
                len(courbe_yesterday_list),
            )

            return {
                "elec_daily_this_month": elec_this_list,
                "elec_daily_prev_month": elec_prev_list,
                "elec_courbe_yesterday": courbe_yesterday_list,
                "contracts": contracts,
            }

        except HellowattAuthError as err:
            raise UpdateFailed(f"Erreur auth Hellowatt: {err}") from err
        except HellowattApiError as err:
            raise UpdateFailed(f"Erreur API Hellowatt: {err}") from err