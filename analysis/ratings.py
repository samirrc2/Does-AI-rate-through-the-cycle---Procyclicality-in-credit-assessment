"""Per-cell rating reduction — the pure foundation of analysis.

Reads FROZEN capture CSVs only. Reduces replicate seeds to a per
(model, variant, firm, state) representative: MEDIAN notch, MEAN expected-notch
(logprobs), MEAN pd. ERROR is first-class (excluded; all-ERROR cell -> None).

States come in two KINDS: `macro` (the economic severity axis) and `placebo` (a
matched-format credit-irrelevant axis). The cyclicality object lives in the macro
states; the placebo states give the frame-compliance floor. We also carry the
within-cell seed dispersion (the NOISE FLOOR) and the served system_fingerprints
(batch-effect covariate) because vendor determinism is best-effort.
"""
from __future__ import annotations
import csv, hashlib, json, statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_RAW = _HERE.parent / "data" / "raw"
_FROZEN = _HERE.parent / "data" / "frozen"


@dataclass
class RatingTable:
    models: list[str]
    variants: list[str]
    family: dict[str, str]
    firms_meta: dict[str, dict]
    state_sev: dict[str, int]                      # state -> severity (both kinds)
    state_kind: dict[str, str]                     # state -> 'macro' | 'placebo'
    notch: dict                                    # (model,variant) -> firm -> state -> median notch
    expnotch: dict                                 # (model,variant) -> firm -> state -> mean expected notch
    pd: dict                                       # (model,variant) -> firm -> state -> mean pd (decimal)
    noise_sd: dict = field(default_factory=dict)   # (model,variant) -> mean within-cell notch sd
    fingerprints: dict = field(default_factory=dict)  # model -> {fingerprint: count}
    n_rows: int = 0
    n_error: int = 0
    n_parse_ok: int = 0
    n_expnotch: int = 0
    seed_indices: set = field(default_factory=set)
    mode: str = ""

    def firms(self) -> list[str]:
        return sorted(self.firms_meta)

    def states_of(self, kind: str) -> list[str]:
        return [s for s, k in sorted(self.state_kind.items(),
                                     key=lambda kv: self.state_sev[kv[0]]) if k == kind]

    def macro_order(self) -> list[str]:
        return self.states_of("macro")

    def placebo_order(self) -> list[str]:
        return self.states_of("placebo")

    def firm_support(self, mv, kind: str = "macro", table: str = "notch") -> list[str]:
        order = self.states_of(kind)
        if not order:
            return []
        d = getattr(self, table).get(mv, {})
        return [f for f in self.firms()
                if all(d.get(f, {}).get(s) is not None for s in order)]

    def stratum_of(self, firm_id: str) -> str:
        return self.firms_meta[firm_id]["stratum"]


def _frozen_ok(csv_path: Path) -> tuple[bool, str]:
    receipt = _FROZEN / f"{csv_path.stem.replace('runs_', '', 1)}.freeze.json"
    if not receipt.exists():
        return False, "no freeze receipt"
    r = json.loads(receipt.read_text())
    if hashlib.sha256(csv_path.read_bytes()).hexdigest() != r.get("sha256"):
        return False, "sha256 mismatch (CSV changed after freeze)"
    return True, "ok"


def _csv_model(path: Path) -> str | None:
    with path.open() as f:
        r = next(csv.DictReader(f), None)
    return r["model_key"] if r else None


