"""Tool schemas for Claude function calling and their API implementations."""

from __future__ import annotations

import datetime
import json
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

_USER_AGENT = "ARA/0.1 (academic-search-tool)"
_TIMEOUT = 30.0
_POLITE_MAILTO = "madhav56rg@gmail.com"

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "search_openalex",
        "description": (
            "Search OpenAlex for academic papers. Returns titles, authors, "
            "abstracts, DOIs, citation counts, and publication years."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5,
                },
                "year_range": {
                    "type": "string",
                    "description": "Year range filter, e.g. '2020-2024'",
                },
                "field_filter": {
                    "type": "string",
                    "description": "Field of study filter, e.g. 'Computer Science'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_arxiv",
        "description": (
            "Search arXiv for preprints and papers. Returns titles, authors, "
            "abstracts, arXiv IDs, and categories."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return",
                    "default": 5,
                },
                "category": {
                    "type": "string",
                    "description": "arXiv category filter, e.g. 'cs.AI', 'cs.LG', 'q-bio.NC'",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "finish_search",
        "description": (
            "Signal that the search is complete and you are ready to output "
            "final results. Call this when you have sufficient coverage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why the search is complete",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_paper_details",
        "description": (
            "Fetch detailed metadata for a single paper by DOI or arXiv ID. "
            "Returns full abstract, citation count, publication venue, and "
            "related work DOIs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "identifier": {
                    "type": "string",
                    "description": "DOI (e.g. '10.1038/...') or arXiv ID (e.g. '2301.12345')",
                },
            },
            "required": ["identifier"],
        },
    },
    {
        "name": "check_coverage",
        "description": (
            "Assess how well the current paper set covers the search intent. "
            "Deterministic analysis — no API call. Reports method coverage, "
            "recency distribution, paper type match, and gaps."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "current_papers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "year": {"type": "integer"},
                            "abstract": {"type": "string"},
                            "doi": {"type": "string"},
                            "arxiv_id": {"type": "string"},
                            "source": {"type": "string"},
                        },
                    },
                    "description": "Papers collected so far",
                },
                "intent_profile": {
                    "type": "object",
                    "properties": {
                        "original_query": {"type": "string"},
                        "domain": {"type": "string"},
                        "application": {"type": "string"},
                        "methods": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "recency": {"type": "string"},
                    },
                    "description": "The search intent profile",
                },
            },
            "required": ["current_papers", "intent_profile"],
        },
    },
    {
        "name": "filter_results",
        "description": (
            "Filter a list of papers by year range. "
            "Deterministic — no API call. Returns the filtered subset."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "papers": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "year": {"type": "integer"},
                            "doi": {"type": "string"},
                            "arxiv_id": {"type": "string"},
                            "abstract": {"type": "string"},
                            "citation_count": {"type": "integer"},
                            "source": {"type": "string"},
                            "authors": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                        },
                    },
                    "description": "List of paper objects to filter",
                },
                "year_min": {
                    "type": "integer",
                    "description": "Minimum publication year (inclusive)",
                },
                "year_max": {
                    "type": "integer",
                    "description": "Maximum publication year (inclusive)",
                },
            },
            "required": ["papers"],
        },
    },
]


async def search_openalex(
    query: str,
    max_results: int = 10,
    year_range: str | None = None,
    field_filter: str | None = None,
) -> list[dict[str, Any]]:
    """Search OpenAlex API and return paper metadata."""
    params: dict[str, Any] = {
        "search": query,
        "per_page": min(max_results, 200),
        "mailto": _POLITE_MAILTO,
    }

    filters: list[str] = []
    if year_range:
        filters.append(f"publication_year:{year_range}")
    if field_filter:
        filters.append(f"topics.display_name.search:{field_filter}")
    if filters:
        params["filter"] = ",".join(filters)

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            "https://api.openalex.org/works",
            params=params,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()
        data = resp.json()

    papers = []
    for item in data.get("results") or []:
        raw_doi = item.get("doi") or ""
        doi = raw_doi.replace("https://doi.org/", "") if raw_doi else None

        authors = [
            a.get("author", {}).get("display_name", "")
            for a in (item.get("authorships") or [])
        ]

        ids = item.get("ids") or {}
        openalex_id = ids.get("openalex", "")
        arxiv_url = ids.get("arxiv", "")
        arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else None

        primary_loc = item.get("primary_location") or {}
        source_info = primary_loc.get("source") or {}
        journal = source_info.get("display_name") or ""

        papers.append({
            "title": item.get("title") or "",
            "authors": authors,
            "year": item.get("publication_year"),
            "doi": doi,
            "arxiv_id": arxiv_id,
            "abstract": _reconstruct_abstract(item.get("abstract_inverted_index")),
            "citation_count": item.get("cited_by_count"),
            "journal": journal,
            "source": "openalex",
        })
    return papers


