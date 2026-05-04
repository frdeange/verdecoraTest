from __future__ import annotations

from datetime import UTC, datetime
from html import escape
from typing import Any

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse

app = FastAPI(title="ACS Email HITL Web Form Stub", version="0.1.0")
DECISIONS: dict[str, dict[str, Any]] = {}


def _page(title: str, body: str) -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang=\"en\">
  <body style=\"margin:0;padding:24px;background:#f3f4f6;font-family:Arial,Helvetica,sans-serif;color:#111827;\">
    <div style=\"max-width:760px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;\">
      <div style=\"padding:24px 32px;background:#14532d;color:#ffffff;\">
        <div style=\"font-size:13px;letter-spacing:0.08em;text-transform:uppercase;opacity:0.85;\">HITL web form stub</div>
        <h1 style=\"margin:12px 0 0;font-size:28px;\">{escape(title)}</h1>
      </div>
      <div style=\"padding:32px;\">{body}</div>
    </div>
  </body>
</html>
"""
    return HTMLResponse(content=html)


def _confirmation_form(albaran_id: str, action: str, token: str) -> HTMLResponse:
    body = f"""
<p style=\"font-size:15px;line-height:1.7;color:#374151;\">You are about to <strong>{escape(action)}</strong> the discrepancy workflow for albarán <strong>{escape(albaran_id)}</strong>.</p>
<form method=\"post\" action=\"/api/hitl/{escape(albaran_id)}/submit\" style=\"margin-top:24px;\">
  <input type=\"hidden\" name=\"action\" value=\"{escape(action)}\" />
  <input type=\"hidden\" name=\"token\" value=\"{escape(token)}\" />
  <label style=\"display:block;font-weight:700;margin-bottom:8px;\">Comment (optional)</label>
  <textarea name=\"comment\" rows=\"4\" style=\"width:100%;padding:12px;border:1px solid #d1d5db;border-radius:10px;\" placeholder=\"Add context for the audit trail\"></textarea>
  <button type=\"submit\" style=\"margin-top:20px;padding:14px 22px;background:#166534;border:0;border-radius:999px;color:#ffffff;font-weight:700;cursor:pointer;\">Confirm {escape(action)}</button>
</form>
"""
    return _page(f"Confirm {action.title()} decision", body)


@app.get("/api/hitl/{albaran_id}/accept", response_class=HTMLResponse)
def accept_page(albaran_id: str, token: str = Query(...)) -> HTMLResponse:
    return _confirmation_form(albaran_id, "accept", token)


@app.get("/api/hitl/{albaran_id}/reject", response_class=HTMLResponse)
def reject_page(albaran_id: str, token: str = Query(...)) -> HTMLResponse:
    return _confirmation_form(albaran_id, "reject", token)


@app.get("/api/hitl/{albaran_id}/modify", response_class=HTMLResponse)
def modify_page(albaran_id: str, token: str = Query(...)) -> HTMLResponse:
    body = f"""
<p style=\"font-size:15px;line-height:1.7;color:#374151;\">Adjust quantities for albarán <strong>{escape(albaran_id)}</strong>. In production this page would preload the discrepancy lines and validate the caller identity.</p>
<form method=\"post\" action=\"/api/hitl/{escape(albaran_id)}/submit\" style=\"margin-top:24px;\">
  <input type=\"hidden\" name=\"action\" value=\"modify\" />
  <input type=\"hidden\" name=\"token\" value=\"{escape(token)}\" />
  <label style=\"display:block;font-weight:700;margin-bottom:8px;\">Corrected quantity</label>
  <input type=\"number\" step=\"0.01\" min=\"0\" name=\"modified_quantity\" required style=\"width:100%;padding:12px;border:1px solid #d1d5db;border-radius:10px;\" />
  <label style=\"display:block;font-weight:700;margin:20px 0 8px;\">Reason</label>
  <textarea name=\"comment\" rows=\"4\" style=\"width:100%;padding:12px;border:1px solid #d1d5db;border-radius:10px;\" placeholder=\"Explain the approved adjustment\"></textarea>
  <button type=\"submit\" style=\"margin-top:20px;padding:14px 22px;background:#d97706;border:0;border-radius:999px;color:#ffffff;font-weight:700;cursor:pointer;\">Submit modification</button>
</form>
"""
    return _page("Modify quantities", body)


@app.post("/api/hitl/{albaran_id}/submit", response_class=HTMLResponse)
def submit_decision(
    albaran_id: str,
    action: str = Form(...),
    token: str = Form(...),
    comment: str = Form(""),
    modified_quantity: float | None = Form(default=None),
) -> HTMLResponse:
    DECISIONS[albaran_id] = {
        "action": action,
        "token": token,
        "comment": comment,
        "modified_quantity": modified_quantity,
        "submitted_at": datetime.now(UTC).isoformat(),
    }
    body = f"""
<p style=\"font-size:15px;line-height:1.7;color:#374151;\">Decision captured for albarán <strong>{escape(albaran_id)}</strong>.</p>
<ul style=\"font-size:15px;line-height:1.8;color:#111827;\">
  <li><strong>Action:</strong> {escape(action)}</li>
  <li><strong>Modified quantity:</strong> {escape(str(modified_quantity)) if modified_quantity is not None else 'n/a'}</li>
  <li><strong>Comment:</strong> {escape(comment) if comment else 'n/a'}</li>
  <li><strong>Stub status:</strong> In-memory only — replace with Cosmos DB + Service Bus event emission in Sprint 3.</li>
</ul>
"""
    return _page("Decision recorded", body)