def load_rating_table(subgrid_filter: str | None = None, allow_unfrozen: bool = False,
                      raw_dir: Path | None = None,
                      allowed_models: set[str] | None = None) -> RatingTable:
    raw_dir = raw_dir or _RAW
    glob = f"runs_{subgrid_filter}_*.csv" if subgrid_filter else "runs_*.csv"
    csvs = sorted(p for p in raw_dir.glob(glob) if p.stat().st_size > 0)
    if allowed_models is not None:
        csvs = [p for p in csvs if _csv_model(p) in allowed_models]
    if not csvs:
        raise FileNotFoundError(f"no {glob} in {raw_dir} — capture first")

    notch_reps: dict = defaultdict(list)
    exp_reps: dict = defaultdict(list)
    pd_reps: dict = defaultdict(list)
    firms_meta: dict = {}
    family: dict = {}
    state_sev: dict = {}
    state_kind: dict = {}
    fingerprints: dict = defaultdict(lambda: defaultdict(int))
    n_rows = n_error = n_parse_ok = n_exp = 0
    seeds, modes = set(), set()

    for path in csvs:
        ok, why = _frozen_ok(path)
        if not ok and not allow_unfrozen:
            raise RuntimeError(
                f"ANALYSIS WALL: {path.name} is not frozen ({why}). Run "
                f"capture/freeze.py, or pass --allow-unfrozen for the dev loop.")
        for r in csv.DictReader(path.open()):
            if subgrid_filter and r.get("subgrid") != subgrid_filter:
                continue
            n_rows += 1
            modes.add(r.get("mode", ""))
            seeds.add(int(r["seed_index"]))
            family[r["model_key"]] = r["family"]
            fid = r["firm_id"]
            firms_meta.setdefault(fid, {"tier": r["tier"], "sector": r["sector"],
                                        "stratum": r["stratum"]})
            st = r["macro_state"]
            state_kind[st] = r.get("macro_kind") or "macro"
            try:
                state_sev[st] = int(r["macro_severity"])
            except (ValueError, KeyError):
                pass
            fp = r.get("system_fingerprint") or ""
            if fp:
                fingerprints[r["model_key"]][fp] += 1
            if r["decision"] == "ERROR" or r.get("ok") != "True":
                n_error += 1
                continue
            try:
                nt = int(r["rating_notch"])
            except (ValueError, KeyError):
                n_error += 1
                continue
            n_parse_ok += 1
            key = (r["model_key"], r["prompt_variant"], fid, st)
            notch_reps[key].append(nt)
            if r.get("expected_notch") not in (None, ""):
                try:
                    exp_reps[key].append(float(r["expected_notch"])); n_exp += 1
                except ValueError:
                    pass
            if r.get("pd_1yr") not in (None, ""):
                try:
                    pd_reps[key].append(float(r["pd_1yr"]))
                except ValueError:
                    pass

    models = sorted(family)
    variants = sorted({k[1] for k in notch_reps})

    def _reduce(reps, agg):
        out: dict = defaultdict(lambda: defaultdict(dict))
        for (m, v, f, st), vals in reps.items():
            out[(m, v)][f][st] = agg(vals) if vals else None
        return {mv: {f: dict(d) for f, d in fd.items()} for mv, fd in out.items()}

    notch = _reduce(notch_reps, lambda xs: float(statistics.median(xs)))
    expnotch = _reduce(exp_reps, lambda xs: sum(xs) / len(xs))
    pd = _reduce(pd_reps, lambda xs: sum(xs) / len(xs))

    # noise floor: mean within-cell notch sd across cells with >=2 replicate seeds
    noise_sd: dict = {}
    cell_sd: dict = defaultdict(list)
    for (m, v, f, st), vals in notch_reps.items():
        if len(vals) >= 2:
            cell_sd[(m, v)].append(statistics.pstdev(vals))
    for mv, sds in cell_sd.items():
        noise_sd[mv] = sum(sds) / len(sds) if sds else None

    return RatingTable(
        models=models, variants=variants, family=family, firms_meta=firms_meta,
        state_sev=state_sev, state_kind=state_kind, notch=notch, expnotch=expnotch,
        pd=pd, noise_sd=noise_sd, fingerprints={m: dict(d) for m, d in fingerprints.items()},
        n_rows=n_rows, n_error=n_error, n_parse_ok=n_parse_ok, n_expnotch=n_exp,
        seed_indices=seeds,
        mode=("MOCK" if modes == {"MOCK"} else ("REAL" if modes == {"REAL"} else "MIXED")))


def error_rate(rt: RatingTable) -> float:
    return rt.n_error / max(1, rt.n_rows)


def dispersion(rt: RatingTable) -> dict:
    """Pooled rating dispersion across ALL macro-kind cells — the variance a macro
    shift must be visible against. Degenerate ratings => KILL."""
    vals = []
    for mv, fd in rt.notch.items():
        for f, row in fd.items():
            for st, nt in row.items():
                if nt is not None and rt.state_kind.get(st) == "macro":
                    vals.append(nt)
    if not vals:
        return {"n": 0, "mean_notch": None, "sd_notch": None,
                "distinct_notches": 0, "parse_rate": 0.0}
    return {"n": len(vals), "mean_notch": sum(vals) / len(vals),
            "sd_notch": statistics.pstdev(vals) if len(vals) > 1 else 0.0,
            "distinct_notches": len(set(round(x) for x in vals)),
            "parse_rate": rt.n_parse_ok / max(1, rt.n_rows)}


def fingerprint_summary(rt: RatingTable) -> dict:
    """Per-model distinct served fingerprints — a mid-run change is a batch-effect
    covariate to control for (vendor determinism is best-effort)."""
    return {m: {"n_distinct": len(d), "counts": d} for m, d in rt.fingerprints.items()}
