# The Tripartite Data Architecture: Refining the Ledger
**Author:** Antigravity | **Status:** Architectural Thesis for Ewan's Review

Ewan has defined the core working architecture:
1. **Linear:** The Immediate (Task routing, state tracking).
2. **GitHub:** The Permanent-ish (Operational code, immutable principles, mutable implementations).
3. **The Vault (Postgres/Qdrant/Graph):** The Curated Truth. This is where agents actually go to get context, check facts, and pull client history. It is highly structured and token-efficient.

So, where does the raw thread storage (MinIO) fit into this design? If agents aren't querying it for context, why does it exist?

Here is the refined design. The MinIO storage is not a "Bloat Vault." It is the **Immutable Ledger**. Its value is structural, legal, and operational. 

---

### 1. The Liability Receipt (Audit & Provenance)
The Vault stores the *conclusion*. The Ledger stores the *proof*.
If a client questions a business decision ("Why did the Ghost Sidecar tell me to fire my accountant?"), the Vault holds the synthesized rule. But the Ledger holds the exact raw conversation, the chain of thought, and the hallucination-checks the agent performed. In a commercial holding company, you need an immutable receipt of work to prove the AI acted under the Duty of Care principle. The Ledger is your legal shield.

### 2. The Simulation Sandbox (Shadow Testing)
If you want to test a new agent persona or a massive upgrade to the Portable Spine, you cannot test it on live clients. 
Because the Ledger holds every raw interaction perfectly preserved, you can feed historical Ledger threads into a sandboxed `03_shadow/` agent. You can run perfect historical simulations to see if the new agent performs better than the old agent did on the exact same conversation. The Ledger is your simulation fuel.

### 3. The Nuance Retrieval (Emotion & Friction)
The Vault is designed to strip out noise to save tokens. It turns a 2-hour frustrated client rant into: `Client friction point: Invoicing speed`. 
When Kimmy hands a client profile to a copywriting agent, the copywriter reads the Vault. But if the copywriter needs to match the exact *tone* of the client's frustration to write an empathetic email, the Vault is too sterile. The copywriter can selectively pull the raw transcript from the Ledger to absorb the human nuance that curation destroyed.

### 4. Event Sourcing (The Ultimate Backup)
As discussed, GitHub is mutable. The Vault is mutable. If we structure the Vault wrong, or an agent curates bad data that poisons the Qdrant vectors, the Vault is compromised. 
Because the Ledger is append-only, you can delete the entire Vault, hit play on the Ledger, and perfectly rebuild the database from scratch with new curation rules.

---
### The Final Blueprint
* **Linear:** What are we doing right now?
* **GitHub:** How do we do it? (Code/Spine)
* **The Vault:** What do we know? (Curated Context)
* **The Ledger (MinIO):** What exactly happened? (Immutable Proof/Simulation/Rebuild)
