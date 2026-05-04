"""
Stub agents for MAF v1.0 PoC.

Three agents mimicking the albarán processing architecture:
  - StubExtractor: mock document extraction → structured JSON
  - StubValidator: mock validation → coincide / discrepancia
  - StubInventory: mock BC posting → receipt ID

Each agent uses a real MAF Agent with a mock @tool instead of MCP,
so we can validate orchestration without cloud dependencies.
"""

import json
from typing import Annotated

from agent_framework import Agent, tool

# ---------------------------------------------------------------------------
# Mock tools (replace with MCPStreamableHTTPTool in production)
# ---------------------------------------------------------------------------

@tool(approval_mode="never_require")
def extract_document(
    document_url: Annotated[str, "URL or path of the delivery note PDF"],
) -> str:
    """Simulate Document Intelligence extraction of an albarán."""
    return json.dumps({
        "albaran_number": "ALB-2026-00142",
        "supplier": "Viveros El Pino S.L.",
        "supplier_id": "SUP-0087",
        "po_number": "PO-2026-003201",
        "date": "2026-05-04",
        "lines": [
            {"sku": "PLANT-OLV-150", "description": "Olivo 150 cm", "qty": 25, "unit_price": 34.50},
            {"sku": "PLANT-LAV-030", "description": "Lavanda 30 cm", "qty": 100, "unit_price": 2.80},
            {"sku": "SUBS-UNI-050", "description": "Sustrato universal 50L", "qty": 40, "unit_price": 5.20},
        ],
        "total": 1370.50,
    })


@tool(approval_mode="never_require")
def validate_against_po(
    extracted_json: Annotated[str, "JSON string of extracted delivery note data"],
) -> str:
    """Compare extracted data against the purchase order in Business Central (mock)."""
    data = json.loads(extracted_json)
    po = data.get("po_number", "")
    # Simulate: PO-2026-003201 matches, anything else is a discrepancy
    if po == "PO-2026-003201":
        return json.dumps({
            "status": "coincide",
            "po_number": po,
            "matched_lines": len(data.get("lines", [])),
            "discrepancies": [],
        })
    return json.dumps({
        "status": "discrepancia",
        "po_number": po,
        "matched_lines": 0,
        "discrepancies": [{"type": "po_not_found", "detail": f"PO {po} not found in BC"}],
    })


@tool(approval_mode="never_require")
def post_inventory_receipt(
    validated_json: Annotated[str, "JSON string of validated delivery note data"],
) -> str:
    """Post inventory receipt to Business Central (mock)."""
    data = json.loads(validated_json)
    return json.dumps({
        "receipt_id": "REC-2026-007834",
        "po_number": data.get("po_number", "UNKNOWN"),
        "status": "posted",
        "bc_document_no": "PREC-00456",
    })


# ---------------------------------------------------------------------------
# Agent factories
# ---------------------------------------------------------------------------

def create_extractor(client) -> Agent:
    """Create the StubExtractor agent."""
    return Agent(
        client=client,
        name="StubExtractor",
        instructions=(
            "You are the Extraction Agent. When you receive a delivery note reference, "
            "use the extract_document tool to extract structured data. "
            "Return the extracted JSON to the next agent in the pipeline."
        ),
        tools=[extract_document],
    )


def create_validator(client) -> Agent:
    """Create the StubValidator agent (handoff-ready)."""
    return Agent(
        client=client,
        name="StubValidator",
        instructions=(
            "You are the Validation Agent. You receive extracted delivery note JSON. "
            "Use validate_against_po to compare it with the purchase order.\n\n"
            "Decision rules:\n"
            "- If status is 'coincide': hand off to StubInventory so it can post the receipt.\n"
            "- If status is 'discrepancia': respond with the discrepancy details "
            "and hand off to 'user' for human review (HITL).\n"
        ),
        tools=[validate_against_po],
        handoffs=["StubInventory", "user"],
        require_per_service_call_history_persistence=True,
    )


def create_inventory(client) -> Agent:
    """Create the StubInventory agent (handoff-ready)."""
    return Agent(
        client=client,
        name="StubInventory",
        instructions=(
            "You are the Inventory Agent. You receive validated delivery note data. "
            "Use post_inventory_receipt to register the goods in Business Central. "
            "Return the receipt confirmation with the BC document number."
        ),
        tools=[post_inventory_receipt],
        require_per_service_call_history_persistence=True,
    )
