"""
Research Pipe Stage 3: Curator 1 — Search Design
Design multi-pass search strategy using Claude (or Qwen if available).
"""

import uuid
import json
import re
from config_research_pipe import get_config

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


def stage_curator1(interpreter: dict) -> dict:
    """
    Stage 3: Design multi-pass search strategy.
    Returns three queries (broad, foundational, recent) with engine allocation.
    
    Args:
        interpreter: Output from stage_interpreter
    
    Returns:
        curator1_output: dict with search_strategy (3 queries)
    """
    curator1_id = str(uuid.uuid4())
    
    prompt = f"""You are Curator 1. Design a search strategy with three passes.

Neutralised question: "{interpreter['neutralised_question']}"
Researcher guidance: {interpreter['researcher_guidance']}

Return JSON only (no markdown):
{{
  "search_strategy": {{
    "round": 1,
    "queries": [
      {{"query": "BOOLEAN QUERY", "engines": ["exa", "arxiv"], "pass": "broad_landscape", "expected_results": 40, "confidence": "high"}},
      {{"query": "BOOLEAN QUERY", "engines": ["arxiv"], "pass": "foundational", "expected_results": 20, "confidence": "high"}},
      {{"query": "BOOLEAN QUERY", "engines": ["exa"], "pass": "recent_applications", "expected_results": 25, "confidence": "high"}}
    ],
    "sufficiency_criteria": {{
      "minimum_representations": 3,
      "ideal_representations": 5,
      "depth_required": "background logic + implementation",
      "diversity_check": "at least 2 schools of thought",
      "source_dominance": "no single source >40%"
    }}
  }}
}}"""
    
    search_strategy = None
    
    # Try Qwen if available
    if OLLAMA_AVAILABLE:
        try:
            config = get_config()
            print(f"[CURATOR1] Attempting Qwen with model: {config.QWEN_MODEL}")
            response = ollama.generate(
                model=config.QWEN_MODEL,
                prompt=prompt,
                stream=False
            )
            strategy_text = response['response']
            try:
                search_strategy = json.loads(strategy_text)
            except:
                json_match = re.search(r'\{.*\}', strategy_text, re.DOTALL)
                if json_match:
                    search_strategy = json.loads(json_match.group())
        except Exception as e:
            print(f"Ollama error: {e}")
    
    # Fallback to Claude
    if not search_strategy:
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic library required. Run: pip install anthropic")
        print("[CURATOR1] Using Claude (Ollama unavailable)")
        try:
            client = anthropic.Anthropic()
            response = client.messages.create(
                model="claude-opus-4-1",
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}]
            )
            response_text = response.content[0].text
            try:
                search_strategy = json.loads(response_text)
            except:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    search_strategy = json.loads(json_match.group())
        except Exception as e:
            print(f"Claude error: {e}")
    
    # Last resort
    if not search_strategy:
        search_strategy = {
            "search_strategy": {
                "round": 1,
                "queries": [
                    {"query": interpreter['neutralised_question'], "engines": ["exa", "arxiv"], "pass": "broad_landscape", "expected_results": 40, "confidence": "medium"},
                    {"query": "foundational research", "engines": ["arxiv"], "pass": "foundational", "expected_results": 20, "confidence": "medium"},
                    {"query": "recent applications", "engines": ["exa"], "pass": "recent_applications", "expected_results": 25, "confidence": "medium"}
                ],
                "sufficiency_criteria": {
                    "minimum_representations": 3,
                    "ideal_representations": 5,
                    "depth_required": "background logic",
                    "diversity_check": "at least 2 schools",
                    "source_dominance": "no >40%"
                }
            }
        }
    
    curator1_output = {
        "curator1_id": curator1_id,
        "interpreter_ref": interpreter["interpreter_id"],
        **search_strategy
    }
    
    return curator1_output
