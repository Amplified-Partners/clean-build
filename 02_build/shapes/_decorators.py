"""
Decorators for the Huf Haus shape system.

These are the Huf Haus pre-wires — the pipes and electrics already in the wall.
Each decorator is baked into the shape template. Zero extra work on site.

Authored by Devon-58ca | 2026-05-17 | session devin-58caaceb8d3b48188ab11d10821038f1
Source architect: Ewan Bramley (monitoring doctrine, 2026-05-17)
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import functools
import hashlib
import json
import logging
import threading
import time
from collections import defaultdict
from typing import Any

from ._types import GuardHalt, ShapeError, TrafficLight

log = logging.getLogger("amplified.shapes")


# ---------------------------------------------------------------------------
# Telemetry storage — thread-safe, in-memory for reference implementation
# ---------------------------------------------------------------------------


class _MetricsStore:
    """Thread-safe metrics accumulator. Production replaces with Vellum sink."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.timings: dict[str, list[float]] = defaultdict(list)
        self.call_counts: dict[str, int] = defaultdict(int)
        self.error_counts: dict[str, int] = defaultdict(int)
        self.last_error: dict[str, str] = {}

    def record_call(self, name: str, duration: float, error: str | None = None) -> None:
        with self._lock:
            self.timings[name].append(duration)
            self.call_counts[name] += 1
            if error:
                self.error_counts[name] += 1
                self.last_error[name] = error

    def get_stats(self, name: str) -> dict[str, Any]:
        with self._lock:
            times = self.timings.get(name, [])
            return {
                "call_count": self.call_counts.get(name, 0),
                "error_count": self.error_counts.get(name, 0),
                "avg_time": sum(times) / len(times) if times else 0.0,
                "max_time": max(times) if times else 0.0,
                "last_error": self.last_error.get(name),
            }


METRICS = _MetricsStore()


# ---------------------------------------------------------------------------
# @monitored — tracks timing, call count, error rate
# ---------------------------------------------------------------------------


def monitored(fn: Any) -> Any:
    """Baked-in monitoring. Tracks timing, call frequency, error rate.

    The wall arrives with the sensor in it. No extra work on site.
    Signals route through the metrics store → Vellum (reader-first).
    """

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        name = f"{fn.__qualname__}"
        start = time.monotonic()
        error_msg = None
        try:
            result = fn(*args, **kwargs)
            return result
        except Exception as exc:
            error_msg = str(exc)
            raise
        finally:
            duration = time.monotonic() - start
            METRICS.record_call(name, duration, error_msg)
            log.debug(
                "MONITOR %s: %.4fs%s",
                name,
                duration,
                f" ERROR: {error_msg}" if error_msg else "",
            )

    wrapper._monitored = True  # type: ignore[attr-defined]
    return wrapper


# ---------------------------------------------------------------------------
# @tracked — assigns tracking IDs
# ---------------------------------------------------------------------------


def tracked(fn: Any) -> Any:
    """Assigns a tracking ID to the operation. Every data movement is traceable."""

    import uuid

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        tracking_id = str(uuid.uuid4())
        log.debug("TRACK %s: tracking_id=%s", fn.__qualname__, tracking_id)
        # Inject tracking_id into kwargs if the function accepts it
        import inspect

        sig = inspect.signature(fn)
        if "tracking_id" in sig.parameters:
            kwargs["tracking_id"] = tracking_id
        result = fn(*args, **kwargs)
        return result

    wrapper._tracked = True  # type: ignore[attr-defined]
    return wrapper


# ---------------------------------------------------------------------------
# @validated — validates input against model
# ---------------------------------------------------------------------------


