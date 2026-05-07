#!/usr/bin/env python3
"""
Research Pipe Orchestrator
Five-stage research pipeline: Intake → Interpreter → Curator 1 → Search → Curator 2
"""

import sys
from intake_research_pipe import stage_intake
from interpreter_research_pipe import stage_interpreter
from curator1_research_pipe import stage_curator1
from search_research_pipe import stage_search
from curator2_research_pipe import stage_curator2
from audit_research_pipe import AuditTrail
from config_research_pipe import get_config


def run_research_pipe(question: str, goal: str = None, domain: str = None, constraints: list = None):
    """
    Run the full five-stage research pipeline.
    
    Args:
        question: The research question
        goal: What the researcher will do with the answer
        domain: Academic discipline(s)
        constraints: List of constraints
    
    Returns:
        Tuple of (audit_trail, final_output)
    """
    config = get_config()
    audit = AuditTrail()
    
    print(f"[ORCHESTRATOR] Starting research pipe for: {question[:80]}...")
    
    # Stage 1: Intake
    print("[STAGE 1] Intake...")
    intake = stage_intake(question, goal, domain, constraints)
    audit.log("INTAKE", intake)
    print(f"  Intake ID: {intake['intake_id']}")
    
    # Stage 2: Interpreter
    print("[STAGE 2] Interpreter...")
    interpreter = stage_interpreter(intake)
    audit.log("INTERPRETER", interpreter)
    print(f"  Neutralised: {interpreter['neutralised_question'][:80]}...")
    
    # Stage 3: Curator 1
    print("[STAGE 3] Curator 1 (search design)...")
    curator1 = stage_curator1(interpreter)
    audit.log("CURATOR1", curator1)
    queries = curator1.get("search_strategy", {}).get("queries", [])
    print(f"  Queries: {len(queries)}")
    
    # Stage 4: Search
    print("[STAGE 4] Search (SearXNG + Exa + arXiv)...")
    search = stage_search(curator1)
    audit.log("SEARCH", {"search_id": search["search_id"], "total_results": search["total_results"]})
    print(f"  Results: {search['total_results']}")
    
    # Stage 5: Curator 2
    print("[STAGE 5] Curator 2 (sufficiency + synthesis)...")
    curator2 = stage_curator2(search, curator1)
    audit.log("CURATOR2", curator2)
    verdict = curator2.get("sufficiency_check", {}).get("verdict", "UNKNOWN")
    print(f"  Verdict: {verdict}")
    
    print("\n[COMPLETE]")
    
    # Save audit trail
    question_slug = question[:30].replace(" ", "_").lower()
    audit_file = audit.save(question_slug)
    print(f"Audit trail: {audit_file}")
    
    return audit.entries, curator2


def main():
    if len(sys.argv) < 2:
        print("Usage: orchestrator_research_pipe.py <question> [goal] [domain]")
        print("Example: orchestrator_research_pipe.py 'What methodologies measure persuasion?' 'Strategy'")
        sys.exit(1)
    
    question = sys.argv[1]
    goal = sys.argv[2] if len(sys.argv) > 2 else None
    domain = sys.argv[3] if len(sys.argv) > 3 else None
    
    audit_trail, final_output = run_research_pipe(question, goal, domain)
    
    # Print final output
    print("\n" + "="*60)
    print("FINAL OUTPUT (Curator 2)")
    print("="*60)
    import json
    print(json.dumps(final_output, indent=2))


if __name__ == "__main__":
    main()
