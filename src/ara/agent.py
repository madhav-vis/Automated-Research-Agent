"""ReAct agent loop — orchestrates Claude with tool calling."""

from __future__ import annotations

import datetime
import json
import logging
import re
from collections.abc import Callable

logger = logging.getLogger(__name__)

import anthropic

from ara.models import Paper, SearchIntentProfile
from ara.presenter import format_tool_status
from ara.tools import TOOL_SCHEMAS, execute_tool

_BASE_SYSTEM_PROMPT = """\
You are a research assistant that finds academic papers on a given topic.
Today's date is {today}.

## Search Intent Profile
{intent_profile_section}

## Your workflow
1. **Plan queries**: Based on the search intent profile (if provided) and the \
user's topic, plan 2-3 targeted search queries with appropriate keywords, \
year ranges, and field filters.
2. **Search iteratively**: Call search_openalex and/or search_arxiv. After each \
batch, use check_coverage to assess whether you have gaps against the intent \
profile. Search again to fill gaps if needed.
3. **Inspect**: Use get_paper_details when you need full abstracts, citation \
counts, or related works for a promising paper.
4. **Filter**: Use filter_results to narrow results by year range when the set \
is too broad.
5. **Finish**: When coverage is sufficient (8+ papers or all intent dimensions \
covered), call finish_search. Then output your final ranked list.

## Critical rules
- NEVER fabricate paper titles, authors, DOIs, or any metadata.
- Only report information returned by the search tools.
- If a search returns no results, say so honestly.
- arXiv papers without DOIs are acceptable — use the arXiv ID as identifier.

## Final output format
When you are done (after calling finish_search), return ONLY a JSON array \
(no markdown fences) where each element has:
{{"title", "authors", "year", "doi", "arxiv_id", "abstract", "citation_count", \
"journal", "source", "relevance_score"}}
"""

MAX_AGENT_TURNS = 25


def build_system_prompt(
    intent_profile: SearchIntentProfile | None = None,
) -> str:
    """Render the system prompt, injecting the intent profile."""
    if intent_profile is None:
        intent_section = "No profile provided — use the topic directly."
    else:
        intent_section = _format_intent_profile(intent_profile)
    return _BASE_SYSTEM_PROMPT.format(
        today=datetime.date.today().isoformat(),
        intent_profile_section=intent_section,
    )


def _format_intent_profile(profile: SearchIntentProfile) -> str:
    """Format a SearchIntentProfile as a readable block for the system prompt."""
    lines = [f"Original query: {profile.original_query}"]
    if profile.domain:
        lines.append(f"Domain: {profile.domain}")
    if profile.application:
        lines.append(f"Application: {profile.application}")
    if profile.methods:
        lines.append(f"Methods of interest: {', '.join(profile.methods)}")
    current_year = datetime.date.today().year
    if profile.year_from:
        lines.append(f"Recency: from {profile.year_from} onward. Only include papers from {profile.year_from} or later.")
    elif profile.recency == "2y":
        cutoff = current_year - 2
        lines.append(f"Recency: last 2 years ({cutoff}-{current_year}). Only include papers from {cutoff} or later.")
    elif profile.recency == "5y":
        cutoff = current_year - 5
        lines.append(f"Recency: last 5 years ({cutoff}-{current_year}). Only include papers from {cutoff} or later.")
    else:
        lines.append("Recency: foundational/seminal (no year restriction)")
    return "\n".join(lines)


def _build_search_prompt(
    topic: str,
    max_results: int,
    intent_profile: SearchIntentProfile | None,
) -> str:
    """Build the initial user message for the search loop."""
    base = (
        f"Find up to {max_results} relevant academic papers on the "
        f"following research topic:\n\n{topic}"
    )
    if intent_profile:
        base += f"\n\nSearch intent profile:\n{_format_intent_profile(intent_profile)}"
    return base


