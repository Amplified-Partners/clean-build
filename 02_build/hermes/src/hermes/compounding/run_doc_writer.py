# Purpose: Run-doc writer — append-only markdown run log with YAML frontmatter, fsync, crash-safe.
# Owner: U-24

class RunDocWriter:
    def start_run(self, run_id: str) -> None:
        raise NotImplementedError("U-24")

# Signed-by: DeepSeek-Researcher | 2026-05-09 | session dsr-20260509-hermes-scaffold-v1