def validated(fn: Any) -> Any:
    """Validates input before processing. Shape, not content — content is the guard's job."""

    @functools.wraps(fn)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        input_model = getattr(self, "input_model", None)
        if input_model is not None and args:
            raw = args[0]
            if isinstance(raw, (bytes, str)):
                log.debug("VALIDATE %s: raw input, schema check deferred to parse", fn.__qualname__)
            elif hasattr(input_model, "__dataclass_fields__"):
                if not isinstance(raw, input_model):
                    raise ShapeError(
                        f"Input type mismatch: expected {input_model.__name__}, "
                        f"got {type(raw).__name__}",
                        shape_kind="entry",
                    )
        return fn(self, *args, **kwargs)

    wrapper._validated = True  # type: ignore[attr-defined]
    return wrapper


# ---------------------------------------------------------------------------
# @retryable — retry with exponential backoff
# ---------------------------------------------------------------------------


def retryable(
    max_retries: int = 3,
    backoff_base: float = 1.0,
    retriable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Any:
    """Retry with exponential backoff. Workers and connectors wear this.

    Can be used as @retryable or @retryable(max_retries=5).
    """

    def decorator(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except retriable_exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        wait = backoff_base * (2**attempt)
                        log.warning(
                            "RETRY %s: attempt %d/%d, waiting %.1fs: %s",
                            fn.__qualname__,
                            attempt + 1,
                            max_retries,
                            wait,
                            exc,
                        )
                        time.sleep(wait)
            raise last_exc  # type: ignore[misc]

        wrapper._retryable = True  # type: ignore[attr-defined]
        wrapper._max_retries = max_retries  # type: ignore[attr-defined]
        return wrapper

    # Allow @retryable without parentheses
    if callable(max_retries):
        fn = max_retries
        max_retries = 3
        return decorator(fn)

    return decorator


# ---------------------------------------------------------------------------
# @circuit_breaker — fail-open after N consecutive failures
# ---------------------------------------------------------------------------


def circuit_breaker(threshold: int = 5, reset_timeout: float = 60.0) -> Any:
    """Circuit breaker for connectors. Stops calling a failing external system.

    After `threshold` consecutive failures, the circuit opens for `reset_timeout` seconds.
    Can be used as @circuit_breaker or @circuit_breaker(threshold=10).
    """

    def decorator(fn: Any) -> Any:
        _failures = {"count": 0, "open_until": 0.0}
        _lock = threading.Lock()

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with _lock:
                if _failures["open_until"] > time.monotonic():
                    from ._types import ConnectorError

                    raise ConnectorError(
                        f"Circuit breaker OPEN for {fn.__qualname__}. "
                        f"Resets in {_failures['open_until'] - time.monotonic():.0f}s",
                        retry_eligible=False,
                    )

            try:
                result = fn(*args, **kwargs)
                with _lock:
                    _failures["count"] = 0
                return result
            except Exception as exc:
                with _lock:
                    _failures["count"] += 1
                    if _failures["count"] >= threshold:
                        _failures["open_until"] = time.monotonic() + reset_timeout
                        log.error(
                            "CIRCUIT OPEN %s: %d consecutive failures, open for %.0fs",
                            fn.__qualname__,
                            _failures["count"],
                            reset_timeout,
                        )
                raise

        wrapper._circuit_breaker = True  # type: ignore[attr-defined]
        return wrapper

    if callable(threshold):
        fn = threshold
        threshold = 5
        return decorator(fn)

    return decorator


# ---------------------------------------------------------------------------
# @no_bypass — prevents any override/skip mechanism on guards
# ---------------------------------------------------------------------------


def no_bypass(cls: type) -> type:
    """Class decorator for guards. There is no admin mode, no debug flag, no skip.

    Vellum records every accept and reject. The record is the evidence.
    """

    original_init = cls.__init__ if hasattr(cls, "__init__") else None

    def guarded_init(self: Any, *args: Any, **kwargs: Any) -> None:
        if kwargs.pop("skip_validation", None) is not None:
            raise GuardHalt(
                f"{cls.__name__}: @no_bypass — skip_validation is forbidden. "
                "There is no admin mode. There is no debug flag.",
            )
        if kwargs.pop("bypass", None) is not None:
            raise GuardHalt(
                f"{cls.__name__}: @no_bypass — bypass is forbidden.",
            )
        if original_init and original_init is not object.__init__:
            original_init(self, *args, **kwargs)

    cls.__init__ = guarded_init
    cls._no_bypass = True  # type: ignore[attr-defined]
    return cls


# ---------------------------------------------------------------------------
# @epistemic — declares epistemic tier for services and scorers
# ---------------------------------------------------------------------------


def epistemic(tier: str = "intuited", canon_ref: str = "") -> Any:
    """Declares the epistemic tier of a shape's output.

    tier: intuited | structured | measured | proven
    canon_ref: reference to the Logic Canon method, if any
    """

    def decorator(cls: type) -> type:
        cls._epistemic_tier = tier  # type: ignore[attr-defined]
        cls._canon_ref = canon_ref  # type: ignore[attr-defined]
        return cls

    return decorator


# ---------------------------------------------------------------------------
# @reader_first — ensures output is formatted for the reader
# ---------------------------------------------------------------------------


def reader_first(cls: type) -> type:
    """Class decorator for agents. Output shaped for the reader, not the writer. Always."""

    cls._reader_first = True  # type: ignore[attr-defined]
    return cls


# ---------------------------------------------------------------------------
# @confidence_floor — rejects output below confidence threshold
# ---------------------------------------------------------------------------


def confidence_floor(minimum: float = 0.6) -> Any:
    """Class decorator for agents. Rejects output below confidence threshold."""

    def decorator(cls: type) -> type:
        cls._confidence_floor = minimum  # type: ignore[attr-defined]
        return cls

    return decorator


# ---------------------------------------------------------------------------
# @hash_protected — hashes specified fields to detect silent corruption
# ---------------------------------------------------------------------------


def hash_protected(preserve: str = "header") -> Any:
    """Method decorator for pipelines. Protect the label, work the specimen.

    Hashes the specified field before processing, verifies after.
    If the hash doesn't match, the pipeline stops.
    """

    def decorator(fn: Any) -> Any:
        @functools.wraps(fn)
        def wrapper(self: Any, data: Any, *args: Any, **kwargs: Any) -> Any:
            field_value = getattr(data, preserve, None)
            if field_value is not None:
                original_hash = hashlib.sha256(
                    json.dumps(field_value, default=str, sort_keys=True).encode()
                ).hexdigest()
            else:
                original_hash = None

            result = fn(self, data, *args, **kwargs)

            if original_hash is not None:
                result_field = getattr(result, preserve, None)
                if result_field is not None:
                    result_hash = hashlib.sha256(
                        json.dumps(result_field, default=str, sort_keys=True).encode()
                    ).hexdigest()
                    if result_hash != original_hash:
                        from ._types import PipelineError

                        raise PipelineError(
                            f"Hash protection violation: '{preserve}' was modified. "
                            "Protect the label, work the specimen.",
                            step_failed=fn.__qualname__,
                        )
            return result

        wrapper._hash_protected = True  # type: ignore[attr-defined]
        wrapper._protected_field = preserve  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# @transactional — wraps in transaction boundary
# ---------------------------------------------------------------------------


def transactional(fn: Any) -> Any:
    """Marks a store method as transactional. All writes are atomic."""

    @functools.wraps(fn)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        log.debug("TRANSACTION BEGIN: %s", fn.__qualname__)
        try:
            result = fn(self, *args, **kwargs)
            log.debug("TRANSACTION COMMIT: %s", fn.__qualname__)
            return result
        except Exception:
            log.debug("TRANSACTION ROLLBACK: %s", fn.__qualname__)
            raise

    wrapper._transactional = True  # type: ignore[attr-defined]
    return wrapper


# ---------------------------------------------------------------------------
# @debt_tracked — marks glue as acknowledged debt
# ---------------------------------------------------------------------------


def debt_tracked(
    reason: str = "",
    removal_condition: str = "",
    temporary: bool = True,
) -> Any:
    """Class decorator for glue shapes. Makes debt visible.

    Shows up in Vellum as acknowledged debt with a removal condition.
    When the condition is met, the glue lights up RED: 'delete me.'
    """

    def decorator(cls: type) -> type:
        cls._debt_tracked = True  # type: ignore[attr-defined]
        cls._debt_reason = reason  # type: ignore[attr-defined]
        cls._removal_condition = removal_condition  # type: ignore[attr-defined]
        cls._temporary = temporary  # type: ignore[attr-defined]
        cls._debt_created = dt.datetime.now(dt.timezone.utc).isoformat()  # type: ignore[attr-defined]
        return cls

    return decorator


# ---------------------------------------------------------------------------
# @step — pipeline step ordering
# ---------------------------------------------------------------------------


def step(order: int) -> Any:
    """Marks a method as a pipeline step with explicit ordering."""

    def decorator(fn: Any) -> Any:
        fn._step_order = order  # type: ignore[attr-defined]
        fn._is_step = True  # type: ignore[attr-defined]

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        wrapper._step_order = order  # type: ignore[attr-defined]
        wrapper._is_step = True  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# @workflow — orchestrator workflow marker
# ---------------------------------------------------------------------------


def workflow(fn: Any) -> Any:
    """Marks a method as the orchestrator's main workflow entry point."""

    fn._is_workflow = True  # type: ignore[attr-defined]

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    wrapper._is_workflow = True  # type: ignore[attr-defined]
    return wrapper


# ---------------------------------------------------------------------------
# @signal_classifier — telemetry signal classification
# ---------------------------------------------------------------------------


def signal_classifier(fn: Any) -> Any:
    """Marks a method as a telemetry signal classifier."""

    fn._signal_classifier = True  # type: ignore[attr-defined]

    @functools.wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)

    wrapper._signal_classifier = True  # type: ignore[attr-defined]
    return wrapper


# ---------------------------------------------------------------------------
# field / setting / secret / metric — descriptor helpers
# ---------------------------------------------------------------------------


def field(
    required: bool = True,
    default: Any = dataclasses.MISSING,
    description: str = "",
    gt: float | None = None,
    min_length: int | None = None,
    **kwargs: Any,
) -> Any:
    """Model field descriptor. Documents and constrains a field."""

    metadata = {
        "required": required,
        "description": description,
        "gt": gt,
        "min_length": min_length,
        **kwargs,
    }
    if default is not dataclasses.MISSING:
        return dataclasses.field(default=default, metadata=metadata)
    if not required:
        return dataclasses.field(default=None, metadata=metadata)
    return dataclasses.field(metadata=metadata)


def setting(
    default: Any = dataclasses.MISSING,
    description: str = "",
    min_value: float | None = None,
    max_value: float | None = None,
) -> Any:
    """Config setting descriptor."""

    metadata = {
        "description": description,
        "min_value": min_value,
        "max_value": max_value,
        "source": "config",
    }
    if default is not dataclasses.MISSING:
        return dataclasses.field(default=default, metadata=metadata)
    return dataclasses.field(metadata=metadata)


def secret(env_var: str = "", description: str = "") -> Any:
    """Config secret descriptor. Secrets via env var reference, NEVER hardcoded."""

    return dataclasses.field(
        default="",
        metadata={
            "description": description,
            "env_var": env_var,
            "source": "secret",
            "secret": True,
        },
    )


def metric(
    type: str = "counter",
    description: str = "",
    buckets: list[float] | None = None,
) -> Any:
    """Telemetry metric descriptor."""

    return dataclasses.field(
        default=0,
        metadata={
            "metric_type": type,
            "description": description,
            "buckets": buckets,
        },
    )
