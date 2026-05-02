// OpenClaw Sovereign Fleet — Development Cedar Policies
// =====================================================
// Relaxed variant for local development and testing.
// Authored by Devon | 2026-05-02 | devin-701075c43e444229aa32f993bf60b36a
// All agents get broader permissions; approval gates still exist
// but are auto-satisfied in dev mode.

// ── Tier 1: Read-Only Recon (Auto-Allow — same as prod) ───────────
permit (
    principal in Role::"Agent",
    action in [
        Action::"read_file",
        Action::"git_log",
        Action::"grep_search",
        Action::"view_metrics"
    ],
    resource
);

// ── Tier 2: Write Operations (Dev — all agents, no approval gate) ─
permit (
    principal in Role::"Agent",
    action == Action::"write_file",
    resource in Directory::"/workspace/worktrees"
);

// ── Tier 3: Destructive Ops (Dev — Kimmy/Alpha, auto-approved) ────
permit (
    principal in [Agent::"Kimmy", Agent::"Alpha"],
    action in [Action::"merge_pr", Action::"deploy_production", Action::"execute_shell"],
    resource
);

// ── Absolute Deny (still enforced in dev) ─────────────────────────
forbid (
    principal,
    action,
    resource in [
        File::"/etc/openclaw/policies/prod.cedar",
        File::"/workspace/.env"
    ]
);
