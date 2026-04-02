"""Capteurs Hellowatt pour Home Assistant."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, CURRENCY_EURO
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import (
    HellowattCoordinator,
    sum_kwh,
    sum_cost,
    last_day_kwh,
    last_day_date,
    _kwh,
    _cost,
)


@dataclass
class HellowattSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any] | None = None


def _last_day_cost(
    daily_records: list[dict], fallback: list[dict] | None = None
) -> float | None:
    records = daily_records if daily_records else (fallback or [])
    if not records:
        return None
    val = _cost(records[-1])
    return round(val, 2) if val is not None else None


def _courbe_total_kwh(data: dict) -> float | None:
    return sum_kwh(data.get("elec_courbe_yesterday", []))


def _courbe_total_cost(data: dict) -> float | None:
    return sum_cost(data.get("elec_courbe_yesterday", []))


SENSOR_DESCRIPTIONS: tuple[HellowattSensorDescription, ...] = (
    # ── Mois en cours ────────────────────────────────────────────────────
    HellowattSensorDescription(
        key="elec_consumption_this_month",
        name="Hellowatt Conso Élec Mois",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:flash",
        value_fn=lambda d: sum_kwh(d.get("elec_daily_this_month", [])),
    ),
    HellowattSensorDescription(
        key="elec_cost_this_month",
        name="Hellowatt Coût Élec Mois",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:currency-eur",
        value_fn=lambda d: sum_cost(d.get("elec_daily_this_month", [])),
    ),
    # ── Mois précédent ───────────────────────────────────────────────────
    HellowattSensorDescription(
        key="elec_consumption_prev_month",
        name="Hellowatt Conso Élec Mois Précédent",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:flash",
        value_fn=lambda d: sum_kwh(d.get("elec_daily_prev_month", [])),
    ),
    HellowattSensorDescription(
        key="elec_cost_prev_month",
        name="Hellowatt Coût Élec Mois Précédent",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:currency-eur",
        value_fn=lambda d: sum_cost(d.get("elec_daily_prev_month", [])),
    ),
    # ── Dernier jour kWh ─────────────────────────────────────────────────
    HellowattSensorDescription(
        key="elec_last_day_kwh",
        name="Hellowatt Élec Dernier Jour",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:flash-outline",
        value_fn=lambda d: last_day_kwh(
            d.get("elec_daily_this_month", []),
            d.get("elec_daily_prev_month", [])
        ),
    ),
    # ── Dernier jour € ───────────────────────────────────────────────────
    HellowattSensorDescription(
        key="elec_last_day_cost",
        name="Hellowatt Coût Élec Dernier Jour",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:currency-eur",
        value_fn=lambda d: _last_day_cost(
            d.get("elec_daily_this_month", []),
            d.get("elec_daily_prev_month", [])
        ),
    ),
    # ── Courbe 30 min veille kWh ─────────────────────────────────────────
    HellowattSensorDescription(
        key="elec_courbe_yesterday_kwh",
        name="Hellowatt Élec Veille Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:chart-line",
        value_fn=_courbe_total_kwh,
    ),
    # ── Courbe 30 min veille € ───────────────────────────────────────────
    HellowattSensorDescription(
        key="elec_courbe_yesterday_cost",
        name="Hellowatt Coût Élec Veille",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:currency-eur",
        value_fn=_courbe_total_cost,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: HellowattCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HellowattSensor(coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class HellowattSensor(CoordinatorEntity[HellowattCoordinator], SensorEntity):
    entity_description: HellowattSensorDescription

    def __init__(
        self,
        coordinator: HellowattCoordinator,
        description: HellowattSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"hellowatt_{coordinator.home_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(coordinator.home_id))},
            "name": "Hellowatt",
            "manufacturer": "Hellowatt",
            "model": "Suivi énergie",
            "entry_type": "service",
        }

    @property
    def native_value(self) -> Any:
        if self.coordinator.data is None:
            return None
        if self.entity_description.value_fn is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        if self.coordinator.data is None:
            return attrs

        key = self.entity_description.key

        if "courbe" in key:
            records = self.coordinator.data.get("elec_courbe_yesterday", [])
            if records:
                attrs["nb_tranches"] = len(records)
                attrs["granularite_minutes"] = records[0].get("measureTimeGap", 30)
                attrs["premiere_tranche"] = records[0].get("datetime", "")
                attrs["derniere_tranche"] = records[-1].get("datetime", "")
                attrs["tranches"] = [
                    {
                        "datetime": r.get("datetime", ""),
                        "kwh": _kwh(r),
                        "eur": _cost(r),
                    }
                    for r in records
                ]
        else:
            records = self.coordinator.data.get("elec_daily_this_month", [])
            fallback = self.coordinator.data.get("elec_daily_prev_month", [])
            last = last_day_date(records, fallback)
            if last:
                attrs["last_measure_date"] = last
            if "this_month" in key:
                attrs["detail_jours"] = [
                    {
                        "datetime": r.get("datetime", ""),
                        "kwh": _kwh(r),
                        "eur": _cost(r),
                    }
                    for r in records
                ]

        return attrs