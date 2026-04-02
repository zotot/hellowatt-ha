"""Constants for the Hellowatt integration."""

DOMAIN = "hellowatt"
BASE_URL = "https://www.hellowatt.fr/api"
API_VERSION = "1.54"

CONF_HOME_ID = "home_id"

ENDPOINT_USER = "/user"
ENDPOINT_HOMES = "/homes"
ENDPOINT_SGE_CONSO = "/homes/{home_id}/sge_measures/conso_daily"
ENDPOINT_ADICT_CONSO = "/homes/{home_id}/adict_measures/conso_daily"
ENDPOINT_CONTRACTS = "/homes/{home_id}/contracts"
ENDPOINT_RANK = "/homes/{home_id}/rank/elec/monthly/{year}/{month}"

SCAN_INTERVAL_HOURS = 4