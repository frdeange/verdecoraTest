from __future__ import annotations

from html import escape

from .email_templates import HitlEmailContext, build_action_url


def render_reminder_email(context: HitlEmailContext, pending_hours: int = 24) -> str:
    accept_url = build_action_url(context, "accept")
    modify_url = build_action_url(context, "modify")
    reject_url = build_action_url(context, "reject")

    return f"""<!DOCTYPE html>
<html lang=\"en\">
  <body style=\"margin:0;padding:24px;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;color:#111827;\">
    <div style=\"max-width:720px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;\">
      <div style=\"padding:24px 32px;background:#78350f;color:#ffffff;\">
        <div style=\"font-size:13px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;\">24h reminder</div>
        <h1 style=\"margin:12px 0 4px;font-size:26px;\">Decision still pending for albarán {escape(context.albaran_number)}</h1>
        <p style=\"margin:0;font-size:15px;line-height:1.6;\">This HITL request has been waiting for {pending_hours} hours and still requires a decision.</p>
      </div>
      <div style=\"padding:32px;\">
        <p style=\"margin:0 0 16px;font-size:15px;line-height:1.7;\"><strong>Supplier:</strong> {escape(context.supplier_name)}<br /><strong>PO reference:</strong> {escape(context.po_reference)}</p>
        <p style=\"margin:0 0 24px;font-size:15px;line-height:1.7;color:#374151;\">Please review the discrepancy and complete the action before the escalation threshold is reached.</p>
        <div style=\"text-align:center;\">
          <a href=\"{accept_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 22px;background:#166534;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Accept</a>
          <a href=\"{modify_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 22px;background:#d97706;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Modify</a>
          <a href=\"{reject_url}\" style=\"display:inline-block;margin:0 8px 12px;padding:14px 22px;background:#b91c1c;border-radius:999px;color:#ffffff;text-decoration:none;font-weight:700;\">Reject</a>
        </div>
        <p style=\"margin:24px 0 0;font-size:13px;color:#6b7280;line-height:1.7;\">Reminder logic belongs in the orchestrator layer; this template is only the notification surface.</p>
      </div>
    </div>
  </body>
</html>
"""
