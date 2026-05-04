from __future__ import annotations

import json
from collections.abc import Sequence

from pydantic import BaseModel

from src.models.albaran import AlbaranExtraction, CoherenceCheckResult, TriageResult
from src.models.inventory import PostingResult
from src.models.learning import LearningReport
from src.models.reconciliation import ReconciliationReport
from src.models.validation import ValidationResult

from ..communication_agent import CommunicationSummary
from ..security import harden_system_prompt
from .coherence_prompt import COHERENCE_SYSTEM_PROMPT
from .communication_prompt import COMMUNICATION_SYSTEM_PROMPT
from .extractor_prompt import EXTRACTOR_SYSTEM_PROMPT
from .inventory_prompt import INVENTORY_SYSTEM_PROMPT
from .learning_prompt import LEARNING_SYSTEM_PROMPT
from .reconciliation_prompt import RECONCILIATION_SYSTEM_PROMPT
from .triage_prompt import TRIAGE_SYSTEM_PROMPT
from .validator_prompt import VALIDATOR_SYSTEM_PROMPT

DEFAULT_EXTRACTOR_TOOL_NAMES: tuple[str, ...] = (
    "content_understanding.analyze_document",
    "content_understanding.extract_tables",
)
DEFAULT_COHERENCE_TOOL_NAMES: tuple[str, ...] = (
    "bc.search_vendors",
    "bc.search_purchase_orders",
    "bc.search_items",
)
DEFAULT_VALIDATOR_TOOL_NAMES: tuple[str, ...] = (
    "bc.search_purchase_orders",
    "bc.get_purchase_order_lines",
    "bc.search_items",
)
DEFAULT_INVENTORY_TOOL_NAMES: tuple[str, ...] = (
    "bc.create_purchase_receipt",
    "bc.post_purchase_receipt_lines",
)


def _build_system_prompt(
    template: str,
    schema_model: type[BaseModel],
    *,
    tool_names: Sequence[str] = (),
) -> str:
    schema = json.dumps(schema_model.model_json_schema(), ensure_ascii=False, indent=2)
    tool_hint = f"\nAvailable MCP tools: {', '.join(tool_names)}" if tool_names else ""
    return harden_system_prompt(template.format(schema=schema) + tool_hint)


def build_triage_instructions() -> str:
    return _build_system_prompt(TRIAGE_SYSTEM_PROMPT, TriageResult)


def build_extractor_instructions(tool_names: Sequence[str] = DEFAULT_EXTRACTOR_TOOL_NAMES) -> str:
    return _build_system_prompt(EXTRACTOR_SYSTEM_PROMPT, AlbaranExtraction, tool_names=tool_names)


def build_coherence_instructions(tool_names: Sequence[str] = DEFAULT_COHERENCE_TOOL_NAMES) -> str:
    return _build_system_prompt(COHERENCE_SYSTEM_PROMPT, CoherenceCheckResult, tool_names=tool_names)


def build_validator_instructions(tool_names: Sequence[str] = DEFAULT_VALIDATOR_TOOL_NAMES) -> str:
    return _build_system_prompt(VALIDATOR_SYSTEM_PROMPT, ValidationResult, tool_names=tool_names)


def build_inventory_instructions(tool_names: Sequence[str] = DEFAULT_INVENTORY_TOOL_NAMES) -> str:
    return _build_system_prompt(INVENTORY_SYSTEM_PROMPT, PostingResult, tool_names=tool_names)


def build_communication_instructions() -> str:
    return _build_system_prompt(COMMUNICATION_SYSTEM_PROMPT, CommunicationSummary)


def build_reconciliation_instructions(tool_names: Sequence[str] = ()) -> str:
    return _build_system_prompt(RECONCILIATION_SYSTEM_PROMPT, ReconciliationReport, tool_names=tool_names)


def build_learning_instructions(tool_names: Sequence[str] = ()) -> str:
    return _build_system_prompt(LEARNING_SYSTEM_PROMPT, LearningReport, tool_names=tool_names)


__all__ = [
    "COHERENCE_SYSTEM_PROMPT",
    "COMMUNICATION_SYSTEM_PROMPT",
    "DEFAULT_COHERENCE_TOOL_NAMES",
    "DEFAULT_EXTRACTOR_TOOL_NAMES",
    "DEFAULT_INVENTORY_TOOL_NAMES",
    "DEFAULT_VALIDATOR_TOOL_NAMES",
    "EXTRACTOR_SYSTEM_PROMPT",
    "INVENTORY_SYSTEM_PROMPT",
    "LEARNING_SYSTEM_PROMPT",
    "RECONCILIATION_SYSTEM_PROMPT",
    "TRIAGE_SYSTEM_PROMPT",
    "VALIDATOR_SYSTEM_PROMPT",
    "build_coherence_instructions",
    "build_communication_instructions",
    "build_extractor_instructions",
    "build_inventory_instructions",
    "build_learning_instructions",
    "build_reconciliation_instructions",
    "build_triage_instructions",
    "build_validator_instructions",
]
