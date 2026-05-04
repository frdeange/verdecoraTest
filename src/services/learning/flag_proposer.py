from __future__ import annotations

from src.models.learning import LearningInsight, SupplierReputation


def propose_feature_flag_updates(
    reputations: list[SupplierReputation],
    insights: list[LearningInsight] | None = None,
) -> list[dict[str, str]]:
    proposed: list[dict[str, str]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()

    for reputation in reputations:
        proposed.extend(
            [
                {f"supplier.{reputation.supplier_id}.tolerance_pct": f"{reputation.recommended_tolerance_pct:.2f}"},
                {
                    f"supplier.{reputation.supplier_id}.auto_approve": (
                        "true" if reputation.auto_approve_eligible else "false"
                    )
                },
            ]
        )
        if reputation.reliability_score < 0.5:
            proposed.append({f"supplier.{reputation.supplier_id}.force_hitl": "true"})

    for insight in insights or []:
        if insight.suggested_flag_update:
            proposed.append(insight.suggested_flag_update)

    deduplicated: list[dict[str, str]] = []
    for proposal in proposed:
        normalized = tuple(sorted((str(key), str(value)) for key, value in proposal.items()))
        if normalized in seen:
            continue
        seen.add(normalized)
        deduplicated.append(dict(proposal))
    return deduplicated


__all__ = ["propose_feature_flag_updates"]
