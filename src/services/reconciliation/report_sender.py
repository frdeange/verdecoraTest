from __future__ import annotations

from html import escape
from typing import Any, Callable

from src.mcp.acs_email_mcp.server import send_email
from src.models.reconciliation import ReconciliationReport


class ReconciliationReportSender:
    def __init__(
        self,
        recipients: tuple[str, ...] | list[str],
        *,
        send_email_tool: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self._recipients = tuple(recipients)
        self._send_email_tool = send_email_tool or send_email

    def send_report(
        self, report: ReconciliationReport, *, fix_proposals: list[str] | None = None
    ) -> dict[str, Any] | None:
        if not self._recipients:
            return None
        return self._send_email_tool(
            to=list(self._recipients),
            subject=f"[Verdecora] Daily reconciliation report · {report.report_date.isoformat()}",
            body_html=self._build_body(report, fix_proposals=fix_proposals or []),
        )

    def _build_body(self, report: ReconciliationReport, *, fix_proposals: list[str]) -> str:
        drift_rows = "".join(
            (
                "<tr>"
                f"<td>{escape(item.albaran_id)}</td>"
                f"<td>{escape(item.supplier_name or '-')}</td>"
                f"<td>{escape(item.drift_type.value)}</td>"
                f"<td>{escape(item.suggested_action)}</td>"
                f"<td>{escape(str(item.difference) if item.difference is not None else '-')}</td>"
                "</tr>"
            )
            for item in report.drift_items
        )
        if not drift_rows:
            drift_rows = '<tr><td colspan="5">No drifts found.</td></tr>'

        fix_items = "".join(f"<li>{escape(proposal)}</li>" for proposal in fix_proposals)
        fix_section = (
            f"<p><strong>Pending HITL-gated fix proposals:</strong></p><ul>{fix_items}</ul>" if fix_items else ""
        )

        return (
            '<html><body style="font-family:Arial,Helvetica,sans-serif;line-height:1.5;color:#1f2937;">'
            '<h2 style="color:#14532d;">Daily reconciliation report</h2>'
            f"<p>{escape(report.summary)}</p>"
            "<ul>"
            f"<li>Cosmos records: {report.total_cosmos_records}</li>"
            f"<li>BC records: {report.total_bc_records}</li>"
            f"<li>Drifts found: {report.drifts_found}</li>"
            f"<li>Auto-fixable: {report.auto_fixable}</li>"
            f"<li>Needs review: {report.needs_review}</li>"
            "</ul>"
            '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">'
            "<thead><tr><th>Albarán</th><th>Supplier</th><th>Drift</th><th>Action</th><th>Difference</th></tr></thead>"
            f"<tbody>{drift_rows}</tbody></table>"
            f"{fix_section}"
            "</body></html>"
        )


__all__ = ["ReconciliationReportSender"]
