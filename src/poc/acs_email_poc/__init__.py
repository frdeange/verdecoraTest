"""ACS Email HITL proof-of-concept package."""

from .email_templates import DiscrepancyLine, HitlEmailContext, render_hitl_email
from .escalation_template import render_escalation_email
from .reminder_template import render_reminder_email
from .send_email import ACSMessageConfig, build_hitl_email_message, send_hitl_email

__all__ = [
    "ACSMessageConfig",
    "DiscrepancyLine",
    "HitlEmailContext",
    "build_hitl_email_message",
    "render_escalation_email",
    "render_hitl_email",
    "render_reminder_email",
    "send_hitl_email",
]
