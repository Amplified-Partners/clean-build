# Purpose: Token-proxy connector — forces all LLM calls through cost-tools/token_proxy.py; bans direct Anthropic/OpenAI imports.
# Owner: U-07

async def call_llm(prompt: str, model: str = "haiku") -> dict:
    raise NotImplementedError("U-07")

# Signed-by: DeepSeek-Researcher | 2026-05-09 | session dsr-20260509-hermes-scaffold-v1