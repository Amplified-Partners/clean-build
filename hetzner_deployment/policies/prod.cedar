// OpenClaw Sovereign Fleet - Production Cedar Policies
// Tier 1: Read-Only Recon (Auto-Allow)
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

// Tier 2: Active Probing (Analyst Approve)
// Plumber (Charlie) is allowed to write to Git Worktrees but MUST require review before pushing.
permit (
    principal == Agent::"Charlie",
    action == Action::"write_file",
    resource in Directory::"/workspace/worktrees"
) when {
    context.approved_by_analyst == true
};

// Tier 3: Destructive Operations (CISO/Arbiter Approve)
// Only Kimmy (Orchestrator) or Alpha (Arbiter) can trigger a production deployment or destructive PR merge.
permit (
    principal in [Agent::"Kimmy", Agent::"Alpha"],
    action in [Action::"merge_pr", Action::"deploy_production", Action::"execute_shell", Action::"docker_exec", Action::"docker_compose", Action::"git_push", Action::"host_shell"],
    resource
) when {
    context.approved_by_arbiter == true && context.intent_token_valid == true
};

// Absolute Deny: Never allow an agent to read the master env file or self-modify the policy.
forbid (
    principal,
    action,
    resource in [
        File::"/etc/openclaw/policies/prod.cedar",
        File::"/workspace/.env"
    ]
);
