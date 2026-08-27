"""ASCII art banner and animated text effects for ARA CLI."""

from __future__ import annotations

import sys

from rich.color import Color
from rich.console import Console
from rich.style import Style
from rich.text import Text

_ARA_ASCII = """\
     █████╗   ██████╗    █████╗
    ██╔══██╗  ██╔══██╗  ██╔══██╗
    ███████║  ██████╔╝  ███████║
    ██╔══██║  ██╔══██╗  ██╔══██║
    ██║  ██║  ██║  ██║  ██║  ██║
    ╚═╝  ╚═╝  ╚═╝  ╚═╝  ╚═╝  ╚═╝"""

_SUBTITLE = "  Automated Research Agent — AI-powered academic paper search"

_GRADIENT = ((255, 0, 0), (255, 20, 147), (255, 105, 180))


def _gradient_text(text: str) -> Text:
    """Apply red-pink gradient across text."""
    result = Text()
    n = max(len(text) - 1, 1)
    start, end = _GRADIENT[0], _GRADIENT[2]
    for i, char in enumerate(text):
        r = start[0] + (end[0] - start[0]) * i // n
        g = start[1] + (end[1] - start[1]) * i // n
        b = start[2] + (end[2] - start[2]) * i // n
        result.append(char, style=Style(color=Color.from_rgb(r, g, b), bold=True))
    return result


def _is_interactive() -> bool:
    return sys.stdout.isatty()


def _terminal_config():
    from terminaltexteffects.engine.terminal import TerminalConfig

    return TerminalConfig(
        canvas_width=-1, canvas_height=-1, frame_rate=60,
        no_color=False, xterm_colors=False, no_eol=False,
        no_restore_cursor=False, tab_width=4,
        ignore_terminal_dimensions=False, reuse_canvas=False,
        wrap_text=False, anchor_canvas="sw", anchor_text="sw",
        existing_color_handling="ignore",
    )


def _static_fallback(console: Console | None = None) -> None:
    console = console or Console()
    for line in _ARA_ASCII.splitlines():
        console.print(_gradient_text(line))
    console.print(_gradient_text(_SUBTITLE))


def show_animated_banner() -> None:
    """Display animated MiddleOut banner (interactive mode landing page)."""
    console = Console()
    console.print()

    if not _is_interactive():
        _static_fallback(console)
        console.print()
        return

    try:
        from terminaltexteffects.effects.effect_middleout import MiddleOut, MiddleOutConfig
        from terminaltexteffects.utils.easing import in_out_sine
        from terminaltexteffects.utils.graphics import Color as TColor
        from terminaltexteffects.utils.graphics import Gradient

        full_text = _ARA_ASCII + "\n" + _SUBTITLE
        config = MiddleOutConfig(
            starting_color=TColor("ffffff"),
            expand_direction="vertical",
            center_movement_speed=0.6,
            full_movement_speed=0.6,
            center_easing=in_out_sine,
            full_easing=in_out_sine,
            final_gradient_stops=(TColor("ff0000"), TColor("ff1493"), TColor("ff69b4")),
            final_gradient_steps=(12,),
            final_gradient_direction=Gradient.Direction.VERTICAL,
        )
        effect = MiddleOut(full_text, effect_config=config, terminal_config=_terminal_config())
        with effect.terminal_output() as terminal:
            for frame in effect:
                terminal.print(frame)
    except Exception:
        _static_fallback(console)

    console.print()


def static_banner(console: Console) -> None:
    """Display static gradient banner (direct invocation mode)."""
    console.print()
    _static_fallback(console)
    console.print()


def animate_header(text: str) -> None:
    """Display a section header with ColorShift animation."""
    console = Console()
    console.print()

    if not _is_interactive():
        console.print(_gradient_text(text))
        return

    try:
        from terminaltexteffects.effects.effect_colorshift import ColorShift, ColorShiftConfig
        from terminaltexteffects.utils.graphics import Color as TColor
        from terminaltexteffects.utils.graphics import Gradient

        config = ColorShiftConfig(
            gradient_stops=(TColor("ff0000"), TColor("ff1493"), TColor("ff69b4")),
            final_gradient_stops=(TColor("ff0000"), TColor("ff1493"), TColor("ff69b4")),
            final_gradient_steps=(12,),
            gradient_steps=(12,),
            cycles=1,
            gradient_frames=1,
            no_loop=True,
            travel_direction=Gradient.Direction.RADIAL,
            final_gradient_direction=Gradient.Direction.VERTICAL,
            skip_final_gradient=False,
            reverse_travel_direction=False,
            no_travel=False,
        )
        effect = ColorShift(text, effect_config=config, terminal_config=_terminal_config())
        with effect.terminal_output() as terminal:
            for frame in effect:
                terminal.print(frame)
    except Exception:
        console.print(_gradient_text(text))


def animate_highlight(text: str) -> None:
    """Display text with a Highlight sweep animation."""
    console = Console()

    if not _is_interactive():
        console.print(_gradient_text(text))
        return

    try:
        from terminaltexteffects.effects.effect_highlight import Highlight, HighlightConfig
        from terminaltexteffects.utils.argutils import CharacterGroup
        from terminaltexteffects.utils.graphics import Color as TColor
        from terminaltexteffects.utils.graphics import Gradient

        config = HighlightConfig(
            final_gradient_stops=(TColor("ff0000"), TColor("ff1493"), TColor("ff69b4")),
            final_gradient_steps=(12,),
            final_gradient_direction=Gradient.Direction.VERTICAL,
            highlight_brightness=1.75,
            highlight_width=8,
            highlight_direction=CharacterGroup.DIAGONAL_BOTTOM_LEFT_TO_TOP_RIGHT,
        )
        effect = Highlight(text, effect_config=config, terminal_config=_terminal_config())
        with effect.terminal_output() as terminal:
            for frame in effect:
                terminal.print(frame)
    except Exception:
        console.print(_gradient_text(text))
