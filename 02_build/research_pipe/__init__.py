"""research_pipe — prevents 'research done' from masquerading as completion.

Every research job has a state machine that enforces: no closure without
evidence. The pipe routes and tags; it does not promote.

Signed-by: Devon-d493 | 2026-05-19 | devin-d49302e4179d43d0892997a7f3a9f57f
"""
