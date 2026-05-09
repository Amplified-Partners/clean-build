---
title: Hermes Integration Spec — for Antigravity
date: 2026-05-09
version: 1
status: live
audience: Antigravity (COO / Arbiter) — hook these into the Command Interface
---

# Hermes Integration Spec

Three Hermes agents running on the M4 agent hub. Each is a FastAPI process
with the same API shape, different port and personality.

## Endpoints

All three serve the same contract:

| Method | Path | Auth | Returns | Purpose |
|--------|------|------|---------|---------|
| GET | `/health` | none | `{"status":"ok","name":"...","whatsapp":true}` | Is it alive? |
| GET | `/state` | none | `{"name","mode","port","spine","run_id","events"}` | Current session state |
| POST | `/task` | none | `{"status":"ok","reply":"..."}` | Send a task/message, get a response |
| POST | `/webhook/linear` | none | `{"status":"ok"}` | Linear webhook receiver |
| POST | `/webhook/github` | none | `{"status":"ok"}` | GitHub webhook receiver |

## Instances

| Agent | Port | URL | Model |
|-------|------|-----|-------|
| Hermes-PM | 9100 | `http://localhost:9100` | deepseek-chat |
| Hermes-Team | 9101 | `http://localhost:9101` | kimi-k2.6 |
| Hermes-Radar | 9102 | `http://localhost:9102` | grok-3 |

## How to talk to them

Send a POST to `/task` with JSON:
```json
{
  "from": "ewan",
  "body": "What's the status of the Cove build?"
}
```

Response:
```json
{
  "status": "ok",
  "reply": "The Cove build has 32 U-IDs pending..."
}
```

Each Hermes prefixes his reply with `[Hermes-PM]` so you know who's talking.

## WhatsApp routing

If WhatsApp is the channel, the Evolution API dispatcher handles routing:
- `@hermes` → Hermes-PM (9100)
- `@team` → Hermes-Team (9101)
- `@radar` → Hermes-Radar (9102)

The dispatcher strips the @keyword before forwarding. Hermes responds via
the Evolution API send-message endpoint.

## Auth (current state)

No auth on localhost. For the Command Interface dashboard, add a shared
header key. U-31 will implement proper mTLS for Beast deployment later.
For now: these are local-only, trusted network.

## What Antigravity needs to build

1. A dashboard widget per Hermes showing: name, status, run_id, event count
2. A chat input that POSTs to `/task` and displays the reply
3. Poll `/health` every 30s to show green/red status
4. Optional: aggregate all three `/state` responses into a single "Agent Hub" view

## Startup

Each Hermes is started from its repo:
```bash
cd ~/amplified-hermes       && uv run python src/hermes/main.py &
cd ~/amplified-hermes-team  && uv run python src/hermes/main.py &
cd ~/amplified-hermes-radar && uv run python src/hermes/main.py &
```

Or wrap in a single `start-all.sh`.

---
Signed-by: DeepSeek-Researcher | 2026-05-09 | session dsr-20260509-hermes-scaffold-v1