---
status: parked
date: 2026-04-28
from: Antigravity (Mac Air M5)
to: Antigravity (Mac Mini)
subject: Vault Architecture Sync & Dedupe Pipeline
---

# Baton Pass: Vault UI & Deduplication Sync

Agent (Mini), read this immediately upon waking. You have just completed the Beast code transfer. This is the delta of what we built on the Air M5 in the meantime.

## 1. The Vault UI is Live
- We built a deterministic "Vault Search" UI into `StaffUI.jsx` and `sidecar_api.py`.
- It dynamically searches the local `/clean-build/01_truth/` and the `/corpus-raw/` databases and serves exact snippets with a one-click copy button. 
- Ewan has zero-friction access to the full knowledge base without leaving the Sidecar.

## 2. Perplexity Architecture Alignment
- Ewan is using the native **Perplexity Computer** Mac App to read the uncurated, massive Google Drive backups and the `corpus-raw` folder.
- **Rule:** Do not let AI summarize or curate the raw Google Drive dumps. Perplexity must read the raw files to preserve the nuance. The Sidecar reads the curated Vault to execute deterministic marketing engines (Remotion/Brevo).

## 3. Brute Force Dedupe
- We built `Brute_Force_Dedupe.py` and `hound_dog.py` scripts to mathematically deduplicate (SHA-256) Ewan's massive Google Drive backups on the Mac Air M4. 

## Next Action for the Mini
Now that the Beast code (Marketing Engine) is pulled down, focus entirely on **Brick 2 and Brick 3**:
1. Prove the programmatic Remotion render pipeline (`ViralHook` with `--props`).
2. Finalize the Brevo API dispatch for the Day 0, Day 3, Day 7 email drips.

Do not rebuild the UI. Ewan hates friction. Focus on the raw python pipelines that execute the logic.
