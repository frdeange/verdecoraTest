from __future__ import annotations

from html import escape

from .email_templates import HitlEmailContext, build_action_url

ESCALATION_NOTICE = (
    "This escalation is intended for the responsible approver and their backup contact. "
    "If no action is recorded, operations should intervene."
)


def render_escalation_email(context: HitlEmailContext, pending_hours: int = 48) -> str:
    accept_url = build_action_url(context, "accept")
    modify_url = build_action_url(context, "modify")
    reject_url = build_action_url(context, "reject")

    return f"""<!DOCTYPE html>
<html lang=\"en\">
  <body style=\"margin:0;padding:24px;background:#fef2f2;font-family:Arial,Helvetica,sans-serif;color:#111827;\">
    <div style=\"max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #fecaca;border-radius:16px;overflow:hidden;\">
      <div style=\"padding:24px 32px;background:#991b1b;color:#ffffff;\">
        <div style=\"font-size:13px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;\">48h escalation</div>
        <h1 style=\"margin:12px 0 4px;font-size:26px;\">Urgent approval needed for albarán {escape(context.albaran_number)}</h1>
        <p style=\"margin:0;font-size:15px;line-height:1.6;\">The discrepancy has been pending for {pending_hours} hours and now requires escalation handling.</p>
      </div>
      <div style=\"padding:32px;\">
        <div style=\"padding:18px;background:#fef2f2;border:1px solid #fecaca;border-radius:12px;font-size:14px;line-height:1.7;color:#7f1d1d;\">{escape(ESCALATION_NOTICE)}</div>
        <p style=\"margin:20px 0 16px;font-size:15px;line-height:1.7;\"><strong>Supplier:</strong> {escape(context.supplier_name)}<br /><strong>PO reference:</strong> {escape(context.po_reference)}<br /><strong>PDF:</strong> <a href=\"{escape(context.pdf_url)}\" style=\"color:#991b1b;\">Open evidence package</a></p>
        <div style=\"text-align:center;\">
          <a href=\"{accept_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 22px;background:#166534;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Accept</a>
          <a href=\"{modify_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 22px;background:#d97706;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Modify</a>
          <a href=\"{reject_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 22px;background:#b91c1c;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Reject</a>
        </div>
        <p style=\"margin:24px 0 0;font-size:13px;color:#6b7280;line-height:1.7;\">In Sprint 3 this email should be triggered by a Service Bus scheduled message and cancelled as soon as a valid HITL response arrives.</p>
      </div>
    </div>
  </body>
</html>
"""
