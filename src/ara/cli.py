"""CLI entry point — Typer app for automated-research-agent."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import typer
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from rich.console import Console

from ara.agent import run_agent_loop
from ara.banner import animate_highlight, show_animated_banner, static_banner
from ara.dialogue import run_narrowing_dialogue
from ara.eval.runner import run_tool_evals, run_agent_evals
from ara.models import Paper
from ara.presenter import (
    display_intent_profile,
    display_results,
)
from ara.prompt import styled_confirm, styled_input

app = typer.Typer(
    name="ara",
    help="AI-powered academic paper search with hallucination firewall.",
)
console = Console()


def _paper_id(paper: Paper) -> str | None:
    """Return DOI or arXiv ID for dedup, or None if neither exists."""
    return paper.doi or paper.arxiv_id or None


def _dedup(papers: list[Paper], seen_ids: set[str]) -> list[Paper]:
    """Filter out already-seen papers and register new ones."""
    new: list[Paper] = []
    for p in papers:
        pid = _paper_id(p)
        if pid is None or pid not in seen_ids:
            new.append(p)
            if pid:
                seen_ids.add(pid)
    return new


@app.command()
def search(
    topic: str = typer.Argument(None, help="Research topic to search"),
    max_results: int = typer.Option(5, "--max", "-n", help="Maximum papers to return"),
    model: str = typer.Option(
        "claude-sonnet-4-5",
        "--model",
        "-m",
        help="Claude model to use",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug logs (CrossRef status codes, retries)"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Skip narrowing dialogue and search immediately"),
    eval_mode: bool = typer.Option(False, "--eval", help="Run tool-level evals (free, no LLM)"),
    eval_agent: bool = typer.Option(False, "--eval-agent", help="Run agent-level evals (uses API credits)"),
) -> None:
    """Search for academic papers on a topic using an AI research agent."""
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s: %(message)s")

    if eval_mode:
        asyncio.run(_run_tool_eval())
        return
    if eval_agent:
        asyncio.run(_run_agent_eval(model))
        return

    if not topic:
        show_animated_banner()
        topic = styled_input("What would you like to research?", console=console)
        if not topic.strip():
            raise typer.Exit(0)
        asyncio.run(_search(topic, max_results, model, quick, show_banner=False))
        return

    asyncio.run(_search(topic, max_results, model, quick))


async def _search(topic: str, max_results: int, model: str, quick: bool, show_banner: bool = True) -> None:
    """Async pipeline: dialogue -> search -> validate -> dedup -> display -> feedback."""
    seen_ids: set[str] = set()

    intent_profile = None

    if show_banner:
        static_banner(console)
    console.print(f"  Topic: [bold]{topic}[/bold]")
    console.print(f"  Model: [dim]{model}[/dim]")
    console.print(f"  Max results: [dim]{max_results}[/dim]\n")

    if not quick and intent_profile is None:
        console.print("[bold]Let me ask a few questions to refine your search...[/bold]")
        intent_profile = await run_narrowing_dialogue(
            topic, model=model, console=console
        )
        display_intent_profile(intent_profile)

        count_str = styled_input(
            f"How many papers would you like? [dim](default: {max_results})[/dim]",
            console=console,
        )
        if count_str.strip().isdigit():
            max_results = int(count_str.strip())

    console.print()
    _spinner = console.status("[bold]Finding papers...[/bold]", spinner="dots")
    _spinner.start()

    def on_status(msg: str) -> None:
        _spinner.stop()
        console.print(f"  [bright_blue]→[/bright_blue] [dim]{msg}[/dim]")
        _spinner.update(f"[bold]{msg}[/bold]")
        _spinner.start()

    papers, iterations_used = await run_agent_loop(
        topic,
        model=model,
        max_results=max_results,
        intent_profile=intent_profile,
        on_status=on_status,
    )
    _spinner.stop()
    console.print()
    console.print(f"  [bold]Found {len(papers)} papers.[/bold]")
    console.print()

    displayable = _dedup(papers, seen_ids)
    display_topic = (intent_profile.identified_topic if intent_profile and intent_profile.identified_topic else topic)
    display_results(displayable, display_topic)

    _collect_feedback(displayable)

    if displayable:
        if styled_confirm("Would you like to find more papers on the topic?", console=console):
            pick = styled_input("Which paper number? [dim](default: 1)[/dim]", console=console) or "1"
            if pick.strip().isdigit():
                idx = int(pick.strip()) - 1
                if 0 <= idx < len(displayable):
                    count_str = styled_input("How many more papers? [dim](default: 5)[/dim]", console=console) or "5"
                    count = int(count_str) if count_str.strip().isdigit() else 5
                    await _find_similar(displayable[idx], model=model, max_results=count, seen_ids=seen_ids)
                else:
                    console.print(f"  [yellow]Paper {idx + 1} not found.[/yellow]")


def _collect_feedback(papers: list[Paper]) -> tuple[int, int]:
    """Prompt user to save papers, optionally to Zotero."""
    if not papers:
        return 0, 0

    answer = styled_input(
        "Would you like to save any of these papers? Enter paper numbers to save [dim](comma-separated, or Enter to skip)[/dim]",
        console=console,
    )

    selected: list[Paper] = []
    if answer.strip():
        for part in answer.split(","):
            part = part.strip()
            if part.isdigit():
                idx = int(part) - 1
                if 0 <= idx < len(papers):
                    selected.append(papers[idx])

    if not selected:
        return 0, len(papers)

    from ara.zotero import is_zotero_running, save_papers_to_zotero

    if is_zotero_running():
        if styled_confirm("Save to Zotero?", console=console):
            saved, location = save_papers_to_zotero(selected)
            if saved:
                console.print(f"\n  [green]Saved {saved} paper(s) to Zotero → {location}.[/green]")
                if location == "My Library":
                    console.print("  [dim]Tip: create an \"ARA Imports\" collection in Zotero and papers will auto-sort there next time.[/dim]")
            else:
                console.print("\n  [yellow]Could not save to Zotero. Check that Zotero is running and try again.[/yellow]")
        else:
            console.print(f"\n  [dim]Skipped saving {len(selected)} paper(s).[/dim]")
    else:
        console.print("\n  [yellow]Zotero is not running.[/yellow] Start Zotero desktop and re-run to save papers.")

    return len(selected), len(papers) - len(selected)


async def _find_similar(paper: Paper, model: str, max_results: int = 5, seen_ids: set[str] | None = None) -> None:
    """Run another agent loop to find papers similar to the selected one."""
    if seen_ids is None:
        seen_ids = set()

    query = f"Papers similar to: {paper.title}"
    if paper.abstract:
        query += f". {paper.abstract[:200]}"

    console.print(f"\n  [bold]Searching for papers similar to:[/bold] {paper.title}\n")

    _spinner = console.status("[bold]Finding similar papers...[/bold]", spinner="dots")
    _spinner.start()

    def on_status(msg: str) -> None:
        _spinner.stop()
        console.print(f"  [bright_blue]→[/bright_blue] [dim]{msg}[/dim]")
        _spinner.update(f"[bold]{msg}[/bold]")
        _spinner.start()

    similar_papers, _ = await run_agent_loop(
        query,
        model=model,
        max_results=max_results,
        on_status=on_status,
    )
    _spinner.stop()

    new_papers = _dedup(similar_papers, seen_ids)
    display_results(new_papers, f"Similar to: {paper.title}")

    _collect_feedback(new_papers)


async def _run_tool_eval() -> None:
    """Run free tool-level evals."""
    static_banner(console)
    await run_tool_evals(console=console)


async def _run_agent_eval(model: str) -> None:
    """Run agent-level evals (costs API credits)."""
    static_banner(console)
    await run_agent_evals(model=model, console=console)
