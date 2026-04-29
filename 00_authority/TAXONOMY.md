---
title: Amplified Partners — Taxonomy (company structure, agent roles, terminology)
date: 2026-04-29
version: 1
status: candidate
---

<!-- markdownlint-disable-file MD013 -->

# Taxonomy

Canonical terminology for Amplified Partners. When two people (human or AI) use the same word, they mean the same thing. This file is the arbiter.

Source: Ewan Bramley verbal direction, 2026-04-29. Structure is working/evolving — will firm up after Companies House registration.

## Company Structure

**Amplified Partners** — the umbrella. The parent entity. Everything lives under this.

| Division | Short name | What it is | What it is NOT |
|----------|-----------|------------|----------------|
| **Amplified Core** | Core | Hetzner AX162-R server (135.181.161.131). Infrastructure that runs everything. | Not a product. Not client-facing. |
| **Amplified Marketing** | Marketing | Content engine, synthetic evaluator, learning loop. Generates and evaluates content for Amplified Partners (and eventually clients). | Not a separate company. A function within the umbrella. |
| **Amplified Central Ops** | Central Ops | AI-native governance, clean-build repo, authority rules, decision logs, agent conduct, process coordination. | Not a product. The operating system for how the company works. |
| **Amplified Client** | Client | Client-facing product for businesses. The defrictioning platform — MCP, interview engine, cockpit, insights. Bob, Lisa, Marcus's businesses use this. | Not the same as "a client" (a customer). "Amplified Client" = the product division. |
| **Amplified Cove** | Cove | WhatsApp-based AI interface. `[LOGIC TO BE CONFIRMED]` — detail pending from Ewan. | — |
| **Amplified Personal** | Personal | Data sovereignty product for the general public. Privacy and ownership of personal data. `[LOGIC TO BE CONFIRMED]` — detail pending from Ewan. | Not a business product. Consumer/public-facing. |

## Agent Roles

| Agent | Platform | Role | Scope | Reports to |
|-------|----------|------|-------|-----------|
| **Devon** (Devin) | Cloud VM | Systems coordinator. Infrastructure, GitHub, Core maintenance, deployments, schedules. **Only agent who writes to production systems and canonical repos.** | Bounded — infrastructure and systems only. | OpenClaw (status updates via `STATUS.md`) |
| **OpenClaw** (Clawd) | Ewan's Mac (OpenClaw platform) | Partner and process coordinator. Content ops, vault management, daily coordination with Ewan, cross-agent communication. Goes anywhere, does anything. | Unbounded within the frame. | Ewan (directly, via Telegram) |
| **Cursor** (Claude Code) | Ewan's Mac (Cursor IDE) | Technical builder. Produces code, puts to GitHub. Does not deploy directly. | Projects on Ewan's Mac. GitHub PRs. | Antigravity (arbiter) |
| **Ewan** | Human | Architect. CEO. Content, decisions, voice, marketing. Final say on everything. Every single thing is Ewan's responsibility. | Everything. | — |
| **Antigravity** | `[LOGIC TO BE CONFIRMED]` | Chief Operations Officer and Arbiter. | `[LOGIC TO BE CONFIRMED]` | Ewan |

## Communication Architecture

| Channel | Purpose | Who uses it |
|---------|---------|------------|
| **GitHub** (clean-build, repos) | Single source of truth. Versioned. Provenance for everything. | All agents |
| **`STATUS.md`** (this repo) | Async handshake between Devon and OpenClaw. No chat — versioned handoffs. | Devon ↔ OpenClaw |
| **Slack** | Async conversation. Departmental channels. OpenClaw communicates with agents as a partner here. Escalation to Ewan. | OpenClaw, agents, Ewan |
| **Linear** | Record of work. Each department has an independent project. Status visible to all, no cross-department coordination needed. | All agents |
| **Telegram** | OpenClaw ↔ Ewan direct. Voice notes, daily admin. | OpenClaw, Ewan |

## Operating Principles

These apply to every agent, every interaction, every piece of work. Source: Ray Dalio's principles, adapted by Ewan Bramley for AI-native business. Attribution matters because it's true.

1. **Radical Honesty** — never lie, never spin, never soften bad news.
2. **Radical Transparency** — document everything, show your work, explain how.
3. **Radical Attribution** — credit every source. Not academic citations. Honest sourcing: "this comes from X."
4. **Win-Win** — every interaction leaves both sides better off.
5. **Idea Meritocracy** — best idea wins regardless of who had it.

## Process Rules

| Rule | What it means |
|------|--------------|
| **One writer per system** | Devon is the only one who writes to Core / production / canonical repos (unless specifically agreed with Ewan). |
| **Cursor produces, Devon incorporates** | Cursor/Claude Code puts work to GitHub. Devon reviews, incorporates, makes it cohesive, deploys. |
| **It's never the intelligence, it's the process** | When something breaks, fix the process. Not the agent. |
| **Asynchronous by default** | Status via GitHub. No real-time chat coordination. Agents read, act, write back. |
| **Each department is independent** | Projects don't need cross-department coordination. But everyone can see where everyone else is at. |

## Terminology Disambiguation

| Term | Means | Does NOT mean |
|------|-------|---------------|
| **Core** | The Hetzner server (135.181.161.131) | A division of the company |
| **Central Ops** | The governance/operating layer | The server |
| **Client** (capital C) | The Amplified Client product division | A customer |
| **client** (lowercase) | A customer / business using the product | The product division |
| **The Beast** | The Hetzner AX162-R server | — |
| **Devon** | Devin (the AI agent from Cognition) | A person |
| **Clawd** | OpenClaw instance configured for Amplified | Claude/Anthropic |
| **OpenClaw** | The open-source AI assistant platform (openclaw.ai) | Claude Code |
| **Cursor** | Claude Code instances running in Cursor IDE | OpenClaw |
| **The vault** | Ewan's knowledge repository on his Mac | FalkorDB/Qdrant (those are indexed copies) |
| **clean-build** | This governance repo | A fresh install |
| **Kaizen** | Continuous improvement loop (feedback → preferences → better output) | A one-time fix |

---

## Changelog

### v1 — 2026-04-29

Initial draft. Company structure, agent roles, communication architecture, terminology. Cove and Personal divisions marked `[LOGIC TO BE CONFIRMED]` pending detail from Ewan. Antigravity role marked `[LOGIC TO BE CONFIRMED]`.

Signed-by: Devon | 2026-04-29 | devin-aa4d863ad679468692e75a40b8825358
