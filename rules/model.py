"""Load and validate a Seance skeleton JSON file into a typed object.

A skeleton describes a trading rule: parameters, pool configuration, sweep
detections, and the ordered resolution predicates.  This module reads the
JSON, validates every field, parses every predicate through ``rules/expr``,
and returns a fully validated :class:`Skeleton`.

Every structural or semantic problem raises :class:`SeanceModelError` with a
message that names the offending field — never a bare ``KeyError``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

# Import from the sibling expr module.  Works whether this file is imported
# as rules.model (package) or run directly with rules/ on sys.path.
try:
    from .expr import compile_expr, SeanceParseError, SeanceError
except ImportError:                       # pragma: no cover
    from expr import compile_expr, SeanceParseError, SeanceError


class SeanceModelError(SeanceError):
    """Raised when a skeleton JSON fails structural or semantic validation."""


# ── validated data classes ──────────────────────────────────────────────── #

@dataclass(frozen=True)
class Param:
    key: str
    type: str          # only "int" for now
    default: int
    min: int | None
    title: str


@dataclass(frozen=True)
class Detection:
    event: str
    side: str          # "high" | "low"
    when: Any          # AST node from expr.compile_expr


@dataclass(frozen=True)
class Resolution:
    event: str
    target: str        # "high" | "low" | "any"   (JSON key is "for")
    when: Any          # AST node


@dataclass(frozen=True)
class Pool:
    lookback_param: str


@dataclass(frozen=True)
class Skeleton:
    name: str
    id: str
    version: str
    params: Dict[str, Param]
    closed_candles_only: bool
    pool: Pool
    detections: List[Detection]
    detection_conflict: str
    collision_policy: str
    resolutions: List[Resolution]

    def param_defaults(self) -> Dict[str, int]:
        """Return ``{key: default}`` for every declared parameter."""
        return {k: v.default for k, v in self.params.items()}


# ── constants ─────────────────────────────────────────────────────────────── #

_REQUIRED_TOP = (
    "name", "id", "version", "params", "closed_candles_only",
    "pool", "detections", "detection_conflict", "collision_policy",
    "resolutions",
)

_VALID_SIDES = ("high", "low")
_VALID_TARGETS = ("high", "low", "any")


# ── public API ────────────────────────────────────────────────────────────── #

def load(path) -> Skeleton:
    """Read *path* as JSON and return a validated :class:`Skeleton`."""
    data = json.loads(Path(path).read_text())
    return from_dict(data)


def from_dict(data: dict) -> Skeleton:
    """Validate a parsed JSON dict and return a :class:`Skeleton`.

    Raises :class:`SeanceModelError` — never ``KeyError`` — for any missing
    or invalid field.
    """
    if not isinstance(data, dict):
        raise SeanceModelError("skeleton root must be a JSON object")

    # Require every top-level field up-front so a missing key never surfaces
    # as a raw KeyError deeper in the parser.
    for key in _REQUIRED_TOP:
        if key not in data:
            raise SeanceModelError(f"missing required field {key!r}")

    # name / id / version — basic sanity
    for k in ("name", "id", "version"):
        v = data[k]
        if not isinstance(v, str) or not v:
            raise SeanceModelError(f"{k!r} must be a non-empty string")

    params = _parse_params(data["params"])
    pool = _parse_pool(data["pool"], set(params))

    cco = data["closed_candles_only"]
    if not isinstance(cco, bool):
        raise SeanceModelError(
            f"closed_candles_only must be a boolean, got {type(cco).__name__}")

    dc = data["detection_conflict"]
    if not isinstance(dc, str) or not dc:
        raise SeanceModelError("detection_conflict must be a non-empty string")

    cp = data["collision_policy"]
    if not isinstance(cp, str) or not cp:
        raise SeanceModelError("collision_policy must be a non-empty string")

    param_names = set(params)
    detections = _parse_detections(data["detections"], param_names)
    resolutions = _parse_resolutions(data["resolutions"], param_names)

    return Skeleton(
        name=data["name"],
        id=data["id"],
        version=data["version"],
        params=params,
        closed_candles_only=cco,
        pool=pool,
        detections=detections,
        detection_conflict=dc,
        collision_policy=cp,
        resolutions=resolutions,
    )


# ── helpers ──────────────────────────────────────────────────────────────── #

def _parse_params(raw) -> Dict[str, Param]:
    if not isinstance(raw, list):
        raise SeanceModelError("params must be a list")
    params: Dict[str, Param] = {}
    for i, p in enumerate(raw):
        if not isinstance(p, dict):
            raise SeanceModelError(f"params[{i}] must be an object")
        key = p.get("key")
        if not key or not isinstance(key, str):
            raise SeanceModelError(f"params[{i}] is missing 'key'")

        ptype = p.get("type", "int")
        if ptype != "int":
            raise SeanceModelError(
                f"param {key!r}: unsupported type {ptype!r} (only 'int')")

        default = p.get("default")
        if not isinstance(default, int) or isinstance(default, bool):
            raise SeanceModelError(f"param {key!r}: default must be an integer")

        pmin = p.get("min")
        if pmin is not None:
            if not isinstance(pmin, int) or isinstance(pmin, bool):
                raise SeanceModelError(f"param {key!r}: min must be an integer")
            if default < pmin:
                raise SeanceModelError(
                    f"param {key!r}: default ({default}) is below min ({pmin})")

        title = p.get("title", key)
        if not isinstance(title, str):
            raise SeanceModelError(f"param {key!r}: title must be a string")

        params[key] = Param(key=key, type=ptype, default=default,
                            min=pmin, title=title)
    return params


def _parse_pool(raw, param_names) -> Pool:
    if not isinstance(raw, dict):
        raise SeanceModelError("pool must be an object")
    lookback = raw.get("lookback_param")
    if not lookback or not isinstance(lookback, str):
        raise SeanceModelError("pool.lookback_param is required")
    if lookback not in param_names:
        raise SeanceModelError(
            f"pool.lookback_param {lookback!r} is not a declared parameter")
    return Pool(lookback_param=lookback)


def _parse_detections(raw, param_names) -> List[Detection]:
    if not isinstance(raw, list):
        raise SeanceModelError("detections must be a list")
    if not raw:
        raise SeanceModelError("detections must not be empty")
    out: List[Detection] = []
    for i, d in enumerate(raw):
        if not isinstance(d, dict):
            raise SeanceModelError(f"detections[{i}] must be an object")
        event = d.get("event")
        if not event or not isinstance(event, str):
            raise SeanceModelError(f"detections[{i}] is missing 'event'")
        side = d.get("side")
        if side not in _VALID_SIDES:
            raise SeanceModelError(
                f"detections[{i}] ({event}): side must be 'high' or 'low', "
                f"got {side!r}")
        when_str = d.get("when")
        if not when_str or not isinstance(when_str, str):
            raise SeanceModelError(
                f"detections[{i}] ({event}): 'when' must be a non-empty string")
        try:
            ast = compile_expr(when_str, param_names)
        except SeanceParseError as exc:
            raise SeanceModelError(
                f"detections[{i}] ({event}): cannot parse predicate: {exc}"
            ) from exc
        out.append(Detection(event=event, side=side, when=ast))
    return out


def _parse_resolutions(raw, param_names) -> List[Resolution]:
    if not isinstance(raw, list):
        raise SeanceModelError("resolutions must be a list")
    if not raw:
        raise SeanceModelError("resolutions must not be empty")
    out: List[Resolution] = []
    for i, r in enumerate(raw):
        if not isinstance(r, dict):
            raise SeanceModelError(f"resolutions[{i}] must be an object")
        event = r.get("event")
        if not event or not isinstance(event, str):
            raise SeanceModelError(f"resolutions[{i}] is missing 'event'")
        target = r.get("for")
        if target not in _VALID_TARGETS:
            raise SeanceModelError(
                f"resolutions[{i}] ({event}): 'for' must be 'high', 'low' or "
                f"'any', got {target!r}")
        when_str = r.get("when")
        if not when_str or not isinstance(when_str, str):
            raise SeanceModelError(
                f"resolutions[{i}] ({event}): 'when' must be a non-empty string")
        try:
            ast = compile_expr(when_str, param_names)
        except SeanceParseError as exc:
            raise SeanceModelError(
                f"resolutions[{i}] ({event}): cannot parse predicate: {exc}"
            ) from exc
        out.append(Resolution(event=event, target=target, when=ast))
    return out


__all__ = [
    "SeanceModelError",
    "Param", "Detection", "Resolution", "Pool", "Skeleton",
    "load", "from_dict",
]
