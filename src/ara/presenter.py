"""Rich CLI output formatting for search results."""

from __future__ import annotations

from rich.color import Color
from rich.console import Console
from rich.style import Style
from rich.table import Table
from rich.text import Text

from ara.banner import animate_header
from ara.models import Paper, SearchIntentProfile

console = Console()


def _gradient_text(text: str, start_rgb: tuple[int, int, int], end_rgb: tuple[int, int, int]) -> Text:
    """Apply a smooth RGB gradient across a text string."""
    result = Text()
    n = max(len(text) - 1, 1)
    for i, char in enumerate(text):
        r = start_rgb[0] + (end_rgb[0] - start_rgb[0]) * i // n
        g = start_rgb[1] + (end_rgb[1] - start_rgb[1]) * i // n
        b = start_rgb[2] + (end_rgb[2] - start_rgb[2]) * i // n
        result.append(char, style=Style(color=Color.from_rgb(r, g, b), bold=True))
    return result


def gradient_header(text: str) -> Text:
    """Create a gradient header in red-to-pink style."""
    return _gradient_text(text, (255, 0, 0), (255, 105, 180))


def _format_citations(count: int | None) -> str:
    """Color citation counts by magnitude."""
    if count is None:
        return "[dim]—[/dim]"
    if count >= 100:
        return f"[bold green]{count}[/bold green]"
    if count >= 10:
        return f"[yellow]{count}[/yellow]"
    return f"[dim]{count}[/dim]"


def display_results(papers: list[Paper], topic: str) -> None:
    """Render the final ranked papers as a Rich table."""
    console.print()
    animate_header("Search Results")
    console.print(f"  [bold]{topic}[/bold]\n")

    if not papers:
        console.print("[yellow]No papers found.[/yellow]")
        return

    table = Table(show_header=True, header_style="bold bright_cyan", show_lines=True)
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Title")
    table.add_column("Authors", max_width=30)
    table.add_column("Year", justify="center", width=6)
    table.add_column("Journal", max_width=20)
    table.add_column("Cited", justify="right", width=6)
    table.add_column("Identifier", max_width=32)

    for i, paper in enumerate(papers, 1):
        authors_str = ", ".join(paper.authors[:3])
        if len(paper.authors) > 3:
            authors_str += f" +{len(paper.authors) - 3}"

        if paper.doi:
            identifier = paper.doi
        elif paper.arxiv_id:
            identifier = f"arXiv:{paper.arxiv_id}"
        else:
            identifier = "—"

        table.add_row(
            str(i),
            paper.title,
            authors_str,
            str(paper.year or "—"),
            paper.journal or "—",
            _format_citations(paper.citation_count),
            identifier,
        )

    console.print(table)


def display_intent_profile(profile: SearchIntentProfile) -> None:
    """Render the search intent profile as a Rich panel."""
    lines: list[str] = []
    if profile.domain:
        lines.append(f"[bold]Domain:[/bold] {profile.domain}")
    if profile.application:
        lines.append(f"[bold]Application:[/bold] {profile.application}")
    if profile.methods:
        lines.append(f"[bold]Methods:[/bold] {', '.join(profile.methods)}")
    if profile.year_from:
        lines.append(f"[bold]Recency:[/bold] From {profile.year_from} onward")
    else:
        recency_labels = {"2y": "Last 2 years", "5y": "Last 5 years", "foundational": "Foundational"}
        lines.append(f"[bold]Recency:[/bold] {recency_labels.get(profile.recency, profile.recency)}")
    console.print()
    animate_header("Search Profile")
    for line in lines:
        console.print(f"  {line}")
    console.print()





def format_tool_status(tool_name: str, tool_input: dict) -> str | None:
    """Map a tool call to a human-readable status line, or None to hide it."""
    if tool_name == "search_openalex":
        q = tool_input.get("query", "")
        if len(q) > 50:
            q = q[:50] + "..."
        return f'search_openalex("{q}")'
    if tool_name == "search_arxiv":
        q = tool_input.get("query", "")
        if len(q) > 50:
            q = q[:50] + "..."
        return f'search_arxiv("{q}")'
    if tool_name == "get_paper_details":
        return f'get_paper_details({tool_input.get("identifier", "")})'
    if tool_name == "filter_results":
        return "filter_results(...)"
    if tool_name == "finish_search":
        return None
    if tool_name == "check_coverage":
        return None
    return None


