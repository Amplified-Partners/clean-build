// OpenClaw Sovereign Fleet — Production Cedar Policies
// ====================================================
// IBAC (Intent-Based Access Control) for the three-entity fleet.
// Authored by Devon | 2026-05-02 | devin-701075c43e444229aa32f993bf60b36a
// Loaded at container startup; changes require restart + Arbiter approval.
//
// Entities:  Kimmy (Orchestrator), Alpha (Arbiter), Charlie (Plumber)
// Tiers:     1 = auto-allow, 2 = analyst-approve, 3 = arbiter-approve
// Absolute:  deny-list that overrides all permits.

// ── Tier 1: Read-Only Recon (Auto-Allow) ──────────────────────────
// Any agent may observe the workspace without approval.
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

// ── Tier 2: Active Probing (Analyst Approve) ──────────────────────
// Charlie (Plumber) may write to git worktrees — but only with analyst sign-off.
permit (
    principal == Agent::"Charlie",
    action == Action::"write_file",
    resource in Directory::"/workspace/worktrees"
) when {
    context.approved_by_analyst == true
};

// ── Tier 3: Destructive Operations (Arbiter Approve) ──────────────
// Only Kimmy (Orchestrator) or Alpha (Arbiter) may merge, deploy, or shell out.
// Requires both arbiter approval AND a valid intent token.
permit (
    principal in [Agent::"Kimmy", Agent::"Alpha"],
    action in [Action::"merge_pr", Action::"deploy_production", Action::"execute_shell"],
    resource
) when {
    context.approved_by_arbiter == true && context.intent_token_valid == true
};

// ── Absolute Deny ─────────────────────────────────────────────────
// No agent — regardless of role or approval chain — may read the
// master policy or the environment secrets file.  This is the
// circuit breaker that prevents self-modification and credential
// exfiltration.
forbid (
    principal,
    action,
    resource in [
        File::"/etc/openclaw/policies/prod.cedar",
        File::"/workspace/.env"
    ]
);
