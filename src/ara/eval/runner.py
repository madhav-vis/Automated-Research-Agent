"""Eval runner — scores tool retrieval against gold-standard cases.

Tier 1 (tool-level): calls search_openalex/search_arxiv directly. Free, fast.
Tier 2 (agent-level): runs full agent loop. Costs API credits, run sparingly.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
import uuid

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ara.eval.cases import GOLD_SET, GoldCase, ExpectedPaper
from ara.tools import search_openalex, search_arxiv


def _normalize(s: str) -> str:
    """Normalize an identifier for comparison."""
    s = s.strip().lower()
    s = s.replace("https://doi.org/", "")
    s = s.replace("http://doi.org/", "")
    s = s.replace("10.48550/arxiv.", "")
    s = s.replace("arxiv:", "")
    s = re.sub(r"v\d+$", "", s)
    return s


def _paper_matches(paper: dict, expected: ExpectedPaper) -> bool:
    """Check if a result paper matches an expected paper by DOI, arXiv ID, or title."""
    paper_doi = _normalize(paper.get("doi") or "")
    paper_arxiv = _normalize(paper.get("arxiv_id") or "")
    paper_title = (paper.get("title") or "").lower()

    for doi in expected.dois:
        if paper_doi and _normalize(doi) == paper_doi:
            return True

    for aid in expected.arxiv_ids:
        if paper_arxiv and _normalize(aid) == paper_arxiv:
            return True

    if expected.title_contains and expected.title_contains.lower() in paper_title:
        return True

    return False


async def _run_tool_case(case: GoldCase, k: int = 10) -> dict:
    """Run a single case against both tools and score recall@K."""
    start = time.monotonic()

    openalex_results, arxiv_results = await asyncio.gather(
        search_openalex(case.query, max_results=k),
        search_arxiv(case.query, max_results=k),
    )

    combined = openalex_results + arxiv_results
    duration = time.monotonic() - start

    hits = []
    misses = []
    for expected in case.expected_papers:
        found = any(_paper_matches(p, expected) for p in combined)
        if found:
            hits.append(expected.title_contains)
        else:
            misses.append(expected.title_contains)

    total_expected = len(case.expected_papers)
    recall = len(hits) / total_expected if total_expected else 1.0
    passed = recall >= case.min_recall

    return {
        "case_name": case.name,
        "query": case.query,
        "passed": passed,
        "recall": round(recall, 2),
        "hits": hits,
        "misses": misses,
        "openalex_count": len(openalex_results),
        "arxiv_count": len(arxiv_results),
        "duration_seconds": round(duration, 1),
    }


async def run_tool_evals(
    k: int = 10,
    console: Console | None = None,
) -> dict:
    """Run all gold cases at the tool level. No LLM calls — free and fast."""
    console = console or Console()
    console.print("\n[bold blue]Running Tool-Level Evals (Tier 1 — no API cost)[/bold blue]\n")

    results = []
    for case in GOLD_SET:
        result = await _run_tool_case(case, k=k)
        results.append(result)

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    recalls = [r["recall"] for r in results]
    avg_recall = sum(recalls) / len(recalls) if recalls else 0.0

    table = Table(show_header=True, header_style="bold cyan", show_lines=True)
    table.add_column("Case", min_width=24)
    table.add_column("Result", justify="center", width=8)
    table.add_column(f"Recall@{k}", justify="center", width=10)
    table.add_column("Hits", min_width=20)
    table.add_column("Misses", min_width=20)
    table.add_column("Results", justify="center", width=10)
    table.add_column("Time", justify="right", width=7)

    for r in results:
        status = "[green]PASS[/green]" if r["passed"] else "[red]FAIL[/red]"
        hits_str = ", ".join(h[:30] for h in r["hits"]) or "-"
        misses_str = ", ".join(m[:30] for m in r["misses"]) or "-"
        count = f"{r['openalex_count']}+{r['arxiv_count']}"
        table.add_row(
            r["case_name"],
            status,
            f"{r['recall'] * 100:.0f}%",
            hits_str,
            misses_str,
            count,
            f"{r['duration_seconds']}s",
        )

    console.print(table)

    summary = (
        f"[bold]Pass rate:[/bold] {passed}/{total} "
        f"({round(passed / total * 100) if total else 0}%) | "
        f"[bold]Mean Recall@{k}:[/bold] {avg_recall * 100:.0f}%"
    )
    console.print()
    console.print(Panel(summary, title="Eval Summary", border_style="green"))

    return {
        "tier": "tool",
        "k": k,
        "pass_rate": passed / total if total else 0.0,
        "mean_recall": round(avg_recall, 2),
        "passed_count": passed,
        "total_cases": total,
        "individual_results": results,
    }


async def run_agent_evals(
    model: str = "claude-sonnet-4-5",
    console: Console | None = None,
) -> dict:
    """Run gold cases through the full agent loop. Costs API credits."""
    from ara.agent import run_agent_loop

    console = console or Console()
    console.print("\n[bold yellow]Running Agent-Level Evals (Tier 2 — uses API credits)[/bold yellow]\n")

    results = []
    for case in GOLD_SET:
        query = case.agent_query or case.query
        start = time.monotonic()
        try:
            papers, iterations = await run_agent_loop(
                query,
                model=model,
                max_results=5,
                intent_profile=None,
            )
        except Exception as e:
            results.append({
                "case_name": case.name,
                "query": query,
                "passed": False,
                "recall": 0.0,
                "hits": [],
                "misses": [ep.title_contains for ep in case.expected_papers],
                "papers_found": 0,
                "iterations": 0,
                "duration_seconds": round(time.monotonic() - start, 1),
                "error": str(e),
            })
            continue

        duration = time.monotonic() - start
        paper_dicts = [{"doi": p.doi, "arxiv_id": p.arxiv_id, "title": p.title} for p in papers]

        hits = []
        misses = []
        for expected in case.expected_papers:
            found = any(_paper_matches(p, expected) for p in paper_dicts)
            if found:
                hits.append(expected.title_contains)
            else:
                misses.append(expected.title_contains)

        total_expected = len(case.expected_papers)
        recall = len(hits) / total_expected if total_expected else 1.0

        results.append({
            "case_name": case.name,
            "query": query,
            "passed": recall >= case.min_recall,
            "recall": round(recall, 2),
            "hits": hits,
            "misses": misses,
            "papers_found": len(papers),
            "iterations": iterations,
            "duration_seconds": round(duration, 1),
        })

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    recalls = [r["recall"] for r in results]
    avg_recall = sum(recalls) / len(recalls) if recalls else 0.0

    table = Table(show_header=True, header_style="bold cyan", show_lines=True)
    table.add_column("Case", min_width=24)
    table.add_column("Result", justify="center", width=8)
    table.add_column("Recall", justify="center", width=8)
    table.add_column("Papers", justify="center", width=8)
    table.add_column("Iters", justify="center", width=6)
    table.add_column("Time", justify="right", width=7)

    for r in results:
        status = "[green]PASS[/green]" if r["passed"] else "[red]FAIL[/red]"
        table.add_row(
            r["case_name"],
            status,
            f"{r['recall'] * 100:.0f}%",
            str(r.get("papers_found", "?")),
            str(r.get("iterations", "?")),
            f"{r['duration_seconds']}s",
        )

    console.print(table)

    errors = [(r["case_name"], r["error"]) for r in results if r.get("error")]
    if errors:
        console.print()
        for name, err in errors:
            console.print(f"  [red]{name}: {err}[/red]")

    summary = (
        f"[bold]Pass rate:[/bold] {passed}/{total} | "
        f"[bold]Mean Recall:[/bold] {avg_recall * 100:.0f}%"
    )
    console.print()
    console.print(Panel(summary, title="Agent Eval Summary", border_style="yellow"))

    return {
        "tier": "agent",
        "pass_rate": passed / total if total else 0.0,
        "mean_recall": round(avg_recall, 2),
        "passed_count": passed,
        "total_cases": total,
        "individual_results": results,
    }
