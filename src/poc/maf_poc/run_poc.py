#!/usr/bin/env python3
"""
CLI entry point for the MAF v1.0 PoC.

Usage:
    python -m src.poc.maf_poc.run_poc [--albaran <text>]

Requires:
    - agent-framework >= 1.0.0
    - opentelemetry-sdk
    - A chat client (FoundryChatClient or OpenAIChatClient)

Environment variables (pick one):
    AZURE_AI_PROJECT_ENDPOINT + model name  → FoundryChatClient
    OPENAI_API_KEY                          → OpenAIChatClient
    (none)                                  → falls back to a mock client for dry-run

The PoC prints results and OpenTelemetry spans to the console.
"""

import argparse
import asyncio
import json
import os

from .orchestrator import run_full_poc

# ---------------------------------------------------------------------------
# Chat client factory
# ---------------------------------------------------------------------------

def _create_client():
    """Create the best available chat client based on environment."""
    # Option 1: Azure AI Foundry
    endpoint = os.environ.get("AZURE_AI_PROJECT_ENDPOINT")
    if endpoint:
        from agent_framework.foundry import FoundryChatClient
        from azure.identity import DefaultAzureCredential

        model = os.environ.get("AZURE_AI_MODEL", "gpt-4o")
        print(f"[config] Using FoundryChatClient → {endpoint} / {model}")
        return FoundryChatClient(
            project_endpoint=endpoint,
            model=model,
            credential=DefaultAzureCredential(),
        )

    # Option 2: OpenAI / GitHub Models
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        from agent_framework.openai import OpenAIChatCompletionClient

        model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        print(f"[config] Using OpenAIChatCompletionClient → {model}")
        return OpenAIChatCompletionClient(model=model, api_key=api_key)

    # Option 3: Dry-run mode — no LLM
    print("[config] No LLM credentials found. Running in DRY-RUN mode.")
    print("[config] Set AZURE_AI_PROJECT_ENDPOINT or OPENAI_API_KEY for live run.")
    return _MockChatClient()


class _MockChatClient:
    """
    Minimal mock chat client for dry-run testing.

    This lets us validate the orchestration wiring (Agent creation,
    SequentialBuilder, HandoffBuilder) without calling any LLM.
    The agents' tools will still be invoked by the framework.
    """
    pass


# ---------------------------------------------------------------------------
# Mock mode: override run_full_poc for dry-run
# ---------------------------------------------------------------------------

async def _dry_run_poc(albaran_input: str) -> dict:
    """Simulate the full PoC without an LLM by invoking tools directly."""
    from .stub_agents import extract_document, post_inventory_receipt, validate_against_po

    print("\n" + "=" * 60)
    print("DRY-RUN MODE — Calling tools directly (no LLM)")
    print("=" * 60)

    # Step 1: Extract
    extracted = extract_document(document_url=albaran_input)
    print(f"\n[StubExtractor] Extracted:\n{json.dumps(json.loads(extracted), indent=2)}")

    # Step 2: Validate
    validated = validate_against_po(extracted_json=extracted)
    val_data = json.loads(validated)
    print(f"\n[StubValidator] Validation result:\n{json.dumps(val_data, indent=2)}")

    # Step 3: Post (only if coincide)
    if val_data["status"] == "coincide":
        receipt = post_inventory_receipt(validated_json=extracted)
        receipt_data = json.loads(receipt)
        print(f"\n[StubInventory] Posted receipt:\n{json.dumps(receipt_data, indent=2)}")
        outcome = "posted"
        messages = [extracted, validated, receipt]
    else:
        print("\n[StubValidator] Discrepancy detected → HITL required")
        outcome = "hitl_required"
        messages = [extracted, validated]

    return {
        "extraction_result": extracted,
        "validation_outcome": outcome,
        "messages": messages,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SAMPLE_ALBARAN = (
    "Albarán ALB-2026-00142 from Viveros El Pino S.L., "
    "PO PO-2026-003201, received at Store 12 Alcalá on 2026-05-04. "
    "3 lines: 25x Olivo 150cm, 100x Lavanda 30cm, 40x Sustrato 50L. "
    "Total: 1370.50 EUR."
)


async def _main():
    parser = argparse.ArgumentParser(description="MAF v1.0 PoC — Albarán processing")
    parser.add_argument(
        "--albaran",
        default=SAMPLE_ALBARAN,
        help="Delivery note text to process (default: sample albarán)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("MAF v1.0 PoC — Albarán Processing Pipeline")
    print("=" * 60)
    print(f"\nInput: {args.albaran}\n")

    client = _create_client()

    if isinstance(client, _MockChatClient):
        result = await _dry_run_poc(args.albaran)
    else:
        result = await run_full_poc(client, args.albaran)

    print("\n" + "=" * 60)
    print("RESULT SUMMARY")
    print("=" * 60)
    print(f"  Outcome:    {result['validation_outcome']}")
    print(f"  Messages:   {len(result['messages'])} agent outputs")
    print(f"  Extraction: {result['extraction_result'][:120]}...")
    print("=" * 60)

    # Flush OTel spans
    from opentelemetry import trace as otel_trace

    provider = otel_trace.get_tracer_provider()
    if hasattr(provider, "force_flush"):
        provider.force_flush()

    print("\n✅ PoC complete. Check console output above for OpenTelemetry spans.")


def main():
    asyncio.run(_main())


if __name__ == "__main__":
    main()
