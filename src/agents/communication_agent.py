from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Any, Callable

from pydantic import BaseModel

from src.models.communication import EscalationLevel, HITLNotification


class CommunicationSummary(BaseModel):
    subject: str
    body_html: str


class CommunicationAgentService:
    def __init__(
        self,
        *,
        send_notification_tool: Callable[[HITLNotification], Any] | None = None,
        records_container: Any | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self._send_notification_tool = send_notification_tool or _default_send_notification_tool
        self._records_container = records_container
        self._now_provider = now_provider or (lambda: datetime.now(tz=UTC))

    def build_summary(
        self, review_record: Mapping[str, Any], *, escalation_level: EscalationLevel
    ) -> CommunicationSummary:
        albaran_id = self._get_albaran_id(review_record)
        extraction = self._get_nested_mapping(review_record, "pipeline_result", "extraction")
        header = self._get_nested_mapping(extraction, "header")
        validation = self._get_nested_mapping(review_record, "pipeline_result", "validation")
        document_number = str(header.get("document_number") or albaran_id)
        supplier_name = str(
            header.get("supplier_name") or review_record.get("supplier_name") or "Proveedor no identificado"
        )
        discrepancies = self._collect_discrepancies(validation)
        escalation_text = {
            EscalationLevel.INITIAL: "Revisión inicial requerida",
            EscalationLevel.REMINDER_24H: "Recordatorio de revisión pendiente",
            EscalationLevel.ESCALATION_48H: "Escalado a responsable por demora",
            EscalationLevel.FINAL_72H: "Aviso final antes de expiración automática",
            EscalationLevel.EXPIRED: "Solicitud expirada",
        }[escalation_level]
        subject = f"[Verdecora] {escalation_text} · Albarán {document_number}"
        discrepancy_items = "".join(f"<li>{escape(item)}</li>" for item in discrepancies)
        if not discrepancy_items:
            discrepancy_items = "<li>Se requiere confirmación humana antes de continuar.</li>"
        body_html = (
            '<html><body style="font-family:Arial,Helvetica,sans-serif;line-height:1.6;color:#1f2937;">'
            f'<h2 style="color:#14532d;">{escape(escalation_text)}</h2>'
            f"<p>El albarán <strong>{escape(document_number)}</strong> del proveedor <strong>{escape(supplier_name)}</strong> requiere intervención humana.</p>"
            f"<p><strong>Identificador:</strong> {escape(albaran_id)}</p>"
            "<p><strong>Discrepancias detectadas:</strong></p>"
            f"<ul>{discrepancy_items}</ul>"
            "<p>Por favor, revise el formulario HITL y confirme si debe aprobarse, rechazarse o modificarse.</p>"
            "</body></html>"
        )
        return CommunicationSummary(subject=subject, body_html=body_html)

    def build_notification(
        self,
        review_record: Mapping[str, Any],
        *,
        escalation_level: EscalationLevel = EscalationLevel.INITIAL,
    ) -> HITLNotification:
        summary = self.build_summary(review_record, escalation_level=escalation_level)
        expires_at = self._parse_datetime(review_record.get("expires_at")) or (
            self._now_provider() + timedelta(hours=72)
        )
        callback_url = str(
            review_record.get("callback_url")
            or f"https://hitl-webform.example.com/review/{self._get_albaran_id(review_record)}"
        )
        pdf_sas_url = str(review_record.get("pdf_sas_url") or review_record.get("blob_url") or "")
        return HITLNotification(
            albaran_id=self._get_albaran_id(review_record),
            recipient_email=str(review_record.get("recipient_email") or "responsable@verdecora.example.com"),
            subject=summary.subject,
            body_html=summary.body_html,
            escalation_level=escalation_level,
            callback_url=callback_url,
            pdf_sas_url=pdf_sas_url,
            expires_at=expires_at,
        )

    async def handle_hitl_review(
        self,
        review_record: Mapping[str, Any],
        *,
        escalation_level: EscalationLevel = EscalationLevel.INITIAL,
    ) -> HITLNotification:
        notification = self.build_notification(review_record, escalation_level=escalation_level)
        send_result = self._send_notification_tool(notification)
        if hasattr(send_result, "__await__"):
            await send_result
        await self._track_escalation_state(review_record, notification)
        return notification

    async def _track_escalation_state(
        self,
        review_record: Mapping[str, Any],
        notification: HITLNotification,
    ) -> None:
        if self._records_container is None:
            return
        updated_record = dict(review_record)
        updated_record.update(
            {
                "id": self._get_albaran_id(review_record),
                "status": self._status_for_level(notification.escalation_level),
                "escalation_level": notification.escalation_level.value,
                "last_notification_at": self._now_provider().isoformat(),
                "expires_at": notification.expires_at.isoformat(),
                "recipient_email": notification.recipient_email,
                "callback_url": notification.callback_url,
                "pdf_sas_url": notification.pdf_sas_url,
            }
        )
        maybe_result = self._records_container.upsert_item(updated_record)
        if hasattr(maybe_result, "__await__"):
            await maybe_result

    def _collect_discrepancies(self, validation: Mapping[str, Any]) -> list[str]:
        discrepancies = [str(item) for item in validation.get("discrepancies", []) if str(item).strip()]
        if discrepancies:
            return discrepancies
        collected: list[str] = []
        for comparison in validation.get("line_comparisons", []):
            if not isinstance(comparison, Mapping):
                continue
            status = str(comparison.get("status") or "")
            if status in {"match", "tolerance"}:
                continue
            field = str(comparison.get("field") or "campo")
            extracted = str(comparison.get("extracted_value") or "-")
            bc_value = str(comparison.get("bc_value") or "-")
            collected.append(f"{field}: extraído '{extracted}' vs BC '{bc_value}' ({status}).")
        return collected

    def _get_albaran_id(self, review_record: Mapping[str, Any]) -> str:
        return str(review_record.get("albaran_id") or review_record.get("id") or "")

    def _get_nested_mapping(self, payload: Mapping[str, Any], *keys: str) -> Mapping[str, Any]:
        current: Mapping[str, Any] = payload
        for key in keys:
            value = current.get(key)
            if not isinstance(value, Mapping):
                return {}
            current = value
        return current

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        if isinstance(value, str) and value.strip():
            normalized = value.replace("Z", "+00:00")
            return datetime.fromisoformat(normalized)
        return None

    def _status_for_level(self, escalation_level: EscalationLevel) -> str:
        return {
            EscalationLevel.INITIAL: "pending",
            EscalationLevel.REMINDER_24H: "reminded",
            EscalationLevel.ESCALATION_48H: "escalated",
            EscalationLevel.FINAL_72H: "expired",
            EscalationLevel.EXPIRED: "expired",
        }[escalation_level]


def _default_send_notification_tool(notification: HITLNotification) -> Any:
    from src.mcp.acs_email_mcp.server import send_hitl_notification

    return send_hitl_notification(notification)


__all__ = ["CommunicationAgentService", "CommunicationSummary"]
