"""Zotero integration — save papers to a local Zotero library."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import httpx

from ara.models import Paper

_ZOTERO_PORT = 23119
_ZOTERO_BASE = f"http://localhost:{_ZOTERO_PORT}"
_AUTH_FILE = Path.home() / ".research_cli" / "zotero_auth.json"


def is_zotero_running() -> bool:
    """Check whether Zotero desktop is running and accepting connections."""
    try:
        resp = httpx.get(f"{_ZOTERO_BASE}/connector/ping", timeout=2)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def _get_zotero_version() -> tuple[int, ...] | None:
    """Return the running Zotero version as a tuple, e.g. (9, 0, 6)."""
    try:
        resp = httpx.get(
            f"{_ZOTERO_BASE}/api/users/0/items?limit=1",
            headers={"Accept": "application/json"},
            timeout=3,
        )
        ver = resp.headers.get("x-zotero-version", "")
        return tuple(int(x) for x in ver.split(".")) if ver else None
    except Exception:
        return None


def _parse_author(name: str) -> dict:
    """Parse 'First Last' into Zotero creator dict."""
    parts = name.strip().rsplit(" ", 1)
    if len(parts) == 2:
        return {"creatorType": "author", "firstName": parts[0], "lastName": parts[1]}
    return {"creatorType": "author", "name": name.strip()}


def _paper_to_zotero_item(paper: Paper) -> dict:
    """Map a Paper to Zotero API item format."""
    item_type = "journalArticle" if paper.journal else "preprint"

    extra_parts: list[str] = []
    if paper.citation_count is not None:
        extra_parts.append(f"Citation Count: {paper.citation_count}")
    extra_parts.append(f"Source: {paper.source}")

    item: dict = {
        "itemType": item_type,
        "title": paper.title,
        "creators": [_parse_author(a) for a in paper.authors],
        "abstractNote": paper.abstract,
        "date": str(paper.year) if paper.year else "",
        "publicationTitle": paper.journal,
        "extra": "\n".join(extra_parts),
        "tags": [{"tag": "ARA Import"}],
    }

    if paper.doi:
        item["DOI"] = paper.doi
    if paper.arxiv_id:
        item["url"] = f"https://arxiv.org/abs/{paper.arxiv_id}"

    return item


def _load_auth() -> dict | None:
    if not _AUTH_FILE.exists():
        return None
    try:
        data = json.loads(_AUTH_FILE.read_text())
        if data.get("server_id") and data.get("local_api_key"):
            return data
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def _save_auth(server_id: str, local_api_key: str) -> None:
    _AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    _AUTH_FILE.write_text(json.dumps({
        "server_id": server_id,
        "local_api_key": local_api_key,
    }))


def _clear_auth() -> None:
    if _AUTH_FILE.exists():
        _AUTH_FILE.unlink()


def _find_collection_key(name: str) -> str | None:
    """Find an existing collection by name via the local API (read-only, no auth)."""
    try:
        resp = httpx.get(f"{_ZOTERO_BASE}/api/users/0/collections", timeout=5)
        if resp.status_code == 200:
            for coll in resp.json():
                if coll["data"]["name"] == name:
                    return coll["key"]
    except Exception:
        pass
    return None


def _save_via_pyzotero(
    papers: list[Paper],
    collection_name: str,
) -> tuple[int, str]:
    """Save via pyzotero local API (Zotero 10+ with write support)."""
    from pyzotero import zotero

    cached = _load_auth()

    if cached:
        zot = zotero.Zotero(
            "0", "user", local=True,
            server_id=cached["server_id"],
            local_api_key=cached["local_api_key"],
        )
    else:
        server_id = str(uuid.uuid4())
        zot = zotero.Zotero("0", "user", local=True, server_id=server_id)
        auth = zot.authorize_local("ARA Research Agent")
        _save_auth(server_id, auth["key"])

    collection_key = _find_collection_key(collection_name)
    if collection_key is None:
        try:
            resp = zot.create_collections([{"name": collection_name}])
            if resp and "successful" in resp:
                first = next(iter(resp["successful"].values()))
                collection_key = first["key"]
        except Exception:
            pass

    items = [_paper_to_zotero_item(p) for p in papers]
    if collection_key:
        for item in items:
            item["collections"] = [collection_key]

    resp = zot.create_items(items)
    if resp and "successful" in resp:
        count = len(resp["successful"])
        location = f"{collection_name} collection" if collection_key else "My Library"
        return count, location

    return 0, ""


def _save_via_connector(
    papers: list[Paper],
    collection_name: str,
) -> tuple[int, str]:
    """Save via Connector API (Zotero 7+). Targets personal library."""
    collection_key = _find_collection_key(collection_name)

    items = [_paper_to_zotero_item(p) for p in papers]
    for item in items:
        if item["itemType"] == "preprint":
            item["itemType"] = "report"
        if collection_key:
            item["collections"] = [collection_key]

    payload = {
        "items": items,
        "uri": "https://ara-research-agent",
        "sessionID": str(uuid.uuid4()),
        "libraryID": 1,
    }

    resp = httpx.post(
        f"{_ZOTERO_BASE}/connector/saveItems",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=10,
    )

    if resp.status_code in (200, 201):
        location = f"{collection_name} collection" if collection_key else "My Library"
        return len(papers), location
    return 0, ""


def save_papers_to_zotero(
    papers: list[Paper],
    collection_name: str = "ARA Imports",
) -> tuple[int, str]:
    """Save papers to the user's personal Zotero library.

    Returns (count_saved, location_description).
    Zotero 10+: uses local API with auth (can create collections).
    Zotero 7-9: uses Connector API (saves to personal library;
                 uses existing collection if found).
    """
    if not papers:
        return 0, ""

    version = _get_zotero_version()
    is_v10 = version is not None and version >= (10,)

    if is_v10:
        try:
            return _save_via_pyzotero(papers, collection_name)
        except Exception:
            _clear_auth()
            try:
                return _save_via_pyzotero(papers, collection_name)
            except Exception:
                pass

    try:
        return _save_via_connector(papers, collection_name)
    except Exception:
        return 0, ""
