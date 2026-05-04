from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_SERVICE_ENV_VARS = {
    "bc": "RUN_BC_INTEGRATION",
    "cosmos": "RUN_COSMOS_INTEGRATION",
    "acs": "RUN_ACS_INTEGRATION",
    "service_bus": "RUN_SERVICEBUS_INTEGRATION",
}


def _service_enabled(service_name: str) -> bool:
    value = os.getenv(_SERVICE_ENV_VARS[service_name], "")
    return value.lower() in {"1", "true", "yes", "on"}


requires_bc = pytest.mark.skipif(
    not _service_enabled("bc"),
    reason="Business Central integration unavailable. Set RUN_BC_INTEGRATION=1 to enable.",
)
requires_cosmos = pytest.mark.skipif(
    not _service_enabled("cosmos"),
    reason="Cosmos DB integration unavailable. Set RUN_COSMOS_INTEGRATION=1 to enable.",
)
requires_acs = pytest.mark.skipif(
    not _service_enabled("acs"),
    reason="ACS Email integration unavailable. Set RUN_ACS_INTEGRATION=1 to enable.",
)
requires_service_bus = pytest.mark.skipif(
    not _service_enabled("service_bus"),
    reason="Service Bus integration unavailable. Set RUN_SERVICEBUS_INTEGRATION=1 to enable.",
)


@pytest.fixture(scope="session")
def integration_service_flags() -> dict[str, bool]:
    return {service: _service_enabled(service) for service in _SERVICE_ENV_VARS}
