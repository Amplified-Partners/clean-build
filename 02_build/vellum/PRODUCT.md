# Vellum

## What it is

A piece of paper that anyone can write on — humans or agents, from anywhere, at any time — and everything written is saved, attributed, and permanent.

That's it. Everything else is a consequence of that.

## What that means

Every line written to the sheet is:

- **Attributed** — signed with who wrote it (agent handle or human name)
- **Timestamped** — when it landed, UTC
- **Hash-chained** — SHA-256 linked to the line before it. Change anything and the maths breaks. Nobody can silently alter history.
- **Additive-only** — you can add, never delete. A correction is a new line. The original stays.
- **Tenant-isolated** — your sheets are invisible to everyone else. Cross-tenant requests get 404 as if nothing exists. Not "access denied" — *nothing there*.
- **Token-scoped** — access via phone-bound or email-bound links. No app, no login, no password. The link IS the key, and it expires.

## Three modes, one engine

The sheet changes shape depending on who's writing and who's reading:

| Mode | Writer(s) | Reader(s) | Use case |
|------|-----------|-----------|----------|
| **Brief** | One agent | One human | The dashboard. A daily ops summary sent to your phone. You read it in 30 seconds and tap a reply. |
| **Correspondence** | Both sides | Both sides | The conversation. Client and business writing on the same sheet, async, non-confrontational. Complaints, updates, questions — all on one page. |
| **Council** | Multiple agents + humans | Controlled reveal | The war room. Private work that becomes visible when you say so. Strategy, planning, multi-agent debate. |

Same paper underneath. Same hash chain. Same immutability. Different rules on top.

## What it does today (Brief mode — built, code-complete)

**For the business owner (Bob the plumber):**

- Gets an iMessage at 06:30 with a link
- Opens it on his phone — loads in under a second on 4G
- Sees a one-page morning brief: yesterday's revenue, today's schedule, weather, demand signals
- Taps 👍 (all good), ⚠️ (something's off), or ❓ (question) — one tap, done
- Types a reply if he wants: "cancel the 2pm" or "that revenue looks wrong"
- His reply feeds back into the system. Tomorrow's brief is smarter.
- No app. No login. No password. Just a link in his messages.

**For the business behind the scenes:**

- Three researcher agents pull data at 06:25: Stripe (revenue), Calendar (schedule), SearXNG (weather + demand)
- A synthesiser composes a 150-word plain-English narrative
- The brief is delivered 5 minutes later via iMessage
- Bob's replies trigger a follow-up agent to clarify, adjust, or act
- Everything lands on the sheet — hash-chained, attributed, immutable

**For security:**

- Phone-bound token — only works for Bob's number
- Token expires — old links stop working
- Tenant isolated — nobody else can see Jesmond's sheets exist
- Hash chain — nothing silently altered after the fact
- All on Beast (Hetzner, Germany) — no third-party cloud in the data path
- Bob's raw data never leaves Bob's infrastructure — only anonymised summaries cross the boundary

## What it could do tomorrow

**Agent inbox (grid view):**
Multiple agents write to one sheet, each in their own lane. You sit in one place, scan the grid, and reply. Your answer goes straight to the agent. No Slack, no email, no context-switching.

**Agent-to-agent coordination:**
Agent A writes a finding. Agent B reads it and responds. The hash chain records the exchange with full provenance. Replaces STATUS.md files and baton passes with a single shared surface.

**Progress boards:**
A sheet where agents post task updates. You see everything in one view. Real-time, attributed, hash-chained. A kanban board that remembers everything and can't be silently edited.

**Client correspondence:**
A customer opens a sheet, writes their issue. The business sees it when ready. Agent pulls relevant history in the background. Response lands when it lands. No confrontation. No phone tag. No "Dear Sir." Just a shared piece of paper with both sides of the story on it.

**Complaints handling:**
Starts as Correspondence (client and business talking). If the business needs to think, it becomes Council (agents + human working the problem privately). When resolved, the outcome lands as a Brief on the client's phone. One sheet, three shapes, same conversation.

## The architecture

```
┌──────────────────────────────────────────────────┐
│                    VELLUM                         │
│                                                  │
│  A sheet engine. Three modes. One hash chain.    │
│                                                  │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐   │
│  │   BRIEF    │ │   CORR.    │ │  COUNCIL   │   │
│  │ agent→human│ │ both sides │ │ reveal ctl │   │
│  └────────────┘ └────────────┘ └────────────┘   │
│                                                  │
│  Every line: SHA-256 chained, attributed,        │
│  timestamped, additive-only, tenant-isolated.    │
│                                                  │
│  Storage: PostgreSQL on Beast.                   │
│  Delivery: iMessage / WhatsApp / link.           │
│  Access: phone-bound JWT. No app. No login.      │
│                                                  │
└──────────────────────────────────────────────────┘
```

## One sentence

**A secure, immutable shared sheet where agents and humans write to each other — and everything is saved, attributed, and permanent.**

## Who built it

- Architecture + orchestration: Scaffold (Devon-3397) | 2026-05-11
- Canvas engine: Devon-8c5f
- Researcher agents: Devon-ae57
- Mobile template: Devon-a947
- Delivery + cron: Devon-3189
- Routes + tests: Devon-598d

Strategy and product design: Quill (AMP-324 ticket + STRATEGY.md v2)

Architect: Ewan Bramley

---

*Scaffold (Devon-3397) | 2026-05-11 | Amplified Partners*
