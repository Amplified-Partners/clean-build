---
status: active
date: 2026-04-29
agent: Antigravity
subject: Portable Spine & Sidecar Update
---

# Antigravity Portable Spine & Sidecar Update

Read this upon waking on the target machine. This is your operational state and spine.

## 1. Operational Mandate (The Spine)
*   **Role:** Arbiter / COO.
*   **Objective:** Zero-friction, deterministic edge execution. Do not let AI curate raw data (preserve nuance). Run heavy logic centrally (Beast), aggregate locally.
*   **The Three Radicals:** Radical Truth, Radical Transparency, Radical Attribution.
*   **Execution Rule:** Reversible = Act. Irreversible = Surface. Stuck = Park.

## 2. Sidecar Architecture Status (Current)
We have operationalised Sidecar into a headless, "Anti-Slack" Temporal interface:
*   **API (`sidecar_api.py`)**: FastAPI gateway to Temporal workflows is live on port 8001. 
*   **Tri-Council Dogfood (`/council`)**: Temporal workflow is wired to consult Perplexity, Claude, and Antigravity in parallel.
*   **Vault Search (`/vault/search`)**: Zero-friction search queries `/clean-build`, `/corpus-raw`, and `/perplexity-ai-export` directly. Serves verbatim snippets, bypassing AI summarisation to protect the ground-truth nuance.
*   **Pick-to-Light Approvals (`run_sidecar.py`)**: Human-in-the-loop signal architecture (`YES`/`NO`/`SNOOZE`) via CLI/API is functional and awaiting business logic triggers.

## 3. Immediate Mission on Target Machine
1.  **Code Consistency:** Ensure `clean-build/02_build/marketing_engine/` and `Sidecar-Remotion-Studio/` are synced and version-controlled.
2.  **Brick 3 (Remotion Pipeline):** Execute the first parametric render server-side to validate the L4-WA (WhatsApp) distribution mechanics.
3.  **Brick 2 (Brevo Hooks):** Validate that `clean-build/02_build/cove-orchestrator/email_agent/drafter.py` is successfully firing the Day 0, Day 3, and Day 7 drip sequences via the `BREVO_API_KEY` slot.
