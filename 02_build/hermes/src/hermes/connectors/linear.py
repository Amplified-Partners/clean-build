# Purpose: Linear connector — extends hetzner_deployment/linear_reporter.py with update_state, add_comment, webhook_handler, poll_reconcile.
# Owner: U-27

async def update_issue_state(issue_id: str, new_state: str) -> None:
    raise NotImplementedError("U-27")

# Signed-by: DeepSeek-Researcher | 2026-05-09 | session dsr-20260509-hermes-scaffold-v1