"""
APDS Wiring Glue — routing adapters connecting the 5-stage pipeline.

    Harvest --> [harvest_to_label] --> Label
    Sidecar --> [sidecar_to_label] --> Label
    Score   --> [score_to_graph]   --> FalkorDB
    *       --> [path_abstraction] --> resolved paths

Signed-by: Devon (Devin session f32d587cc3e54f959c5309d93f72bc97) - 2026-05-01
"""