def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """Rebuild abstract text from OpenAlex's inverted-index format."""
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words))


async def search_arxiv(
    query: str,
    max_results: int = 10,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Search arXiv API (Atom XML) and return parsed paper metadata."""
    search_query = f"all:{query}"
    if category:
        search_query = f"cat:{category} AND all:{query}"

    params = {
        "search_query": search_query,
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            "https://export.arxiv.org/api/query",
            params=params,
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(resp.text)

    papers = []
    for entry in root.findall("atom:entry", ns):
        id_url = entry.findtext("atom:id", "", ns)
        arxiv_id = id_url.split("/abs/")[-1] if "/abs/" in id_url else id_url

        title = " ".join(entry.findtext("atom:title", "", ns).split())
        abstract = " ".join(entry.findtext("atom:summary", "", ns).split())
        authors = [
            a.findtext("atom:name", "", ns)
            for a in entry.findall("atom:author", ns)
        ]
        published = entry.findtext("atom:published", "", ns)
        year = int(published[:4]) if published and len(published) >= 4 else None

        papers.append({
            "title": title,
            "authors": authors,
            "year": year,
            "doi": None,
            "arxiv_id": arxiv_id,
            "abstract": abstract,
            "citation_count": None,
            "source": "arxiv",
        })
    return papers


async def finish_search(reason: str = "") -> dict[str, str]:
    """Signal tool — no external API call."""
    return {
        "status": "acknowledged",
        "message": (
            f"Search concluded. Reason: {reason or 'not specified'}. "
            "Please output your final ranked results as a JSON array."
        ),
    }


async def get_paper_details(identifier: str) -> dict[str, Any]:
    """Fetch detailed metadata for one paper by DOI or arXiv ID."""
    is_doi = "/" in identifier
    if is_doi:
        return await _get_details_by_doi(identifier)
    return await _get_details_by_arxiv(identifier)


async def _get_details_by_doi(doi: str) -> dict[str, Any]:
    """Fetch paper details from OpenAlex by DOI."""
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"https://api.openalex.org/works/doi:{doi}",
            params={"mailto": _POLITE_MAILTO},
            headers={"User-Agent": _USER_AGENT},
        )
        if resp.status_code != 200:
            return {"error": f"OpenAlex returned {resp.status_code} for DOI {doi}"}
        item = resp.json()

    raw_doi = item.get("doi") or ""
    clean_doi = raw_doi.replace("https://doi.org/", "") if raw_doi else doi

    authors = [
        a.get("author", {}).get("display_name", "")
        for a in (item.get("authorships") or [])
    ]

    ids = item.get("ids") or {}
    arxiv_url = ids.get("arxiv", "")
    arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else None

    primary_location = item.get("primary_location") or {}
    source_info = primary_location.get("source") or {}
    journal = source_info.get("display_name") or ""

    related = []
    for rw in (item.get("related_works") or [])[:5]:
        related.append(rw)

    return {
        "title": item.get("title") or "",
        "authors": authors,
        "year": item.get("publication_year"),
        "doi": clean_doi,
        "arxiv_id": arxiv_id,
        "abstract": _reconstruct_abstract(item.get("abstract_inverted_index")),
        "citation_count": item.get("cited_by_count"),
        "journal": journal,
        "related_works": related,
        "source": "openalex",
    }


async def _get_details_by_arxiv(arxiv_id: str) -> dict[str, Any]:
    """Fetch paper details from arXiv API, cross-referenced with OpenAlex."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(
            "https://export.arxiv.org/api/query",
            params={"id_list": arxiv_id},
            headers={"User-Agent": _USER_AGENT},
        )
        resp.raise_for_status()

    root = ET.fromstring(resp.text)
    entry = root.find("atom:entry", ns)
    if entry is None:
        return {"error": f"arXiv returned no entry for {arxiv_id}"}

    title = " ".join(entry.findtext("atom:title", "", ns).split())
    abstract = " ".join(entry.findtext("atom:summary", "", ns).split())
    authors = [
        a.findtext("atom:name", "", ns) for a in entry.findall("atom:author", ns)
    ]
    published = entry.findtext("atom:published", "", ns)
    year = int(published[:4]) if published and len(published) >= 4 else None

    result: dict[str, Any] = {
        "title": title,
        "authors": authors,
        "year": year,
        "doi": None,
        "arxiv_id": arxiv_id,
        "abstract": abstract,
        "citation_count": None,
        "journal": "",
        "related_works": [],
        "source": "arxiv",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            oa_resp = await client.get(
                "https://api.openalex.org/works",
                params={
                    "filter": f"ids.arxiv:{arxiv_id}",
                    "mailto": _POLITE_MAILTO,
                },
                headers={"User-Agent": _USER_AGENT},
            )
        if oa_resp.status_code == 200:
            oa_data = oa_resp.json()
            oa_results = oa_data.get("results") or []
            if oa_results:
                oa_item = oa_results[0]
                result["citation_count"] = oa_item.get("cited_by_count")
                raw_doi = oa_item.get("doi") or ""
                if raw_doi:
                    result["doi"] = raw_doi.replace("https://doi.org/", "")
                primary_loc = oa_item.get("primary_location") or {}
                source_info = primary_loc.get("source") or {}
                result["journal"] = source_info.get("display_name") or ""
                for rw in (oa_item.get("related_works") or [])[:5]:
                    result["related_works"].append(rw)
    except (httpx.HTTPError, httpx.TimeoutException):
        pass

    return result



async def check_coverage(
    current_papers: list[dict[str, Any]],
    intent_profile: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic coverage analysis — no AI, no API calls."""
    total = len(current_papers)
    methods = intent_profile.get("methods") or []

    if not methods and not intent_profile.get("domain") and not intent_profile.get("application"):
        if total >= 5:
            return {
                "total_papers": total,
                "recommendation": "sufficient",
                "reason": "No specific intent profile; paper count threshold met",
                "gaps": [],
            }
        return {
            "total_papers": total,
            "recommendation": "search_more",
            "reason": f"Only {total} papers found, need at least 5",
            "gaps": [f"Need {5 - total} more papers"],
        }

    recency = intent_profile.get("recency", "5y")

    covered = []
    uncovered = []
    for method in methods:
        method_lower = method.lower()
        found = any(
            method_lower in (p.get("title") or "").lower()
            or method_lower in (p.get("abstract") or "").lower()
            for p in current_papers
        )
        (covered if found else uncovered).append(method)

    current_year = datetime.date.today().year
    if recency == "2y":
        cutoff = current_year - 2
    elif recency == "5y":
        cutoff = current_year - 5
    else:
        cutoff = 0

    recent_count = sum(
        1 for p in current_papers if (p.get("year") or 0) >= cutoff
    )
    recency_score = recent_count / total if total else 0.0

    source_counts: dict[str, int] = {}
    for p in current_papers:
        s = p.get("source", "unknown")
        source_counts[s] = source_counts.get(s, 0) + 1

    gaps: list[str] = []
    if uncovered:
        gaps.append(f"No papers covering: {', '.join(uncovered)}")
    if recency_score < 0.5 and recency != "foundational":
        gaps.append(
            f"Only {recent_count}/{total} papers from last "
            f"{'2' if recency == '2y' else '5'} years"
        )
    if len(source_counts) < 2:
        gaps.append("Papers from only one source — consider diversifying")

    sufficient = total >= 8 and not uncovered and recency_score >= 0.5
    return {
        "total_papers": total,
        "method_coverage": {"covered": covered, "uncovered": uncovered},
        "recency_score": round(recency_score, 2),
        "recency_detail": f"{recent_count} of {total} papers meet recency preference",
        "source_diversity": source_counts,
        "gaps": gaps,
        "recommendation": "sufficient" if sufficient else "search_more",
    }


async def filter_results(
    papers: list[dict[str, Any]],
    year_min: int | None = None,
    year_max: int | None = None,
) -> list[dict[str, Any]]:
    """Deterministic filter over a list of paper dicts."""
    result = papers
    if year_min is not None:
        result = [p for p in result if (p.get("year") or 0) >= year_min]
    if year_max is not None:
        result = [p for p in result if (p.get("year") or 9999) <= year_max]
    return result


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch a tool call to the right implementation.

    Returns a JSON string to feed back to Claude as a tool_result.
    """
    dispatch = {
        "search_openalex": search_openalex,
        "search_arxiv": search_arxiv,
        "finish_search": finish_search,
        "get_paper_details": get_paper_details,
        "check_coverage": check_coverage,
        "filter_results": filter_results,
    }
    func = dispatch.get(name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        result = await func(**arguments)
        return json.dumps(result, default=str)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
