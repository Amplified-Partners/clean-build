#!/usr/bin/env python3
"""
APDS Harvester MVP — 2026-05-05
Queries 11 confirmed-working SearXNG engines, dumps raw results as JSON.
No LLM, no cost, deterministic.

Status: this is the script that actually ran on Beast on 2026-05-05 and
produced `harvest_20260505_033410.json` (88 query × engine blocks, 250 results),
which `apds_labeller.py` then labelled into 250 :Document nodes in FalkorDB.
Linear: AMP-104.

Originally hand-deployed to /opt/amplified/apds/harvest/harvester_mvp.py by Kimmy.
Promoted to version control unchanged (apart from this header).

Authored-by: Kimmy (hand-deployed to Beast 2026-05-05)
Promoted-by: Devon-9f21 | 2026-05-05 | devin-9f2104fb06624b009f2879c50957c647
"""
import os, json, sys, httpx
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = os.getenv('SEARXNG_URL', 'http://searxng:8080')
OUT_DIR = Path(os.getenv('HARVEST_DIR', '/opt/amplified/apds/harvest'))
LOG_FILE = Path(os.getenv('LOG_DIR', '/opt/amplified/apds/logs')) / 'harvester.jsonl'

# 11 engines confirmed working on 2026-05-05
ENGINES = ['google', 'bing', 'duckduckgo', 'arxiv', 'github', 'stackoverflow',
           'hacker_news', 'metager', 'mojeek', 'startpage', 'ecosia']

# T1/T2 queries for UK SMB context
QUERIES = [
    'UK small business AI automation 2026',
    'tradesperson plumber electrician CRM software',
    'UK hospitality restaurant tech stack',
    'retail shop POS system AI features',
    'small business cash flow prediction tools',
    'UK SME GDPR data protection compliance',
    'freelancer invoice automation UK',
    'trades business scheduling software UK',
]

def harvest():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    run_id = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    results = []
    
    for query in QUERIES:
        for engine in ENGINES:
            try:
                r = httpx.get(
                    f'{BASE_URL}/search',
                    params={'q': query, 'engines': engine, 'format': 'json'},
                    timeout=20
                )
                if r.status_code == 200:
                    data = r.json()
                    hits = data.get('results', [])
                    entry = {
                        'run_id': run_id,
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'query': query,
                        'engine': engine,
                        'results_count': len(hits),
                        'results': [
                            {'title': h.get('title',''), 'url': h.get('url',''), 'content': h.get('content','')[:500]}
                            for h in hits[:5]  # top 5 only for MVP
                        ]
                    }
                    results.append(entry)
                    with open(LOG_FILE, 'a') as f:
                        f.write(json.dumps({'event': 'harvest_ok', **entry}) + '\n')
                    print(f'OK  {engine:12s} | {query[:40]:40s} | {len(hits):3d} hits')
                else:
                    print(f'FAIL {engine:12s} | {query[:40]:40s} | HTTP {r.status_code}')
            except Exception as e:
                print(f'ERR  {engine:12s} | {query[:40]:40s} | {str(e)[:50]}')
    
    out_path = OUT_DIR / f'harvest_{run_id}.json'
    out_path.write_text(json.dumps(results, indent=2))
    print(f'\nWrote {len(results)} entries to {out_path}')
    return len(results)

if __name__ == '__main__':
    count = harvest()
    sys.exit(0 if count > 0 else 1)
