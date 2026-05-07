"""
Research Pipe Stage 5: Curator 2 — Synthesis & Sufficiency
Sufficiency check, synthesize methodologies, apply Pudding Technique.
"""

import uuid
import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def stage_curator2(search: dict, curator1: dict) -> dict:
    """
    Stage 5: Sufficiency check, synthesize methodologies, apply Pudding Technique.
    
    Args:
        search: Output from stage_search
        curator1: Output from stage_curator1 (for sufficiency criteria)
    
    Returns:
        curator2_output: dict with sufficiency verdict and synthesis
    """
    if not ANTHROPIC_AVAILABLE:
        raise ImportError("anthropic library not installed. Run: pip install anthropic")
    
    curator2_id = str(uuid.uuid4())
    client = anthropic.Anthropic()
    
    results_text = json.dumps(search.get("results", [])[:20], indent=2)  # Top 20
    sufficiency_criteria = curator1.get("search_strategy", {}).get("sufficiency_criteria", {})
    
    prompt = f"""You are Curator 2. Evaluate these search results for sufficiency, then synthesize.

Results ({search.get('total_results', 0)} total):
{results_text}

Sufficiency criteria:
{json.dumps(sufficiency_criteria, indent=2)}

Return JSON only:
{{
  "sufficiency_check": {{
    "verdict": "SUFFICIENT|ITERATE",
    "representations_found": NUMBER,
    "depth_assessment": "deep|shallow|mixed",
    "diversity_assessment": "high|moderate|low",
    "dominance_flag": true|false,
    "dominance_note": "STRING or null",
    "iteration_reason": "STRING or null"
  }},
  "synthesis": {{
    "methodologies": [
      {{
        "name": "NAME",
        "source": "AUTHOR, YEAR",
        "core_premise": "ONE_SENTENCE",
        "operationalization": ["step 1", "step 2"],
        "strengths": ["s1", "s2"],
        "limitations": ["l1", "l2"],
        "school": "ethics|behavioral|psychology|other"
      }}
    ],
    "pudding_technique": {{
      "symbiotic_pairs": [
        {{"method_a": "NAME", "method_b": "NAME", "why_they_complement": "STRING"}}
      ],
      "novel_taxonomy": {{
        "dimension_1": ["method_a", "method_b"]
      }}
    }}
  }}
}}"""
    
    try:
        response = client.messages.create(
            model="claude-opus-4-1",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text
        try:
            curator2_data = json.loads(response_text)
        except json.JSONDecodeError:
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                curator2_data = json.loads(json_match.group())
            else:
                raise ValueError(f"No JSON found in response: {response_text[:200]}")
    except Exception as e:
        print(f"Curator 2 error: {e}")
        curator2_data = {
            "sufficiency_check": {
                "verdict": "INSUFFICIENT",
                "representations_found": 0,
                "depth_assessment": "unknown",
                "diversity_assessment": "unknown",
                "dominance_flag": False,
                "dominance_note": None,
                "iteration_reason": "Could not parse results"
            },
            "synthesis": {"methodologies": [], "pudding_technique": {}}
        }
    
    curator2_output = {
        "curator2_id": curator2_id,
        "search_ref": search["search_id"],
        **curator2_data
    }
    
    return curator2_output
