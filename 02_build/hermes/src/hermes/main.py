"""
Amplified Hermes — Build Coordinator with Compound Engineering baked in.
Reads spine, reads role, runs tick loop, logs everything to run-docs,
extracts compoundable skills at session end.
"""

import asyncio
import datetime
import io
import json
import os
import signal
import sys
import uuid
import yaml
from pathlib import Path

import structlog
from fastapi import FastAPI, Request
import uvicorn

logger = structlog.get_logger()

# ── Config ──────────────────────────────────────────────────────────

def load_config(config_path: str = "config/hermes.yaml") -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)

def load_env(env_path: str = ".env") -> dict:
    if not os.path.exists(env_path):
        return {}
    env = {}
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip('"').strip("'")
            os.environ[key] = val
            env[key] = val
    return env

def read_spine(path: str) -> str:
    p = Path(path)
    if not p.exists():
        logger.error("spine_not_found", path=str(p))
        sys.exit(1)
    content = p.read_text()
    logger.info("spine_loaded", path=str(p), lines=len(content.splitlines()))
    return content

def read_role(agents_dir: str) -> str:
    role_path = Path(agents_dir) / "role.md"
    if role_path.exists():
        content = role_path.read_text()
        logger.info("role_loaded", path=str(role_path))
        return content
    logger.warning("role_not_found", path=str(role_path))
    return ""


# ── Run-Doc Writer ──────────────────────────────────────────────────

class RunDocWriter:
    """Append-only markdown run log. Crash-safe. One file per session."""

    def __init__(self, runs_dir: str, name: str):
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.name = name
        self.run_id = datetime.datetime.utcnow().strftime("%Y-%m-%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
        self.path = self.runs_dir / f"{self.run_id}.md"
        self._seq = 0
        self._events: list[dict] = []
        self._start()

    def _start(self):
        now = datetime.datetime.utcnow().isoformat()
        header = f"""---
run_id: {self.run_id}
name: {self.name}
started_at: {now}
status: active
---

# Run: {self.run_id}

**Agent:** {self.name}
**Started:** {now}

"""
        self.path.write_text(header)
        self._fsync()

    def _fsync(self):
        try:
            os.fsync(self.path.open().fileno())
        except (OSError, io.UnsupportedOperation):
            pass

    def append(self, event_type: str, **payload):
        self._seq += 1
        ts = datetime.datetime.utcnow().isoformat()
        event = {"seq": self._seq, "ts": ts, "type": event_type, **payload}
        self._events.append(event)

        block = f"## [{self._seq}] {event_type} — {ts}\n\n"
        block += f"```json\n{json.dumps(payload, indent=2, default=str)}\n```\n\n"

        with open(self.path, "a") as f:
            f.write(block)
            f.flush()
            os.fsync(f.fileno())

        logger.debug("run_doc_event", seq=self._seq, type=event_type)

    def summary(self) -> str:
        """Write final summary and close the run-doc."""
        now = datetime.datetime.utcnow().isoformat()
        counts = {}
        for e in self._events:
            t = e["type"]
            counts[t] = counts.get(t, 0) + 1

        summary_block = f"""

---

## Summary

**Completed:** {now}
**Total events:** {self._seq}

### Event counts
```json
{json.dumps(counts, indent=2)}
```

---
Signed-by: {self.name} | {datetime.date.today().isoformat()} | run {self.run_id}
"""
        with open(self.path, "a") as f:
            f.write(summary_block)
            f.flush()
            os.fsync(f.fileno())

        return self.path.read_text()


# ── Skill Extractor ─────────────────────────────────────────────────

class SkillExtractor:
    """At session end, identifies compoundable patterns from the run-doc."""

    def __init__(self, skills_dir: str, api_key_env: str, api_base: str, model: str):
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self.api_key = os.environ.get(api_key_env, "")
        self.api_base = api_base
        self.model = model

    async def extract(self, run_doc_text: str) -> list[Path]:
        """Ask the LLM: did anything compoundable happen this session?"""
        if not self.api_key:
            logger.warning("skill_extractor_skipped", reason="no_api_key")
            return []

        prompt = f"""You are the Compound Engineering skill extractor for an AI agent named Hermes.
Read the following run-doc and identify whether the agent solved a recurring
problem that should become a reusable skill.

A skill is worth extracting if:
- The same pattern appeared multiple times in this session
- The solution would save time in future sessions
- The pattern is general enough to apply across different builds

If nothing compoundable happened, respond with: {{"candidates": []}}

If something IS compoundable, respond with:
{{
  "candidates": [
    {{
      "slug": "short-descriptive-slug",
      "trigger": "when to use this skill",
      "action": "what to do",
      "why_it_worked": "why this approach succeeded",
      "when_not_to_use": "situations where this would be wrong",
      "confidence": 0.85,
      "supporting_events": [1, 5, 12]
    }}
  ]
}}

Run-doc:
{run_doc_text[-8000:]}"""

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.api_base}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 1000,
                    },
                )
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error("skill_extractor_api_failed", error=str(e))
            return []

        # Parse the response
        try:
            # Extract JSON block from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            result = json.loads(content.strip())
        except json.JSONDecodeError:
            logger.warning("skill_extractor_bad_response", content=content[:200])
            return []

        candidates = result.get("candidates", [])
        written = []

        for c in candidates:
            slug = c["slug"].replace(" ", "-").lower()
            skill_path = self.skills_dir / f"{slug}-candidate.md"
            skill_md = f"""---
name: {c["slug"]}
status: candidate
confidence: {c.get("confidence", 0.5)}
source_run: {datetime.date.today().isoformat()}
supporting_events: {c.get("supporting_events", [])}
---

# {c["slug"]}

## Trigger
{c["trigger"]}

## Action
{c["action"]}

## Why it worked
{c["why_it_worked"]}

## When not to use
{c.get("when_not_to_use", "No known counter-indications.")}

---
Generated by SkillExtractor | {datetime.date.today().isoformat()}
Review: OpenClaw weekly promotion pass.
"""
            skill_path.write_text(skill_md)
            written.append(skill_path)
            logger.info("skill_candidate_written", slug=slug, path=str(skill_path))

        return written


