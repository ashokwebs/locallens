"""Short, WhatsApp-ready summaries in English and Telugu (template-based, so the facts can't drift)."""
from __future__ import annotations

from .models import Business, Fix


def summary_en(b: Business, score: int, avg_comp: int | None, fixes: list[Fix]) -> str:
    lines = [f"*{b.name}*: Google Visibility Score *{score}/100*"]
    if avg_comp is not None:
        gap = avg_comp - score
        lines.append(f"Nearby competitors average {avg_comp}/100" +
                     (f" (you're {gap} points behind)." if gap > 0 else " (you're ahead, so keep it that way)."))
    if fixes:
        lines.append("\n*Fix these first:*")
        for i, f in enumerate(fixes[:3], 1):
            lines.append(f"{i}. {f.title} ({f.effort})")
    lines.append("\nFull report: sent with this message.")
    return "\n".join(lines)


def summary_te(b: Business, score: int, avg_comp: int | None, fixes_te: list[str]) -> str:
    lines = [f"*{b.name}*: గూగుల్ విజిబిలిటీ స్కోర్ *{score}/100*"]
    if avg_comp is not None:
        lines.append(f"పక్కన ఉన్న పోటీదారుల సగటు స్కోర్: {avg_comp}/100.")
    if fixes_te:
        lines.append("\n*ముందుగా చేయాల్సినవి:*")
        for i, t in enumerate(fixes_te[:3], 1):
            lines.append(f"{i}. {t}")
    return "\n".join(lines)
