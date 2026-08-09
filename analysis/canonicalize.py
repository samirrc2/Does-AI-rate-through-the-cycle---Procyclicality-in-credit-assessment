"""Canonical claims.json serialization for cross-platform byte identity.

Floating-point ULP noise (~1e-15) across CPU/OS builds must not change the
committed artifact. Every float is quantized through an integer at fixed scale,
then written as a fixed-width decimal JSON number so Mac/Linux dumps match.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

# Paper cites ~3 decimals; keep 12 so science is unchanged while killing ULP noise.
CLAIMS_FLOAT_DECIMALS = 12
_SCALE = 10 ** CLAIMS_FLOAT_DECIMALS
_PLACEHOLDER = re.compile(r'"__Q(-?\d+)__"')


def quantize(obj: Any) -> Any:
    """Recursively quantize floats via integer scale; leave other JSON types alone."""
    if isinstance(obj, dict):
        return {k: quantize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [quantize(v) for v in obj]
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"non-finite float in claims: {obj!r}")
        return int(round(obj * _SCALE)) / _SCALE
    return obj


def _mark_floats(obj: Any) -> Any:
    """Replace floats with placeholder strings carrying the scaled integer."""
    if isinstance(obj, dict):
        return {k: _mark_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_mark_floats(v) for v in obj]
    if isinstance(obj, bool) or obj is None:
        return obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, float):
        if not math.isfinite(obj):
            raise ValueError(f"non-finite float in claims: {obj!r}")
        return f"__Q{int(round(obj * _SCALE))}__"
    return obj


def _unquote_quantized(match: re.Match[str]) -> str:
    n = int(match.group(1))
    sign = "-" if n < 0 else ""
    n = abs(n)
    whole, frac = divmod(n, _SCALE)
    return f"{sign}{whole}.{frac:0{CLAIMS_FLOAT_DECIMALS}d}"


def dumps_claims(obj: Any) -> str:
    """JSON text with sort_keys, indent=2, and fixed-decimal floats (trailing newline)."""
    marked = _mark_floats(quantize(obj))
    text = json.dumps(marked, indent=2, sort_keys=True, allow_nan=False)
    return _PLACEHOLDER.sub(_unquote_quantized, text) + "\n"


def write_claims(path, obj: Any) -> None:
    path.write_text(dumps_claims(obj))
