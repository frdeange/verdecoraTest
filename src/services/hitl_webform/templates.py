from __future__ import annotations

import json
from html import escape
from typing import Any


def _render_discrepancy_rows(line_comparisons: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for comparison in line_comparisons:
        status = str(comparison.get("status") or "unknown")
        highlight = "#fef2f2" if status not in {"match", "tolerance"} else "#f0fdf4"
        rows.append(
            "<tr>"
            f'<td style="padding:10px;border-bottom:1px solid #e5e7eb;background:{highlight};">{escape(str(comparison.get("line_number", "-")))}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #e5e7eb;background:{highlight};">{escape(str(comparison.get("field", "-")))}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #e5e7eb;background:{highlight};">{escape(str(comparison.get("extracted_value", "-")))}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #e5e7eb;background:{highlight};">{escape(str(comparison.get("bc_value", "-")))}</td>'
            f'<td style="padding:10px;border-bottom:1px solid #e5e7eb;background:{highlight};font-weight:600;">{escape(status)}</td>'
            "</tr>"
        )
    return "".join(rows) or '<tr><td colspan="5" style="padding:10px;">No discrepancies found.</td></tr>'


def render_review_page(albaran_id: str, review_record: dict[str, Any], reviewer_email: str) -> str:
    extraction = review_record.get("pipeline_result", {}).get("extraction", {})
    validation = review_record.get("pipeline_result", {}).get("validation", {})
    line_comparisons = validation.get("line_comparisons", [])
    discrepancies = validation.get("discrepancies", [])
    payload_json = escape(json.dumps(review_record, ensure_ascii=False, indent=2))
    discrepancy_list = (
        "".join(f"<li>{escape(str(item))}</li>" for item in discrepancies) or "<li>Sin discrepancias textuales.</li>"
    )
    return f"""<!DOCTYPE html>
<html lang=\"es\">
  <body style=\"font-family:Arial,Helvetica,sans-serif;margin:0;background:#f3f4f6;color:#111827;\">
    <div style=\"max-width:1080px;margin:0 auto;padding:32px;\">
      <h1 style=\"margin-bottom:8px;color:#14532d;\">Revisión HITL · {escape(albaran_id)}</h1>
      <p style=\"margin-top:0;\">Revisor autenticado: <strong>{escape(reviewer_email)}</strong></p>
      <div style=\"display:grid;grid-template-columns:1fr 1fr;gap:24px;\">
        <section style=\"background:#fff;border-radius:12px;padding:20px;border:1px solid #e5e7eb;\">
          <h2>Extracción</h2>
          <pre style=\"white-space:pre-wrap;word-break:break-word;\">{escape(json.dumps(extraction, ensure_ascii=False, indent=2))}</pre>
        </section>
        <section style=\"background:#fff;border-radius:12px;padding:20px;border:1px solid #e5e7eb;\">
          <h2>Validación / BC</h2>
          <ul>{discrepancy_list}</ul>
          <table style=\"width:100%;border-collapse:collapse;\">
            <thead>
              <tr>
                <th style=\"text-align:left;padding:10px;border-bottom:1px solid #d1d5db;\">Línea</th>
                <th style=\"text-align:left;padding:10px;border-bottom:1px solid #d1d5db;\">Campo</th>
                <th style=\"text-align:left;padding:10px;border-bottom:1px solid #d1d5db;\">Extraído</th>
                <th style=\"text-align:left;padding:10px;border-bottom:1px solid #d1d5db;\">BC</th>
                <th style=\"text-align:left;padding:10px;border-bottom:1px solid #d1d5db;\">Estado</th>
              </tr>
            </thead>
            <tbody>{_render_discrepancy_rows(line_comparisons)}</tbody>
          </table>
        </section>
      </div>
      <section style=\"margin-top:24px;background:#fff;border-radius:12px;padding:20px;border:1px solid #e5e7eb;\">
        <h2>Decisión</h2>
        <form id=\"decision-form\">
          <label><input type=\"radio\" name=\"decision\" value=\"approve\" checked> Aprobar</label>
          <label style=\"margin-left:16px;\"><input type=\"radio\" name=\"decision\" value=\"reject\"> Rechazar</label>
          <label style=\"margin-left:16px;\"><input type=\"radio\" name=\"decision\" value=\"modify\"> Modificar</label>
          <div style=\"margin-top:16px;\">
            <textarea id=\"notes\" rows=\"4\" style=\"width:100%;\" placeholder=\"Notas del revisor\"></textarea>
          </div>
          <button type=\"submit\" style=\"margin-top:16px;padding:12px 20px;background:#166534;color:#fff;border:none;border-radius:999px;\">Enviar decisión</button>
        </form>
        <pre id=\"decision-result\" style=\"margin-top:16px;background:#f9fafb;padding:12px;border-radius:8px;\"></pre>
      </section>
      <section style=\"margin-top:24px;background:#fff;border-radius:12px;padding:20px;border:1px solid #e5e7eb;\">
        <h2>Contexto bruto</h2>
        <pre style=\"white-space:pre-wrap;word-break:break-word;\">{payload_json}</pre>
      </section>
    </div>
    <script>
      const form = document.getElementById('decision-form');
      const result = document.getElementById('decision-result');
      form.addEventListener('submit', async (event) => {{
        event.preventDefault();
        const decision = new FormData(form).get('decision');
        const notes = document.getElementById('notes').value;
        const response = await fetch(window.location.pathname + '/decide', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json', 'Authorization': window.localStorage.getItem('hitlAuthorization') || '' }},
          body: JSON.stringify({{ decision, notes }})
        }});
        result.textContent = await response.text();
      }});
    </script>
  </body>
</html>"""
