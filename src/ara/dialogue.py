"""Narrowing dialogue — conversational intent extraction using Claude."""

from __future__ import annotations

import anthropic
from rich.console import Console

from ara.models import SearchIntentProfile
from ara.prompt import styled_input

MAX_DIALOGUE_TURNS = 4

DIALOGUE_SYSTEM_PROMPT = """\
You are a research librarian helping a user refine their academic paper search.

## Your goal
Ask brief, conversational questions to understand what the user really needs.
You may ask up to {max_turns} questions. Cover these dimensions as relevant
(skip any that are obvious from context):
- Specific subfield or application area
- Recency preference (recent work vs foundational/seminal papers)
- Particular methods, techniques, or frameworks of interest

## Rules
- Be conversational, NOT a form. One question at a time.
- If the user's initial query is already very specific, ask fewer questions.
- When you have enough information, call the submit_profile tool.
- NEVER ask more than {max_turns} questions total.
- If the user gives a terse answer, make reasonable inferences and move on.

## Recency rules
- If the user says "recent" or does not specify a time preference, default \
recency to "5y" (last 5 years).
- If the user specifies an exact year cutoff (e.g. "after 2022", "from 2020", \
"papers since 2023"), set the year_from field to that year instead of using \
the recency enum.

## Identified topic
When submitting the profile, always fill in the identified_topic field with \
the properly identified full topic name. For example, if the user typed \
"BCIs", set identified_topic to "Brain-Computer Interfaces". Use the \
canonical name for the field, not the user's shorthand.
"""

_SUBMIT_PROFILE_SCHEMA: dict = {
    "name": "submit_profile",
    "description": (
        "Submit the structured search intent profile once you have gathered "
        "enough information from the user."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "original_query": {"type": "string"},
            "identified_topic": {
                "type": "string",
                "description": (
                    "The properly identified full topic name, e.g. "
                    "'Brain-Computer Interfaces' if the user typed 'BCIs'"
                ),
            },
            "domain": {
                "type": "string",
                "description": "Academic domain/field",
            },
            "application": {
                "type": "string",
                "description": "Specific application area",
            },
            "methods": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Methods, techniques, or frameworks of interest",
            },
            "recency": {
                "type": "string",
                "enum": ["2y", "5y", "foundational"],
                "description": "How recent should papers be",
            },
            "year_from": {
                "type": "integer",
                "description": (
                    "Specific start year if user requests one, "
                    "e.g. 2022 for 'after 2022'"
                ),
            },
        },
        "required": ["original_query", "identified_topic", "domain"],
    },
}


async def run_narrowing_dialogue(
    topic: str,
    model: str = "claude-sonnet-4-5",
    console: Console | None = None,
) -> SearchIntentProfile:
    """Conduct a conversational narrowing dialogue with the user.

    Uses Claude to generate questions and a submit_profile tool to produce
    the structured SearchIntentProfile.
    """
    client = anthropic.AsyncAnthropic()
    console = console or Console()
    system = DIALOGUE_SYSTEM_PROMPT.format(max_turns=MAX_DIALOGUE_TURNS)

    messages: list[dict] = [
        {
            "role": "user",
            "content": f"The user wants to search for papers on: {topic}",
        }
    ]

    for _turn in range(MAX_DIALOGUE_TURNS + 1):
        spinner = console.status("[bold]Thinking...[/bold]", spinner="dots")
        spinner.start()
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                system=system,
                tools=[_SUBMIT_PROFILE_SCHEMA],
                messages=messages,
            )
        except Exception:
            spinner.stop()
            return _fallback_profile(topic)
        spinner.stop()

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "tool_use":
            for block in response.content:
                if block.type == "tool_use" and block.name == "submit_profile":
                    return _extract_profile(block.input, topic)

        if response.stop_reason == "end_turn":
            text = "".join(
                b.text for b in response.content if hasattr(b, "text")
            )
            if text.strip():
                console.print(f"\n  [bold #ff0000]Agent:[/bold #ff0000] {text.strip()}\n")
                answer = styled_input(console=console)
                if not answer.strip():
                    break
                console.print()
                messages.append({"role": "user", "content": answer})

    messages.append({
        "role": "user",
        "content": "Please submit the profile now based on what you know.",
    })
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            tools=[_SUBMIT_PROFILE_SCHEMA],
            messages=messages,
        )
    except Exception:
        return _fallback_profile(topic)

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_profile":
            return _extract_profile(block.input, topic)

    return _fallback_profile(topic)


def _extract_profile(tool_input: dict, topic: str) -> SearchIntentProfile:
    """Parse the submit_profile tool arguments into a SearchIntentProfile."""
    return SearchIntentProfile(
        original_query=tool_input.get("original_query", topic),
        identified_topic=tool_input.get("identified_topic", ""),
        domain=tool_input.get("domain", ""),
        application=tool_input.get("application", ""),
        methods=tool_input.get("methods", []),
        recency=tool_input.get("recency", "5y"),
        year_from=tool_input.get("year_from"),
    )


def _fallback_profile(topic: str) -> SearchIntentProfile:
    """Create a minimal profile when the dialogue is skipped or fails."""
    return SearchIntentProfile(original_query=topic)
