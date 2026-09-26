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


def spoken_summary(b: Business, score: int, avg_comp: int | None, fixes: list[Fix], ranks: dict[str, int | None]) -> str:
    """Voice-first answer (Alexa+ / assistants): ≤3 short sentences, numbers spoken plainly, one action."""
    parts = [f"{b.name} scores {score} out of 100 on Google visibility."]
    if avg_comp is not None:
        if avg_comp > score:
            parts.append(f"Nearby competitors average {avg_comp}, so it's {avg_comp - score} points behind.")
        else:
            parts.append(f"That's ahead of nearby competitors, who average {avg_comp}.")
    first_rank = next(iter(ranks.items()), None)
    if first_rank and first_rank[1] and first_rank[1] > 3:
        parts.append(f"It's number {first_rank[1]} for {first_rank[0]}.")
    if fixes:
        import re
        title = re.sub(r"\s*\([^)]*\)", "", fixes[0].title).rstrip(".")
        effort = fixes[0].effort.replace("min", "minutes").replace("1 hour", "an hour").replace("1 day", "a day")
        parts.append(f"The first thing to fix: {title}. It takes about {effort}.")
    return " ".join(parts[:5])
