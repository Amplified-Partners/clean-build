"""
Research Pipe Stage 2: Interpreter
Neutralize language, detect assumptions, provide researcher guidance.
"""

import uuid
import json

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def stage_interpreter(intake: dict) -> dict:
    """
    Stage 2: Neutralise language, detect assumptions, provide guidance.
    Uses Claude to analyze the question.
    
    Args:
        intake: Output from stage_intake
    
    Returns:
        interpreter_output: dict with neutralised question and analysis
    """
    if not ANTHROPIC_AVAILABLE:
        raise ImportError("anthropic library not installed. Run: pip install anthropic")
    
    interpreter_id = str(uuid.uuid4())
    client = anthropic.Anthropic()
    
    prompt = f"""You are an expert research interpreter. Analyze this research question for:
1. Loaded language (emotionally weighted terms)
2. Hidden assumptions
3. Logical structure
4. Factual vs. judgment components

Input question: "{intake['question']}"
Domain: {intake['domain']}

Output JSON only:
{{
  "neutralised_question": "STRING (same meaning, neutral language)",
  "component_analysis": {{
    "factual": ["what is verifiable"],
    "judgment_calls": ["what is subjective"],
    "logical_structure": "STRING",
    "scientific": "STRING (what's testable)"
  }},
  "loaded_language_flags": [
    {{"phrase": "STRING", "neutralised": "STRING", "why": "STRING"}}
  ],
  "researcher_guidance": "STRING (hints on what to look for)"
}}"""
    
    try:
        response = client.messages.create(
            model="claude-opus-4-1",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = response.content[0].text
        try:
            analysis = json.loads(response_text)
        except json.JSONDecodeError:
            # Try extracting JSON from response
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
            else:
                raise ValueError(f"No JSON found in response: {response_text[:200]}")
    except Exception as e:
        # Fallback: use question as-is
        print(f"Interpreter error: {e}")
        analysis = {
            "neutralised_question": intake["question"],
            "component_analysis": {
                "factual": [],
                "judgment_calls": [],
                "logical_structure": "unknown",
                "scientific": "unknown"
            },
            "loaded_language_flags": [],
            "researcher_guidance": "Explore methodologies in the domain"
        }
    
    interpreter_output = {
        "interpreter_id": interpreter_id,
        "intake_ref": intake["intake_id"],
        **analysis
    }
    
    return interpreter_output
