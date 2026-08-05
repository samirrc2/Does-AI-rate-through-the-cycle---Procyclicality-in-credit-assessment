"""Priced spend ledger — the hard budget wall. Per-model {calls,in,out,usd} and a
global cumulative total. The cap is enforced GLOBALLY across every orchestrator
invocation of a run by persisting to manifest/ledger_<subgrid>_<mode>.json, so a
run that captures one (model,variant) CSV at a time still cannot cross the cap in
aggregate.

Safety under concurrency: worst-case cost is RESERVED before a call and released
after; a call is refused (and the run stops) if cum + reserved + worst_case would
cross (cap - margin). Pre-flight also refuses to start if the projected worst-case
cost of the remaining work would cross the cap.
"""
from __future__ import annotations
import json, threading
from dataclasses import dataclass, field
from pathlib import Path


def price_of(price_in: float, price_out: float, in_tok: int, out_tok: int) -> float:
    return (in_tok / 1e6) * price_in + (out_tok / 1e6) * price_out


def worst_case_cost(mcfg: dict, est_in: int = 500) -> float:
    return price_of(mcfg.get("price_in", 0.0), mcfg.get("price_out", 0.0),
                    est_in, int(mcfg.get("max_tokens", 256)))


@dataclass
class Ledger:
    path: Path
    cap: float
    margin: float = 0.05
    per_model: dict = field(default_factory=dict)
    cum_usd: float = 0.0
    _reserved: float = 0.0
    _since_save: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    # ── persistence ─────────────────────────────────────────────────────────
    @classmethod
    def load(cls, path: Path, cap: float, margin: float = 0.05) -> "Ledger":
        led = cls(path=Path(path), cap=cap, margin=margin)
        if led.path.exists() and led.path.stat().st_size > 0:
            try:
                d = json.loads(led.path.read_text())
                led.per_model = d.get("per_model", {})
                led.cum_usd = float(d.get("cum_usd", 0.0))
            except (ValueError, KeyError):
                pass    # empty/corrupt ledger → start fresh (append-only capture re-derives done set)
        return led

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "cap": self.cap, "cum_usd": round(self.cum_usd, 6),
            "per_model": self.per_model,
        }, indent=2, sort_keys=True))
        tmp.replace(self.path)

    # ── the wall ──────────────────────────────────────────────────────────────
    def remaining(self) -> float:
        return (self.cap - self.margin) - (self.cum_usd + self._reserved)

    def preflight_ok(self, projected_worst_case: float) -> tuple[bool, float]:
        """True iff already-spent + projected worst-case of remaining work fits the
        cap. Returns (ok, projected_total)."""
        projected_total = self.cum_usd + projected_worst_case
        return (projected_total <= (self.cap - self.margin)), projected_total

    def reserve(self, worst_case: float) -> bool:
        """Try to reserve headroom for one call. False => cap would be crossed; the
        caller must stop (do NOT make the call)."""
        with self._lock:
            if (self.cum_usd + self._reserved + worst_case) > (self.cap - self.margin):
                return False
            self._reserved += worst_case
            return True

    def commit(self, model_key: str, price_in: float, price_out: float,
               in_tok: int, out_tok: int, worst_case: float) -> None:
        cost = price_of(price_in, price_out, in_tok, out_tok)
        with self._lock:
            self._reserved = max(0.0, self._reserved - worst_case)
            self.cum_usd += cost
            m = self.per_model.setdefault(
                model_key, {"calls": 0, "in_tok": 0, "out_tok": 0, "usd": 0.0})
            m["calls"] += 1; m["in_tok"] += in_tok; m["out_tok"] += out_tok
            m["usd"] = round(m["usd"] + cost, 6)
            self._since_save += 1
            if self._since_save >= 5:
                self._since_save = 0
                self.save()

    def release(self, worst_case: float) -> None:
        with self._lock:
            self._reserved = max(0.0, self._reserved - worst_case)

    def breached(self) -> bool:
        return self.cum_usd >= (self.cap - self.margin)