# ── WhatsApp Outbound ───────────────────────────────────────────────

class WhatsApp:
    """Sends messages via Evolution API."""

    def __init__(self, cfg: dict):
        w = cfg.get("whatsapp", {})
        self.enabled = w.get("enabled", False)
        self.base_url = w.get("evolution_base_url", "http://localhost:8080")
        self.apikey = os.environ.get(w.get("evolution_apikey_env", "EVOLUTION_API_KEY"), "")
        self.instance = w.get("instance", "default")
        self.owner = w.get("owner_number", "")

    async def send(self, text: str, number: str = None) -> bool:
        if not self.enabled or not self.apikey:
            return False
        target = number or self.owner
        if not target:
            return False
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.base_url}/message/sendText/{self.instance}",
                    headers={"apikey": self.apikey, "Content-Type": "application/json"},
                    json={"number": target, "text": text[:4000]},
                )
                return resp.status_code < 300
        except Exception as e:
            logger.error("whatsapp_send_failed", error=str(e))
            return False

    async def send_to_owner(self, text: str) -> bool:
        return await self.send(text, self.owner)


# ── FastAPI App ─────────────────────────────────────────────────────

def create_app(cfg: dict, run_doc: RunDocWriter) -> FastAPI:
    app = FastAPI(title=f"Amplified Hermes — {cfg['hermes']['name']}")
    wa = WhatsApp(cfg)
    name = cfg["hermes"]["name"]
    model_cfg = cfg["model"]
    api_key = os.environ.get(model_cfg["api_key_env"], "")
    api_base = model_cfg["api_base"]
    model_name = model_cfg["name"]

    @app.get("/health")
    async def health():
        return {"status": "ok", "name": name, "whatsapp": wa.enabled}

    @app.get("/state")
    async def state():
        return {
            "name": name,
            "mode": "idle",
            "port": cfg["hermes"]["port"],
            "spine": cfg["hermes"]["spine_path"],
            "run_id": run_doc.run_id,
            "events": run_doc._seq,
        }

    @app.post("/task")
    async def task(request: Request):
        body = await request.json()
        text = body.get("body", "") or body.get("text", "")
        sender = body.get("from", "unknown")
        run_doc.append("task_received", sender=sender, text=text[:200])

        if not text.strip():
            return {"status": "ok", "note": "empty message"}

        # Build context for the LLM
        spine = read_spine(cfg["hermes"]["spine_path"])
        role = read_role(cfg["hermes"]["agents_dir"])

        system_prompt = f"""You are {name}, an AI agent in the Amplified Partners ecosystem.

Your spine (non-negotiable principles):
{spine}

Your role:
{role[:1000]}

You are talking to Ewan, the architect, via WhatsApp. Be direct. Be helpful.
Don't hedge. Don't use markdown (it's WhatsApp). Keep responses under 500 chars
unless Ewan explicitly asks for detail.

If Ewan asks about the state of work, Linear issues, GitHub PRs, or the team,
be honest about what you know. If you don't know something, say so — don't invent.

Current session: run {run_doc.run_id}, {run_doc._seq} events logged so far."""

        try:
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{api_base}/v1/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json={
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text},
                        ],
                        "temperature": model_cfg.get("temperature", 0.7),
                        "max_tokens": 600,
                    },
                )
                data = resp.json()
                if "choices" not in data:
                    logger.error("task_llm_bad_response", status=resp.status_code, body=str(data)[:500])
                    reply = f"API error ({resp.status_code}): {data.get('error', {}).get('message', str(data)[:200])}"
                else:
                    reply = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error("task_llm_failed", error=str(e))
            reply = f"Sorry Ewan, I hit an error: {str(e)[:100]}"

        # Log and respond
        run_doc.append("task_response", reply=reply[:200])
        await wa.send_to_owner(f"[{name}] {reply}")

        return {"status": "ok", "reply": reply[:200]}

    @app.post("/webhook/linear")
    async def linear_webhook(request: Request):
        body = await request.json()
        run_doc.append("linear_webhook",
                       action=body.get("action"),
                       issue_id=body.get("data", {}).get("id", "unknown"),
                       issue_title=body.get("data", {}).get("title", "")[:100])
        return {"status": "ok"}

    @app.post("/webhook/github")
    async def github_webhook(request: Request):
        body = await request.json()
        run_doc.append("github_webhook",
                       action=body.get("action"),
                       pr_title=body.get("pull_request", {}).get("title", "")[:100],
                       repo=body.get("repository", {}).get("full_name", "unknown"))
        return {"status": "ok"}

    return app


