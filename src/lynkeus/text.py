"""Small text renderers every screen shares: sparklines, bars, ages, glyphs.

Pure functions over plain values, so the same strings appear in the shell,
in ``to_rich`` output and in tests. Colours are not applied here; the
widgets wrap these in theme variables.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from lynkeus.models import RunState

_BLOCKS = "▁▂▃▄▅▆▇█"

GLYPHS: dict[RunState, str] = {
    RunState.QUEUED: "○",
    RunState.RUNNING: "●",
    RunState.SUCCEEDED: "✓",
    RunState.FAILED: "✗",
    RunState.ARCHIVED: "▫",
}

STYLES: dict[RunState, str] = {
    RunState.QUEUED: "text-muted",
    RunState.RUNNING: "primary",
    RunState.SUCCEEDED: "success",
    RunState.FAILED: "error",
    RunState.ARCHIVED: "text-disabled",
}

LEVEL_GLYPHS: dict[str, tuple[str, str]] = {
    "ok": ("✓", "success"),
    "warn": ("!", "warning"),
    "error": ("✗", "error"),
    "info": ("·", "text-muted"),
}


def spark(values: list[float], width: int | None = None) -> str:
    """Render ``values`` as a one-line sparkline of block characters."""
    if not values:
        return ""
    if width is not None and width > 0 and len(values) > width:
        values = values[-width:]
    low, high = min(values), max(values)
    span = high - low
    out = []
    for value in values:
        ratio = 0.0 if span == 0 else (value - low) / span
        out.append(_BLOCKS[min(len(_BLOCKS) - 1, int(ratio * (len(_BLOCKS) - 1)))])
    return "".join(out)


def bar(done: float, total: float | None, width: int = 24) -> tuple[str, str]:
    """Return ``(filled, rest)`` block strings for a progress bar.

    A ``total`` of ``None`` or zero draws an empty bar; the caller styles the
    two parts differently.
    """
    if not total or total <= 0:
        return "", "━" * width
    ratio = max(0.0, min(1.0, done / total))
    filled = int(round(ratio * width))
    return "━" * filled, "━" * (width - filled)


def age(when: datetime | None, now: datetime | None = None) -> str:
    """Compact relative time: ``41m``, ``2h``, ``yesterday``, ``Mon``, ``Aug 28``."""
    if when is None:
        return ""
    now = now or datetime.now(when.tzinfo)
    if when.tzinfo is not None and now.tzinfo is None:
        now = now.replace(tzinfo=when.tzinfo)
    if when.tzinfo is None and now.tzinfo is not None:
        when = when.replace(tzinfo=now.tzinfo)
    delta = now - when
    if delta < timedelta(0):
        return when.strftime("%H:%M")
    if delta < timedelta(minutes=1):
        return "now"
    if delta < timedelta(hours=1):
        return f"{int(delta.total_seconds() // 60)}m"
    if delta < timedelta(hours=24):
        return f"{int(delta.total_seconds() // 3600)}h"
    if delta < timedelta(days=2):
        return "yesterday"
    if delta < timedelta(days=7):
        return when.strftime("%a")
    if when.year == now.year:
        return when.strftime("%b %d").replace(" 0", " ")
    return when.strftime("%Y-%m-%d")


def elapsed(start: datetime | None, end: datetime | None = None) -> str:
    """``HH:MM:SS`` between two instants (``end`` defaults to now)."""
    if start is None:
        return ""
    end = end or datetime.now(start.tzinfo)
    seconds = max(0, int((end - start).total_seconds()))
    hours, rest = divmod(seconds, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def clip(text: str, width: int) -> str:
    """Cut ``text`` to ``width`` columns with an ellipsis."""
    text = " ".join(str(text).split())
    if len(text) <= width:
        return text
    return text[: max(0, width - 1)] + "…"


def count(value: float | None) -> str:
    """Thousands-separated integer, or an empty string."""
    if value is None:
        return ""
    return f"{int(value):,}"
