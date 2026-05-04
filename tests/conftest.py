from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run tests marked as integration.",
    )
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run tests marked as e2e.",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
    skip_e2e = pytest.mark.skip(reason="need --run-e2e option to run")
    invocation_args = [str(arg).replace("\\", "/") for arg in config.invocation_params.args]
    explicit_integration_selection = any("tests/integration" in arg for arg in invocation_args)
    explicit_e2e_selection = any("tests/e2e" in arg for arg in invocation_args)
    run_integration = config.getoption("--run-integration") or explicit_integration_selection
    run_e2e = config.getoption("--run-e2e") or explicit_e2e_selection

    for item in items:
        item_path = Path(str(item.path))
        if "integration" in item_path.parts:
            item.add_marker(pytest.mark.integration)
        if "e2e" in item_path.parts:
            item.add_marker(pytest.mark.e2e)
        if "integration" in item.keywords and not run_integration:
            item.add_marker(skip_integration)
        if "e2e" in item.keywords and not run_e2e:
            item.add_marker(skip_e2e)


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture(scope="session")
def sample_albaran_data() -> dict[str, object]:
    return _load_fixture("sample_albaran.json")


@pytest.fixture(scope="session")
def sample_po_data() -> dict[str, object]:
    return _load_fixture("sample_po.json")


@pytest.fixture()
def bc_mcp_read_client(sample_po_data: dict[str, object]) -> SimpleNamespace:
    first_line = sample_po_data["purchaseLines"][0]
    return SimpleNamespace(
        get_purchase_order=AsyncMock(return_value=sample_po_data),
        get_purchase_order_lines=AsyncMock(return_value=sample_po_data["purchaseLines"]),
        get_vendor=AsyncMock(
            return_value={
                "number": sample_po_data["vendorNumber"],
                "displayName": sample_po_data["vendorName"],
            }
        ),
        get_item=AsyncMock(
            return_value={
                "number": first_line["lineObjectNumber"],
                "displayName": first_line["description"],
            }
        ),
    )


@pytest.fixture()
def bc_mcp_write_client() -> SimpleNamespace:
    return SimpleNamespace(
        post_purchase_receipt=AsyncMock(return_value={"status": "posted", "posted_receipt_id": "PR-2026-000123"})
    )


@pytest.fixture()
def bc_mcp_clients(bc_mcp_read_client: SimpleNamespace, bc_mcp_write_client: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(read=bc_mcp_read_client, write=bc_mcp_write_client)


@pytest.fixture()
def cosmos_db_client(sample_albaran_data: dict[str, object]) -> SimpleNamespace:
    container = SimpleNamespace(
        read_item=AsyncMock(return_value=sample_albaran_data),
        upsert_item=AsyncMock(side_effect=lambda item, **_: item),
        patch_item=AsyncMock(return_value={"status": "patched"}),
        query_items=MagicMock(return_value=[sample_albaran_data]),
    )
    database = SimpleNamespace(get_container_client=MagicMock(return_value=container))
    return SimpleNamespace(get_database_client=MagicMock(return_value=database), close=AsyncMock())


@pytest.fixture()
def acs_email_client() -> SimpleNamespace:
    poller = MagicMock()
    poller.result.return_value = {
        "id": "acs-msg-001",
        "status": "Succeeded",
        "recipients": ["responsable.principal@verdecora.example.com"],
    }
    return SimpleNamespace(begin_send=MagicMock(return_value=poller))


@pytest.fixture()
def service_bus_client() -> SimpleNamespace:
    sender = SimpleNamespace(
        send_messages=AsyncMock(),
        schedule_messages=AsyncMock(return_value=[101, 102, 103]),
    )
    return SimpleNamespace(
        get_queue_sender=MagicMock(return_value=sender),
        get_topic_sender=MagicMock(return_value=sender),
        close=AsyncMock(),
    )