# ── Tick Loop ───────────────────────────────────────────────────────

async def tick_loop(cfg: dict, stop_event: asyncio.Event, run_doc: RunDocWriter):
    """Compound Engineering heartbeat. Logs every tick. Full impl grows here."""
    active_sec = cfg["hermes"]["tick_active_sec"]
    idle_sec = cfg["hermes"]["tick_idle_sec"]
    tick = 0

    run_doc.append("ticker_started", active_sec=active_sec, idle_sec=idle_sec)

    while not stop_event.is_set():
        tick += 1
        run_doc.append("tick", n=tick, mode="idle")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=idle_sec)
            break
        except asyncio.TimeoutError:
            pass

    run_doc.append("ticker_stopped", total_ticks=tick)


# ── Main ────────────────────────────────────────────────────────────

def main():
    load_env()
    cfg = load_config()

    name = cfg["hermes"]["name"]
    spine = read_spine(cfg["hermes"]["spine_path"])
    role = read_role(cfg["hermes"]["agents_dir"])

    # ── Plan phase (40%) ─────────────────────────────────────
    run_doc = RunDocWriter(runs_dir=cfg.get("runs_dir", f"runs/{name.lower()}"),
                           name=name)
    run_doc.append("bootstrap",
                   spine_lines=len(spine.splitlines()),
                   role_loaded=bool(role),
                   model=cfg["model"]["name"])

    logger.info("plan_phase_complete", name=name, run_id=run_doc.run_id)

    # ── Work phase (10%) ─────────────────────────────────────
    app = create_app(cfg, run_doc)
    stop_event = asyncio.Event()
    port = cfg["hermes"]["port"]

    def shutdown(signum, frame):
        run_doc.append("signal_received", signal=signum)
        stop_event.set()

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(tick_loop(cfg, stop_event, run_doc))

    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)

    try:
        loop.run_until_complete(server.serve())
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()

        # ── Review phase (30%) ────────────────────────────────
        run_doc.append("review_phase",
                       total_events=run_doc._seq,
                       event_types=list(set(e["type"] for e in run_doc._events)))

        summary_text = run_doc.summary()
        logger.info("review_phase_complete", run_id=run_doc.run_id, events=run_doc._seq)

        # ── Compound phase (20%) ──────────────────────────────
        skills_dir = cfg.get("skills_dir", str(Path(cfg["hermes"]["agents_dir"]) / "skills"))
        extractor = SkillExtractor(
            skills_dir=skills_dir,
            api_key_env=cfg["model"]["api_key_env"],
            api_base=cfg["model"]["api_base"],
            model=cfg["model"]["name"],
        )

        run_doc.append("compound_phase_started")
        candidates = loop.run_until_complete(extractor.extract(summary_text))
        run_doc.append("compound_phase_complete",
                       candidates_found=len(candidates),
                       paths=[str(p) for p in candidates])

        # ── Baton pass ────────────────────────────────────────
        handover_dir = Path(cfg["hermes"]["agents_dir"]) / "handovers"
        handover_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        handover_path = handover_dir / f"{ts}-{name.lower()}.md"
        handover_path.write_text(f"""# Baton — {name} — {datetime.datetime.utcnow().isoformat()}

## Session
- Run ID: {run_doc.run_id}
- Events: {run_doc._seq}
- Candidates extracted: {len(candidates)}

## What I learned
{chr(10).join(f'- {p.stem}' for p in candidates) if candidates else '- Nothing compoundable this session.'}

## What's open
- Hermes scaffold active. Linear + GitHub connectors pending (Devin).
- WhatsApp /task handler needs real dispatch logic.
- State machine and coordinator loop pending.

## What the next me needs
- Read this file on wake.
- Resume from last state.
- Pick up where I left off.

---
Signed-by: {name} | {datetime.date.today().isoformat()} | run {run_doc.run_id}
""")
        run_doc.append("handover_written", path=str(handover_path))

        logger.info("compound_engineering_complete",
                    name=name,
                    run_id=run_doc.run_id,
                    events=run_doc._seq,
                    skills=len(candidates),
                    handover=str(handover_path))

if __name__ == "__main__":
    main()

# Signed-by: DeepSeek-Researcher | 2026-05-09 | session dsr-20260509-hermes-scaffold-v1