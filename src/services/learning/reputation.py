from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from src.models.learning import SupplierReputation

SUCCESS_STATUSES = {"posted", "completed", "approved", "success"}


def build_supplier_reputation(
    supplier_id: str,
    supplier_name: str,
    records: list[dict[str, Any]],
    *,
    now: datetime,
) -> SupplierReputation:
    total = len(records)
    successes = sum(1 for record in records if (_extract_status(record) or "").casefold() in SUCCESS_STATUSES)
    success_rate = (successes / total) if total else 1.0

    discrepancy_rates = [_extract_discrepancy_rate(record) for record in records]
    normalized_discrepancies = [rate for rate in discrepancy_rates if rate is not None]
    avg_discrepancy_rate = (
        sum(normalized_discrepancies) / len(normalized_discrepancies) if normalized_discrepancies else 0.0
    )

    processing_times = [_extract_processing_time_seconds(record) for record in records]
    normalized_processing_times = [value for value in processing_times if value is not None]
    avg_processing_time_seconds = (
        sum(normalized_processing_times) / len(normalized_processing_times) if normalized_processing_times else None
    )

    signature_reliability = _extract_signature_reliability(records)
    reliability_score = min(
        max((0.5 * success_rate) + (0.3 * (1 - avg_discrepancy_rate)) + (0.2 * signature_reliability), 0.0), 1.0
    )
    common_issues = [issue for issue, _ in Counter(_collect_common_issues(records)).most_common(3)]
    recommended_tolerance_pct = _recommended_tolerance_pct(reliability_score, avg_discrepancy_rate)
    auto_approve_eligible = total >= 3 and reliability_score >= 0.9 and avg_discrepancy_rate <= 0.02

    notes = (
        f"Success rate {success_rate:.0%}, discrepancy rate {avg_discrepancy_rate:.1%}, "
        f"signature reliability {signature_reliability:.0%}."
    )
    return SupplierReputation(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        total_albaranes_processed=total,
        success_rate=success_rate,
        avg_discrepancy_rate=avg_discrepancy_rate,
        common_issues=common_issues,
        avg_processing_time_seconds=avg_processing_time_seconds,
        reliability_score=reliability_score,
        last_updated=now.astimezone(UTC),
        recommended_tolerance_pct=recommended_tolerance_pct,
        auto_approve_eligible=auto_approve_eligible,
        notes=notes,
    )


def _extract_status(record: dict[str, Any]) -> str | None:
    status = record.get("status")
    if isinstance(status, str) and status.strip():
        return status.strip()
    inventory_success = record.get("inventory_success")
    if isinstance(inventory_success, bool):
        return "posted" if inventory_success else "failed"
    return None


def _extract_discrepancy_rate(record: dict[str, Any]) -> float | None:
    explicit_rate = record.get("discrepancy_rate")
    if explicit_rate is not None:
        try:
            return min(max(float(explicit_rate), 0.0), 1.0)
        except (TypeError, ValueError):
            return None

    discrepancies = record.get("discrepancies")
    if not isinstance(discrepancies, list):
        discrepancies = []
    total_lines = record.get("total_lines") or len(record.get("line_items") or []) or len(record.get("lines") or [])
    try:
        total_lines_value = int(total_lines)
    except (TypeError, ValueError):
        total_lines_value = 0
    if total_lines_value <= 0:
        return 0.0 if not discrepancies else 1.0
    return min(len(discrepancies) / total_lines_value, 1.0)


def _extract_processing_time_seconds(record: dict[str, Any]) -> float | None:
    explicit_value = record.get("processing_time_seconds")
    if explicit_value is not None:
        try:
            return float(explicit_value)
        except (TypeError, ValueError):
            return None

    created_at = _parse_datetime(record.get("created_at"))
    completed_at = _parse_datetime(record.get("completed_at") or record.get("updated_at"))
    if created_at is None or completed_at is None:
        return None
    return max((completed_at - created_at).total_seconds(), 0.0)


def _extract_signature_reliability(records: list[dict[str, Any]]) -> float:
    if not records:
        return 0.5
    positives = 0
    considered = 0
    for record in records:
        for candidate in (
            record.get("signature_reliable"),
            record.get("signature_valid"),
            record.get("has_signature"),
        ):
            if isinstance(candidate, bool):
                considered += 1
                positives += int(candidate)
                break
    if considered == 0:
        return 0.5
    return positives / considered


def _recommended_tolerance_pct(reliability_score: float, avg_discrepancy_rate: float) -> float:
    if reliability_score >= 0.95 and avg_discrepancy_rate <= 0.01:
        return 1.0
    if reliability_score >= 0.85 and avg_discrepancy_rate <= 0.03:
        return 2.0
    return 3.0


def _collect_common_issues(records: list[dict[str, Any]]) -> list[str]:
    collected: list[str] = []
    for record in records:
        discrepancies = record.get("discrepancies")
        if isinstance(discrepancies, list):
            collected.extend(str(item).strip() for item in discrepancies if str(item).strip())
        issue = record.get("issue")
        if isinstance(issue, str) and issue.strip():
            collected.append(issue.strip())
    return collected


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value.strip():
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


__all__ = ["SUCCESS_STATUSES", "build_supplier_reputation"]
