# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run

```bash
pip install -e .          # editable install (use --break-system-packages if needed on macOS)
ara "your topic"      # run the CLI
ara "topic" --max 5 -m claude-sonnet-4-5   # with options
```

Requires `ANTHROPIC_API_KEY` in the environment. No other API keys needed — OpenAlex, arXiv, and CrossRef are all free/unauthenticated.

## Test individual components

```bash
# OpenAlex search (no API key, no cost)
python3 -c "import asyncio; from ara.tools import search_openalex; print(asyncio.run(search_openalex('test', max_results=2)))"

# arXiv search
python3 -c "import asyncio; from ara.tools import search_arxiv; print(asyncio.run(search_arxiv('test', max_results=2)))"

# DOI validation
python3 -c "import asyncio; from ara.tools import validate_doi; print(asyncio.run(validate_doi('10.1038/s41586-021-03819-2')))"
```

No test suite exists yet. Verify changes by running the CLI end-to-end and checking Rich output.

## Architecture

This is a **ReAct-pattern agentic CLI**: Claude reasons about what to search, calls tools, observes results, and decides next steps. The agent loop is an explicit while-loop — no frameworks.

### Core invariant

**Claude never generates paper metadata.** Titles, authors, DOIs, and citation counts come exclusively from API responses. This is enforced by:
1. The system prompt in `agent.py` forbids fabrication
2. Tool functions in `tools.py` return only API data
3. **Double validation**: Claude calls `validate_doi` during the loop, AND `validator.py` re-validates all DOIs post-loop before display

### Data flow

```
cli.py  →  agent.py (ReAct loop with Claude)  →  tools.py (API calls)
                                                      ↓
cli.py  ←  presenter.py (Rich output)  ←  validator.py (post-loop DOI check)
```

### Key modules

- **`agent.py`** — The ReAct loop. Sends messages to Claude with `TOOL_SCHEMAS`, executes tool_use blocks via `execute_tool`, feeds results back, repeats until `stop_reason == "end_turn"`. `_parse_final_response` extracts the JSON paper list from Claude's final text.
- **`tools.py`** — Three tool schemas (passed to Claude) and their implementations. `execute_tool` dispatches by name and catches errors as JSON for Claude to see. OpenAlex abstracts arrive as inverted indexes and are reconstructed by `_reconstruct_abstract`.
- **`models.py`** — Pydantic models. `Paper.doi_validated` is set only by the validator, never by Claude.

### Adding a new tool

1. Add the schema dict to `TOOL_SCHEMAS` in `tools.py`
2. Write the async implementation function returning `list[dict]` or `dict`
3. Add the entry to the `dispatch` dict in `execute_tool`
4. Update `SYSTEM_PROMPT` in `agent.py` to reference the new tool

### External APIs

| API | Endpoint | Auth | Notes |
|-----|----------|------|-------|
| OpenAlex | `api.openalex.org/works` | None (polite pool via `mailto`) | 10 req/s, DOIs include `https://doi.org/` prefix (stripped in code) |
| arXiv | `export.arxiv.org/api/query` | None | Returns Atom XML, `follow_redirects=True` required |
| CrossRef | `api.crossref.org/works/{doi}` | None | Used for DOI validation only |
