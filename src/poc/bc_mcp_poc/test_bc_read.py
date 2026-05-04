from __future__ import annotations

import argparse
import json
from typing import Any

from entity_schemas import ACTION_SCHEMAS, SEARCH_RESULTS, VALIDATED_READS, summarize_action

READ_SEQUENCE: list[tuple[str, str]] = [
    ("List purchase orders", "purchase_orders_top5"),
    ("Read purchase order 106030", "purchase_order_106030"),
    ("List PO lines for 106030", "purchase_order_lines_106030"),
    ("List vendors", "vendors_top5"),
    ("List items", "items_top5"),
    ("List posted purchase receipts", "purchase_receipts_top5"),
    ("List posted purchase receipt lines for 107239", "purchase_receipt_lines_107239"),
    ("Search posted purchase receipts by order number 106030", "purchase_receipts_by_order_106030"),
]


def as_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def print_search_inventory() -> None:
    print("== Search inventory ==")
    for query, actions in SEARCH_RESULTS.items():
        print(f"- {query}: {len(actions)} actions")
        for action in actions:
            print(f"  - {action}")


def print_schema_summary() -> None:
    print("\n== Key schema summary ==")
    for action_name in ACTION_SCHEMAS:
        print(f"- {summarize_action(action_name)}")


def print_read_sequence(output_json: bool) -> None:
    print("\n== Validated read sequence ==")
    for title, key in READ_SEQUENCE:
        payload = VALIDATED_READS[key]
        if output_json:
            print(f"\n# {title}\n{as_json(payload)}")
            continue

        print(f"\n# {title}")
        print(f"action: {payload['action']}")
        print(f"request: {as_json(payload['request'])}")
        observed_total = payload.get("observed_total")
        if observed_total is not None:
            print(f"observed_total: {observed_total}")
        if "sample_numbers" in payload:
            print(f"sample_numbers: {', '.join(payload['sample_numbers'])}")
        if "sample_line_numbers" in payload:
            sample_line_numbers = ", ".join(str(value) for value in payload["sample_line_numbers"])
            print(f"sample_line_numbers: {sample_line_numbers}")
        if "purchase_order_id" in payload:
            print(f"purchase_order_id: {payload['purchase_order_id']}")
        if "notes" in payload:
            print(f"notes: {payload['notes']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Document the validated native Business Central MCP read operations "
            "against CRONUS."
        )
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the validated read payloads as JSON.",
    )
    args = parser.parse_args()

    print(
        "This PoC documents native BC MCP read operations validated in CRONUS. "
        "It does not execute writes and does not attempt to call Business Central "
        "directly from Python."
    )
    print_search_inventory()
    print_schema_summary()
    print_read_sequence(output_json=args.json)


if __name__ == "__main__":
    main()
