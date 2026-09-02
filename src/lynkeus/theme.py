"""The one theme every project shares: Flexoki, dark and light.

Flexoki is one of Textual's built-in themes. The dark variant here uses the
Flexoki 400 accent shades, which the Flexoki specification assigns to dark
mode, instead of the 600 shades Textual's copy ships with; the light variant
uses the 600 shades on paper. ``t`` toggles between them in the shell.
"""

from __future__ import annotations

from textual.theme import Theme

FLEXOKI_DARK = Theme(
    name="lynkeus-dark",
    primary="#4385BE",
    secondary="#3AA99F",
    accent="#8B7EC8",
    warning="#D0A215",
    error="#D14D41",
    success="#879A39",
    foreground="#CECDC3",
    background="#100F0F",
    surface="#1C1B1A",
    panel="#282726",
    dark=True,
    variables={
        "border": "#403E3C",
        "text-muted": "#878580",
        "text-disabled": "#575653",
        "footer-key-background": "#282726",
        "footer-key-foreground": "#FFFCF0",
    },
)

FLEXOKI_LIGHT = Theme(
    name="lynkeus-light",
    primary="#205EA6",
    secondary="#24837B",
    accent="#5E409D",
    warning="#AD8301",
    error="#AF3029",
    success="#66800B",
    foreground="#343331",
    background="#FFFCF0",
    surface="#F2F0E5",
    panel="#E6E4D9",
    dark=False,
    variables={
        "border": "#CECDC3",
        "text-muted": "#6F6E69",
        "text-disabled": "#B7B5AC",
        "footer-key-background": "#E6E4D9",
        "footer-key-foreground": "#100F0F",
    },
)

THEMES = (FLEXOKI_DARK, FLEXOKI_LIGHT)
