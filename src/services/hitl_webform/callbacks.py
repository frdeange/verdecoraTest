from __future__ import annotations

import inspect
from datetime import UTC, datetime
from typing import Any, Callable, Protocol

from src.models.communication import HITLDecision
from src.models.inventory import PostingResult


class CallbackReviewStore(Protocol):
    async def get_review_record(self, albaran_id: str) -> dict[str, Any] | None:  # pragma: no cover - protocol definition
        ...

    async def upsert_item(self, document: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover - protocol definition
        ...


class HITLCallbackError(RuntimeError):
    """Raised when a HITL decision cannot be applied to a persisted review record."""


class HITLCallbackHandler:
    def __init__(
        self,
        review_store: CallbackReviewStore,
        *,
        inventory_processor: Callable[[dict[str, Any]], Any],
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.review_store = review_store
        self.inventory_processor = inventory_processor
        self._now_provider = now_provider or (lambda: datetime.now(tz=UTC))

    async def handle_decision(self, decision: HITLDecision) -> dict[str, Any]:
        review_record = await self.review_store.get_review_record(decision.albaran_id)
        if review_record is None:
            raise HITLCallbackError(f"Review record not found for {decision.albaran_id}.")

        updated_record = dict(review_record)
        updated_record.update(
            {
                "id": decision.albaran_id,
                "hitl_decision": decision.model_dump(mode="json"),
                "reviewer_email": decision.reviewer_email,
                "decided_at": decision.decided_at.isoformat(),
                "updated_at": self._now_provider().isoformat(),
            }
        )

        if decision.decision in {"approve", "modify"}:
            posting_result = await self._run_inventory_processor(review_record, decision)
            updated_record["inventory_result"] = posting_result.model_dump(mode="json")
            updated_record["status"] = "completed" if posting_result.success else "hitl_pending"
            updated_record["routing_decision"] = "posted" if posting_result.success else "hitl_review"
        elif decision.decision == "reject":
            updated_record["inventory_result"] = None
            updated_record["status"] = "rejected"
            updated_record["routing_decision"] = "reject"
        else:
            raise HITLCallbackError(f"Unsupported HITL decision: {decision.decision}.")

        return await self.review_store.upsert_item(updated_record)

    async def cancel_review(
        self,
        albaran_id: str,
        *,
        reviewer_email: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        review_record = await self.review_store.get_review_record(albaran_id)
        if review_record is None:
            raise HITLCallbackError(f"Review record not found for {albaran_id}.")

        updated_record = dict(review_record)
        updated_record.update(
            {
                "id": albaran_id,
                "status": "cancelled",
                "routing_decision": "cancelled",
                "reviewer_email": reviewer_email,
                "cancellation_notes": notes,
                "cancelled_at": self._now_provider().isoformat(),
                "updated_at": self._now_provider().isoformat(),
            }
        )
        return await self.review_store.upsert_item(updated_record)

    async def _run_inventory_processor(self, review_record: dict[str, Any], decision: HITLDecision) -> PostingResult:
        payload = {
            "decision": decision.model_dump(mode="json"),
            "validation": review_record.get("pipeline_result", {}).get("validation"),
            "extraction": review_record.get("pipeline_result", {}).get("extraction"),
            "modified_lines": decision.modified_lines,
        }
        result = self.inventory_processor(payload)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, PostingResult):
            return result
        return PostingResult.model_validate(result)


__all__ = ["HITLCallbackError", "HITLCallbackHandler"]
