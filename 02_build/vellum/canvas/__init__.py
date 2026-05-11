"""Canvas engine — shared primitives for all Vellum modes.

Yjs bridge, hash chain, additive-only enforcement, tenant isolation.
"""

from vellum.canvas.yjs_bridge import YjsBridge
from vellum.canvas.hash_chain import HashChain
from vellum.canvas.additive import AdditiveGuard
from vellum.canvas.tenant import TenantStore

__all__ = [
    "YjsBridge",
    "HashChain",
    "AdditiveGuard",
    "TenantStore",
]
