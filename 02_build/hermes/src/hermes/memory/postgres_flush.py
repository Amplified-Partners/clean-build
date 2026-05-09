# Purpose: Postgres flush — idempotent push of episodic + decisions to Postgres at run end.
# Owner: U-23

async def flush_to_postgres(run_id: str) -> None:
    raise NotImplementedError("U-23")

# Signed-by: DeepSeek-Researcher | 2026-05-09 | session dsr-20260509-hermes-scaffold-v1