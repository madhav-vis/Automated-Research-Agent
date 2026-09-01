# ARA: Automated Research Agent

An agentic CLI that searches academic literature using Claude's tool-use API. ARA implements the ReAct (Reason + Act) pattern from scratch to iteratively query OpenAlex and arXiv, then present real, citable papers in the terminal.

Built to solve a real problem: LLMs hallucinate paper titles, authors, and DOIs when asked to recommend research. ARA sidesteps this entirely - Claude never generates metadata. Instead, it reasons about *what* to search and calls tools that hit real academic APIs. Every title, author list, DOI, and citation count comes directly from OpenAlex or arXiv, not from the model.

![Python](https://img.shields.io/badge/python-3.11+-blue)
![Claude API](https://img.shields.io/badge/Claude-Tool_Use-blueviolet)
![License](https://img.shields.io/badge/license-MIT-green)

## Demo

<p align="center">
  <img src="demo.gif" alt="ARA demo - searching for papers on transformer architectures for protein structure prediction" width="800">
</p>

## How It Works

```
User query
    │
    ▼
┌─────────────────────────────────────────────┐
│  Narrowing Dialogue                         │
│  Claude asks 2-4 clarifying questions to    │
│  build a SearchIntentProfile (domain,       │
│  methods, recency, application area)        │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  ReAct Agent Loop (agent.py)                │
│                                             │
│  while not done:                            │
│    Claude reasons about what to search      │
│    ├── search_openalex(query, filters)      │
│    ├── search_arxiv(query, category)        │
│    ├── get_paper_details(doi/arxiv_id)      │
│    ├── check_coverage(papers, intent)       │
│    └── filter_results(papers, year_range)   │
│    Claude observes results, decides next    │
│    step or calls finish_search              │
│                                             │
│  All paper metadata comes from API          │
│  responses - Claude never generates it      │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Output: Rich table with titles, authors,   │
│  year, journal, citation count, DOI/arXiv   │
│  Optional: save to Zotero                   │
└─────────────────────────────────────────────┘
```

## Key Design Decisions

**No frameworks.** The agent loop is an explicit `while` loop that sends messages to the Claude API, dispatches tool calls, and feeds results back. This makes the control flow readable and debuggable - you can step through every iteration.

**Claude never invents metadata.** The model only *decides* what to search for - actual paper data comes exclusively from tool calls to OpenAlex and arXiv. This is a structural guarantee, not a prompt-engineering one: Claude physically cannot return a paper that doesn't exist in a real database because it never generates metadata itself.

**Coverage-aware search.** The agent doesn't just fire one query and stop. It uses a `check_coverage` tool to assess whether the current paper set covers all dimensions of the user's intent (methods, recency, source diversity), then searches again to fill gaps.

**Intent extraction via dialogue.** Before searching, Claude acts as a research librarian by asking 2-4 targeted questions to extract the user's actual need (subfield, methods of interest, recency preference) into a structured `SearchIntentProfile`. This means a vague query like "attention" becomes a precise multi-query search plan.

## Features

- **Multi-source search** - queries both OpenAlex (200M+ works with citation data) and arXiv (preprints) in parallel
- **Conversational narrowing** - refines vague queries into structured search profiles before searching
- **Citation-aware ranking** - results include citation counts from OpenAlex
- **"Find similar" flow** - select a paper from results and search for related work, with automatic deduplication
- **Zotero integration** - save papers directly to your Zotero library (v7+ via Connector API, v10+ via local API with collection support)
- **Eval suite** - gold-standard retrieval evals with recall@K scoring (10 cases spanning ML, neuroscience, crypto, NLP)
- **Animated terminal UI** - Rich tables and TerminalTextEffects banner with gradient styling

## Quickstart

```bash
# Clone and install
git clone https://github.com/yourusername/ara.git
cd ara
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run
ara 

# With options
ara "EEG-based motor imagery classification" --max 10 -m claude-sonnet-4-5

# Skip the narrowing dialogue
ara "BERT pretraining" --quick
```

## Eval Suite

ARA includes a two-tier evaluation framework to measure retrieval quality:

**Tier 1 - Tool-level**: calls `search_openalex` and `search_arxiv` directly against 10 gold-standard queries and checks recall@K. Runs in seconds.

**Tier 2 - Agent-level**: runs the full ReAct loop with vague, natural-language queries and intent profiles, then checks if the agent finds the target papers through its own reasoning.

```bash
# Free tool-level evals
ara --eval

# Agent-level evals (uses API credits)
ara --eval-agent

# Run a single case
ara --eval-agent --eval-case bert
```

Gold cases include landmark papers (Attention Is All You Need, AlphaFold, BERT, ResNet, LSTM, Bitcoin) and domain-specific papers (BCI cursor control, pre-target visual attention). Each case has a vague `agent_query` that tests whether the agent can reason its way to the right paper without being handed the exact title.

## Architecture

```
src/ara/
├── cli.py          # Typer CLI, async pipeline orchestration
├── agent.py        # ReAct loop - message passing with Claude tool use
├── tools.py        # Tool schemas + async implementations (OpenAlex, arXiv)
├── models.py       # Pydantic models (Paper, SearchIntentProfile)
├── dialogue.py     # Conversational intent extraction via Claude
├── presenter.py    # Rich output formatting
├── prompt.py       # Styled terminal input with ANSI escape sequences
├── banner.py       # Animated ASCII banner (TerminalTextEffects)
├── zotero.py       # Zotero desktop integration (Connector + local API)
├── memory/
│   └── database.py # SQLite for eval run history
└── eval/
    ├── cases.py    # Gold-standard test cases with expected papers
    └── runner.py   # Tier 1 (tool) and Tier 2 (agent) eval runners
```

## Stack

| Component | Choice | Why |
|-----------|--------|-----|
| LLM | Claude (Anthropic API) | Native tool use, structured output |
| Agent pattern | ReAct, hand-rolled | Full control over the loop, no framework overhead |
| Academic data | OpenAlex + arXiv | Free, comprehensive, complementary (journals + preprints) |
| Data models | Pydantic | Type-safe paper metadata |
| CLI | Typer | Declarative argument parsing |
| HTTP | httpx | Async, connection pooling |
| Terminal UI | Rich + TerminalTextEffects | Tables, spinners, animations |
| Reference manager | Zotero | Desktop integration via local APIs |
