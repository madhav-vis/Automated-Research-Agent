"""Claude Code-style input prompts for ARA CLI."""

from __future__ import annotations

import sys

from rich.console import Console
from rich.text import Text

_RULE_STYLE = "dim #ff1493"


def _print_rule(console: Console) -> None:
    """Print a thick horizontal separator spanning the terminal width."""
    w = max(console.width - 1, 1)
    console.print(Text("━" * w, style=_RULE_STYLE))


def styled_input(prompt_text: str | None = None, console: Console | None = None) -> str:
    """Show context text, then a persistent input box with top/bottom rules.

    After the user presses Enter, the rules and prompt arrow collapse —
    only the typed text remains in the scrollback.
    """
    console = console or Console()
    if prompt_text:
        console.print(f"  {prompt_text}")
    _print_rule(console)
    console.print()
    _print_rule(console)
    sys.stdout.write("\033[2A\r")
    sys.stdout.flush()
    prompt = Text("> ", style="bold #ff1493")
    result = console.input(prompt)
    # cursor is now on line after bottom rule
    # move up and clear: bottom rule, input line, top rule
    sys.stdout.write("\033[2K\033[1A\033[2K\033[1A\033[2K\033[1A\033[2K\r")
    sys.stdout.flush()
    console.print(f"\n  [bold #ff69b4]User:[/bold #ff69b4] {result}")
    return result


def styled_confirm(question: str, console: Console | None = None) -> bool:
    """Ask a yes/no question with persistent input box. Loops until valid answer."""
    console = console or Console()
    console.print(f"  {question} [dim](y/n)[/dim]")
    while True:
        _print_rule(console)
        console.print()
        _print_rule(console)
        sys.stdout.write("\033[2A\r")
        sys.stdout.flush()
        prompt = Text("> ", style="bold #ff1493")
        answer = console.input(prompt).strip().lower()
        sys.stdout.write("\033[2K\033[1A\033[2K\033[1A\033[2K\033[1A\033[2K\r")
        sys.stdout.flush()
        console.print()
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        console.print("  [dim]Please answer y or n.[/dim]")
