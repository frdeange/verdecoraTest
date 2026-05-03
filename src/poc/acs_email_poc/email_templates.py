from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from html import escape
from typing import Sequence
from urllib.parse import quote

DEFAULT_HITL_BASE_URL = "https://hitl-webform.example.com/api/hitl"


@dataclass(slots=True)
class DiscrepancyLine:
    product: str
    description: str
    albaran_qty: Decimal | float | int
    po_qty: Decimal | float | int
    impact: str

    @property
    def difference(self) -> Decimal:
        return Decimal(str(self.albaran_qty)) - Decimal(str(self.po_qty))


@dataclass(slots=True)
class HitlEmailContext:
    albaran_id: str
    albaran_number: str
    supplier_name: str
    delivery_date: date | datetime | str
    po_reference: str
    pdf_url: str
    token: str
    discrepancy_lines: Sequence[DiscrepancyLine] = field(default_factory=tuple)
    store_name: str | None = None
    notes: str | None = None
    sla_hours: int = 24
    base_url: str = DEFAULT_HITL_BASE_URL


def _format_date(value: date | datetime | str) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _format_decimal(value: Decimal | float | int) -> str:
    decimal_value = Decimal(str(value))
    if decimal_value == decimal_value.to_integral():
        return f"{decimal_value.quantize(Decimal('1'))}"
    return f"{decimal_value.normalize()}"


def _render_discrepancy_rows(lines: Sequence[DiscrepancyLine]) -> str:
    rows: list[str] = []
    for line in lines:
        diff = line.difference
        rows.append(
            "<tr>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e5e7eb;\">{escape(line.product)}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e5e7eb;\">{escape(line.description)}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e5e7eb;text-align:right;\">{_format_decimal(line.albaran_qty)}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e5e7eb;text-align:right;\">{_format_decimal(line.po_qty)}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e5e7eb;text-align:right;font-weight:600;color:#b91c1c;\">{_format_decimal(diff)}</td>"
            f"<td style=\"padding:12px;border-bottom:1px solid #e5e7eb;\">{escape(line.impact)}</td>"
            "</tr>"
        )
    return "".join(rows)


def build_action_url(context: HitlEmailContext, action: str) -> str:
    safe_action = action.strip("/")
    safe_id = quote(context.albaran_id, safe="")
    safe_token = quote(context.token, safe="")
    return f"{context.base_url}/{safe_id}/{safe_action}?token={safe_token}"


def render_hitl_email(context: HitlEmailContext) -> str:
    rows = _render_discrepancy_rows(context.discrepancy_lines)
    discrepancy_count = len(context.discrepancy_lines)
    accept_url = build_action_url(context, "accept")
    modify_url = build_action_url(context, "modify")
    reject_url = build_action_url(context, "reject")
    notes_html = (
        f"<p style=\"margin:16px 0 0;color:#4b5563;font-size:14px;line-height:1.6;\"><strong>Notes:</strong> {escape(context.notes)}</p>"
        if context.notes
        else ""
    )
    store_html = (
        f"<div style=\"margin-top:8px;color:#4b5563;font-size:14px;\"><strong>Store:</strong> {escape(context.store_name)}</div>"
        if context.store_name
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang=\"en\">
  <body style=\"margin:0;padding:24px;background-color:#f3f4f6;font-family:Arial,Helvetica,sans-serif;color:#111827;\">
    <div style=\"max-width:960px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;\">
      <div style=\"padding:24px 32px;background:linear-gradient(90deg,#14532d,#166534);color:#ffffff;\">
        <div style=\"font-size:13px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;\">Verdecora · Human approval required</div>
        <h1 style=\"margin:12px 0 4px;font-size:28px;line-height:1.2;\">Albarán discrepancy awaiting decision</h1>
        <p style=\"margin:0;font-size:15px;line-height:1.6;max-width:640px;\">We detected {discrepancy_count} discrepancy line(s) between the delivery note and the purchase order. Please review and choose how to proceed.</p>
      </div>
      <div style=\"padding:32px;\">
        <div style=\"display:block;margin-bottom:24px;padding:20px;background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;\">
          <div style=\"font-size:18px;font-weight:700;color:#111827;\">Albarán {escape(context.albaran_number)}</div>
          <div style=\"margin-top:12px;color:#374151;font-size:14px;line-height:1.8;\">
            <div><strong>Supplier:</strong> {escape(context.supplier_name)}</div>
            <div><strong>Date:</strong> {escape(_format_date(context.delivery_date))}</div>
            <div><strong>PO reference:</strong> {escape(context.po_reference)}</div>
            <div><strong>HITL request id:</strong> {escape(context.albaran_id)}</div>
            {store_html}
          </div>
        </div>

        <table role=\"presentation\" style=\"width:100%;border-collapse:collapse;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;\">
          <thead>
            <tr style=\"background:#f3f4f6;text-align:left;color:#111827;\">
              <th style=\"padding:12px;border-bottom:1px solid #d1d5db;\">Product</th>
              <th style=\"padding:12px;border-bottom:1px solid #d1d5db;\">Description</th>
              <th style=\"padding:12px;border-bottom:1px solid #d1d5db;text-align:right;\">Albarán qty</th>
              <th style=\"padding:12px;border-bottom:1px solid #d1d5db;text-align:right;\">PO qty</th>
              <th style=\"padding:12px;border-bottom:1px solid #d1d5db;text-align:right;\">Difference</th>
              <th style=\"padding:12px;border-bottom:1px solid #d1d5db;\">Impact</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>

        <div style=\"margin-top:24px;padding:20px;background:#fffbeb;border:1px solid #fcd34d;border-radius:12px;color:#92400e;font-size:14px;line-height:1.7;\">
          Please respond within <strong>{context.sla_hours} hours</strong>. These buttons open the secure HITL web form where the final action is recorded.
        </div>
        {notes_html}

        <div style=\"margin-top:28px;text-align:center;\">
          <a href=\"{accept_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 24px;background:#166534;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Accept</a>
          <a href=\"{modify_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 24px;background:#d97706;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Modify</a>
          <a href=\"{reject_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 24px;background:#b91c1c;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Reject</a>
        </div>

        <div style=\"margin-top:24px;padding:20px;background:#f9fafb;border-radius:12px;border:1px solid #e5e7eb;font-size:14px;line-height:1.7;color:#374151;\">
          <div><strong>PDF evidence:</strong> <a href=\"{escape(context.pdf_url)}\" style=\"color:#166534;\">Open signed PDF (SAS URL placeholder)</a></div>
          <div style=\"margin-top:10px;\"><strong>Fallback links:</strong></div>
          <div style=\"margin-top:6px;word-break:break-all;\">Accept: <a href=\"{accept_url}\" style=\"color:#166534;\">{accept_url}</a></div>
          <div style=\"margin-top:6px;word-break:break-all;\">Modify: <a href=\"{modify_url}\" style=\"color:#d97706;\">{modify_url}</a></div>
          <div style=\"margin-top:6px;word-break:break-all;\">Reject: <a href=\"{reject_url}\" style=\"color:#b91c1c;\">{reject_url}</a></div>
        </div>
      </div>
    </div>
  </body>
</html>
"""
