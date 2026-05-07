"""
Research Pipe Stage 4: Search
Execute queries in parallel (Exa + arXiv), aggregate results.
"""

import uuid
import xml.etree.ElementTree as ET

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from config_research_pipe import get_config


def stage_search(curator1: dict) -> dict:
    """
    Stage 4: Execute search queries in parallel (Exa + arXiv).
    Aggregate and deduplicate results.
    
    Args:
        curator1: Output from stage_curator1
    
    Returns:
        search_output: dict with aggregated results
    """
    config = get_config()
    search_id = str(uuid.uuid4())
    
    if not REQUESTS_AVAILABLE:
        raise ImportError("requests library required. Run: pip install requests")
    results = []
    
    queries = curator1.get("search_strategy", {}).get("queries", [])
    
    for query_spec in queries:
        query = query_spec.get("query", "")
        engines = query_spec.get("engines", [])
        pass_type = query_spec.get("pass", "unknown")
        
        for engine in engines:
            try:
                if engine == "searxng":
                    hits = _search_searxng(query, config)
                    results.extend([{**h, "source": "searxng", "pass": pass_type} for h in hits])
                elif engine == "exa" and config.EXA_API_KEY:
                    hits = _search_exa(query, config)
                    results.extend([{**h, "source": "exa", "pass": pass_type} for h in hits])
                elif engine == "arxiv":
                    hits = _search_arxiv(query, config)
                    results.extend([{**h, "source": "arxiv", "pass": pass_type} for h in hits])
            except Exception as e:
                print(f"Search error ({engine}, {query}): {e}")
    
    # Deduplicate by URL
    seen = set()
    deduplicated = []
    for r in results:
        url = r.get("url", "")
        if url and url not in seen:
            seen.add(url)
            deduplicated.append(r)
        elif not url:
            deduplicated.append(r)
    
    search_output = {
        "search_id": search_id,
        "curator1_ref": curator1["curator1_id"],
        "total_results": len(deduplicated),
        "results": deduplicated[:config.MAX_RESULTS_PER_SEARCH]
    }
    
    return search_output


def _search_exa(query: str, config, limit: int = 10) -> list:
    """Search Exa."""
    try:
        headers = {"Authorization": f"Bearer {config.EXA_API_KEY}"}
        payload = {
            "query": query,
            "num_results": limit,
            "include_domains": None,
            "exclude_domains": None
        }
        resp = requests.post(config.EXA_ENDPOINT, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("text", ""),
                    "type": "research"
                }
                for r in data.get("results", [])
            ]
    except Exception as e:
        print(f"Exa error: {e}")
    return []


def _search_arxiv(query: str, config, limit: int = 10) -> list:
    """Search arXiv."""
    try:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending"
        }
        resp = requests.get(config.ARXIV_ENDPOINT, params=params, timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            results = []
            for entry in root.findall("{http://www.w3.org/2005/Atom}entry"):
                title = entry.find("{http://www.w3.org/2005/Atom}title")
                summary = entry.find("{http://www.w3.org/2005/Atom}summary")
                link = entry.find("{http://www.w3.org/2005/Atom}id")
                results.append({
                    "title": title.text if title is not None else "",
                    "url": link.text if link is not None else "",
                    "snippet": summary.text[:500] if summary is not None else "",
                    "type": "academic"
                })
            return results
    except Exception as e:
        print(f"arXiv error: {e}")
    return []


def _search_searxng(query: str, config, limit: int = 20) -> list:
    """Search local SearXNG meta-search engine."""
    try:
        params = {
            "q": query,
            "format": "json",
            "pageno": 1
        }
        resp = requests.get(f"{config.SEARXNG_ENDPOINT}/search", params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            results = []
            for r in data.get("results", [])[:limit]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", "")[:500],
                    "type": "general",
                    "engines": r.get("engines", [])
                })
            return results
    except Exception as e:
        print(f"SearXNG error: {e}")
    return []
