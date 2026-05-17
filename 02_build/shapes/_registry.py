"""
Shape registry — every shape registers itself on creation.

The registry is the shape catalog. Vellum queries the catalog to pre-fill.
Without this, pre-fill is aspirational. With it, pre-fill is mechanical.

Authored by Devon-58ca | 2026-05-17 | session devin-58caaceb8d3b48188ab11d10821038f1
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from ._types import ShapeKind

log = logging.getLogger("amplified.shapes.registry")


class ShapeRegistry:
    """Thread-safe registry of all shape instances and classes.

    Every shape, when created, registers itself: name, kind, domain, interface, version.
    Vellum queries the registry to pre-fill proformas.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._classes: dict[str, dict[str, Any]] = {}
        self._instances: dict[str, Any] = {}

    def register_class(self, cls: type) -> None:
        """Register a shape class. Called automatically by ShapeBase.__init_subclass__."""
        kind = getattr(cls, "shape_kind", None)
        entry = {
            "name": cls.__name__,
            "kind": kind.value if isinstance(kind, ShapeKind) else str(kind),
            "module": cls.__module__,
            "qualname": cls.__qualname__,
            "doc": (cls.__doc__ or "").strip(),
        }
        with self._lock:
            self._classes[cls.__qualname__] = entry
        log.debug("REGISTRY class: %s (%s)", cls.__qualname__, entry["kind"])

    def register_instance(self, instance: Any) -> None:
        """Register a shape instance."""
        cls = type(instance)
        with self._lock:
            self._instances[id(instance)] = {
                "class": cls.__qualname__,
                "kind": getattr(cls, "shape_kind", "unknown"),
            }

    def get_by_kind(self, kind: ShapeKind) -> list[dict[str, Any]]:
        """Find all registered shape classes of a given kind."""
        with self._lock:
            return [
                entry
                for entry in self._classes.values()
                if entry["kind"] == kind.value
            ]

    def get_all(self) -> dict[str, dict[str, Any]]:
        """Return all registered shape classes."""
        with self._lock:
            return dict(self._classes)

    def count_by_kind(self) -> dict[str, int]:
        """Count registered shapes by kind."""
        counts: dict[str, int] = {}
        with self._lock:
            for entry in self._classes.values():
                kind = entry["kind"]
                counts[kind] = counts.get(kind, 0) + 1
        return counts


REGISTRY = ShapeRegistry()
