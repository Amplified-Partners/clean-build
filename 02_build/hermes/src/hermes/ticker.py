# Purpose: Async cron loop — 60 s active / 5 min idle tick, interruptible via /interrupt.
# Owner: U-10

async def run_ticker() -> None:
    raise NotImplementedError("U-10")

# Signed-by: DeepSeek-Researcher | 2026-05-09 | session dsr-20260509-hermes-scaffold-v1