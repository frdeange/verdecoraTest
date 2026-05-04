from __future__ import annotations

from src.mcp.feature_flags_mcp.models import FlagOverride
from src.mcp.feature_flags_mcp.server import document_matches_context, to_flag_value


def test_document_matches_context_returns_true_for_matching_override() -> None:
    override = FlagOverride(match={"supplier_id": "SUP-1", "store_id": "MAD-01"}, value=True)

    assert document_matches_context(override, {"supplier_id": "SUP-1", "store_id": "MAD-01"}) is True


def test_document_matches_context_returns_false_for_non_matching_override() -> None:
    override = FlagOverride(match={"supplier_id": "SUP-1"}, value=True)

    assert document_matches_context(override, {"supplier_id": "SUP-2"}) is False


def test_to_flag_value_builds_typed_model() -> None:
    flag = to_flag_value(
        {
            "id": "triage.enabled",
            "flag_name": "triage.enabled",
            "value": True,
            "version": 3,
            "description": "Enable the triage agent",
            "overrides": [{"match": {"supplier_id": "SUP-1"}, "value": False}],
            "updated_at": "2026-05-04T12:00:00Z",
        }
    )

    assert flag.flag_name == "triage.enabled"
    assert flag.value is True
    assert flag.version == 3
    assert flag.overrides[0].match == {"supplier_id": "SUP-1"}
