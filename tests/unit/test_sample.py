from __future__ import annotations

from types import SimpleNamespace

import pytest

import src


@pytest.mark.unit
def test_pytest_framework_smoke() -> None:
    assert src.__doc__ == "Verdecora albaranes source package."
    assert 2 + 2 == 4


@pytest.mark.unit
def test_shared_fixtures_load_correctly(
    sample_albaran_data: dict[str, object],
    sample_po_data: dict[str, object],
    bc_mcp_clients: SimpleNamespace,
    cosmos_db_client: SimpleNamespace,
    acs_email_client: SimpleNamespace,
    service_bus_client: SimpleNamespace,
) -> None:
    assert sample_albaran_data["numero_albaran"] == "A-2026-001234"
    assert sample_albaran_data["extracted"]["confianza_global"] == pytest.approx(0.97)
    assert sample_po_data["number"] == sample_albaran_data["ref_pedido_bc"]
    assert bc_mcp_clients.read.get_purchase_order is not None
    assert bc_mcp_clients.write.post_purchase_receipt is not None
    assert cosmos_db_client.get_database_client() is not None
    assert acs_email_client.begin_send().result()["status"] == "Succeeded"
    assert service_bus_client.get_topic_sender() is not None