async def run_agent_loop(
    topic: str,
    model: str = "claude-sonnet-4-5",
    max_results: int = 5,
    intent_profile: SearchIntentProfile | None = None,
    max_turns: int | None = None,
    max_search_calls: int | None = None,
    on_status: Callable[[str], None] | None = None,
    on_event: Callable[[str, dict], None] | None = None,
) -> tuple[list[Paper], int]:
    """Run the iterative ReAct loop with coverage-aware searching.

    Returns (papers, iterations_used).
    """
    effective_max_turns = max_turns if max_turns is not None else MAX_AGENT_TURNS
    client = anthropic.AsyncAnthropic()
    system_prompt = build_system_prompt(intent_profile)

    messages: list[dict] = [
        {
            "role": "user",
            "content": _build_search_prompt(topic, max_results, intent_profile),
        }
    ]

    def emit(event_type: str, data: dict | None = None) -> None:
        if on_event:
            on_event(event_type, data or {})

    search_calls = 0
    iterations = 0
    for turn in range(effective_max_turns):
        iterations = turn + 1
        response = await client.messages.create(
            model=model,
            max_tokens=4096,
            system=system_prompt,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text_parts = [
                block.text
                for block in response.content
                if hasattr(block, "text")
            ]
            papers = _parse_final_response("\n".join(text_parts))
            emit("done", {"papers": len(papers)})
            return papers, iterations

        if response.stop_reason == "tool_use":
            tool_results = []
            finish_block = None

            for block in response.content:
                if block.type == "tool_use":
                    human_msg = format_tool_status(block.name, block.input)
                    if human_msg and on_status:
                        on_status(human_msg)

                    if block.name == "finish_search":
                        finish_block = block
                        continue

                    emit("tool_call", {"tool": block.name})

                    if block.name in ("search_openalex", "search_arxiv"):
                        search_calls += 1
                        emit("iteration", {"count": search_calls})

                    result_json = await execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_json,
                    })

            if finish_block:
                finish_result = await execute_tool("finish_search", finish_block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": finish_block.id,
                    "content": finish_result,
                })

            messages.append({"role": "user", "content": tool_results})

            if finish_block:
                response = await client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                )
                messages.append({"role": "assistant", "content": response.content})
                text_parts = [
                    block.text
                    for block in response.content
                    if hasattr(block, "text")
                ]
                papers = _parse_final_response("\n".join(text_parts))
                emit("done", {"papers": len(papers)})
                return papers, iterations

            if max_search_calls is not None and search_calls >= max_search_calls:
                messages.append({
                    "role": "user",
                    "content": (
                        "Search call limit reached. Please output your final "
                        "ranked results as a JSON array now."
                    ),
                })
                response = await client.messages.create(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                )
                messages.append({"role": "assistant", "content": response.content})
                text_parts = [
                    block.text
                    for block in response.content
                    if hasattr(block, "text")
                ]
                papers = _parse_final_response("\n".join(text_parts))
                emit("done", {"papers": len(papers)})
                return papers, iterations

    if on_status:
        on_status("Wrapping up search...")
    messages.append({
        "role": "user",
        "content": (
            "Maximum search iterations reached. Please output your final "
            "ranked results as a JSON array now."
        ),
    })
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=messages,
    )
    text_parts = [
        block.text for block in response.content if hasattr(block, "text")
    ]
    papers = _parse_final_response("\n".join(text_parts))
    emit("done", {"papers": len(papers)})
    return papers, iterations


def _parse_final_response(text: str) -> list[Paper]:
    """Extract the JSON paper list from Claude's final text response."""
    text = text.strip()

    fence = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        logger.debug("No JSON array found in response: %s", text[:200])
        return []

    json_str = text[start : end + 1]
    try:
        items = json.loads(json_str)
    except json.JSONDecodeError:
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
        try:
            items = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.debug("JSON parse failed: %s — text: %s", e, json_str[:300])
            return []

    papers = []
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_authors = item.get("authors", [])
        if isinstance(raw_authors, str):
            raw_authors = [a.strip() for a in raw_authors.split(",") if a.strip()]
        papers.append(
            Paper(
                title=item.get("title", ""),
                authors=raw_authors,
                year=item.get("year"),
                doi=item.get("doi"),
                arxiv_id=item.get("arxiv_id"),
                abstract=item.get("abstract", ""),
                citation_count=item.get("citation_count"),
                journal=item.get("journal", ""),
                source=item.get("source", "unknown"),
                relevance_score=item.get("relevance_score"),
            )
        )
    if not papers:
        logger.debug("Parsed JSON but got 0 papers from %d items", len(items))
    return papers


