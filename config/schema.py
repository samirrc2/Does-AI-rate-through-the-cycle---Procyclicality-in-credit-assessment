"""ONE config schema for P5 (pydantic v2). The atom is a *rating cell*:
(model_key, prompt_variant, seed_index, firm_id, macro_state) -> one
constrained-JSON credit-rating call. This module validates
models.yaml / firms.yaml / grid.yaml and exposes typed views. Importing it does
not touch the network or spend anything.

The scientific object: firm FUNDAMENTALS are byte-identical across macro states;
only the macro-context block changes. Any rating movement across macro states,
holding fundamentals fixed, is by construction procyclicality — the through-the-
cycle (TTC) null is a zero macro coefficient.
"""
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

Provider = Literal["openai", "gemini", "google", "xai", "anthropic"]

# ── canonical vocabularies (kept in sync with firms.yaml / grid.yaml) ────────
CREDIT_TIERS = ("high_ig", "low_ig", "crossover", "high_yield", "distressed")
SECTORS = (
    "industrials", "consumer_staples", "consumer_discretionary", "technology",
    "utilities", "healthcare", "energy", "real_estate",
)

# S&P-style letter scale -> integer NOTCH (higher = safer). 21 = AAA, 1 = D/C.
RATING_NOTCH: dict[str, int] = {
    "AAA": 21, "AA+": 20, "AA": 19, "AA-": 18, "A+": 17, "A": 16, "A-": 15,
    "BBB+": 14, "BBB": 13, "BBB-": 12, "BB+": 11, "BB": 10, "BB-": 9,
    "B+": 8, "B": 7, "B-": 6, "CCC+": 5, "CCC": 4, "CCC-": 3, "CC": 2, "C": 1,
    # default states collapse to the floor notch
    "SD": 1, "RD": 1, "D": 1, "DDD": 1,
}
NOTCH_TO_RATING = {v: k for k, v in RATING_NOTCH.items()
                   if k in ("AAA", "AA", "A", "BBB", "BB", "B", "CCC", "CC", "C")}
DECISIONS = ("rated", "ERROR")   # ERROR is first-class


# ── models.yaml ─────────────────────────────────────────────────────────────
class ModelCfg(BaseModel):
    family: str
    provider: Provider
    key_env: str
    base_url: str | None = None
    api_model: str
    price_in: float = Field(ge=0)      # USD / 1M input tokens
    price_out: float = Field(ge=0)     # USD / 1M output tokens
    max_tokens: int = Field(gt=0, default=256)
    reasoning_effort: str | None = None
    temperature: float | None = None        # per-model decoding temperature
                                            # override. None -> grid.judge_temperature.
                                            # Set ONLY where a model refuses the grid
                                            # default (gpt-6-astra accepts temp=1 only);
                                            # the captured row records the EFFECTIVE
                                            # value, never the grid default.
    thinking_budget: int | None = None      # Gemini: 0 disables thinking
    logprobs: bool = False                  # request token logprobs (OpenAI-compatible)
    pilot: bool = False
    extra: dict = Field(default_factory=dict)
    probe_receipt: dict | None = None

    @field_validator("provider")
    @classmethod
    def _norm(cls, v: str) -> str:
        return "gemini" if v == "google" else v


class ModelRegistry(BaseModel):
    models: dict[str, ModelCfg]

    def pilot_models(self) -> list[str]:
        return [k for k, m in self.models.items() if m.pilot]

    def cfg(self, key: str) -> ModelCfg:
        if key not in self.models:
            raise KeyError(f"unknown model {key!r}; have {sorted(self.models)}")
        return self.models[key]


# ── firms.yaml (the synthetic fixed-fundamentals battery spec) ──────────────
class FirmSizes(BaseModel):
    full: int = Field(gt=0)
    pilot: int = Field(gt=0)

    @model_validator(mode="after")
    def _pilot_le_full(self):
        if self.pilot > self.full:
            raise ValueError("firms pilot size must be <= full size")
        return self


class FirmsCfg(BaseModel):
    seed: int
    sizes: FirmSizes
    tiers: list[str]                    # credit-quality strata (clustering unit)
    sectors: list[str]
    serialization: dict

    @model_validator(mode="after")
    def _check(self):
        if set(self.tiers) - set(CREDIT_TIERS):
            raise ValueError(f"firm tier not in canonical CREDIT_TIERS {CREDIT_TIERS}")
        if set(self.sectors) - set(SECTORS):
            raise ValueError(f"firm sector not in canonical SECTORS {SECTORS}")
        return self


# ── grid.yaml ───────────────────────────────────────────────────────────────
class Budgets(BaseModel):
    pilot: float = Field(gt=0)
    full: float = Field(gt=0)
    seeds: float | None = None           # AMENDMENT #7 replication-stability arm
    real: float | None = None            # AMENDMENT #7 real-fundamentals arm
    ofat: float | None = None            # AMENDMENT #6 macro-factor decomposition
    frontier: float | None = None        # AMENDMENT #5 confirmatory frontier grids
    probe_astra: float | None = None     # AMENDMENT #4 frontier probe arm. Declared so
                                        # analysis/run.py's ran_clean gate compares spend
                                        # against THIS arm's cap; without it the gate falls
                                        # back to the $10 pilot cap and reports a spurious
                                        # failure for a run that never breached its own.


class Subgrid(BaseModel):
    models: list[str]
    variants: list[str]
    seed_indices: list[int]
    macro_states: list[str]
    placebo_states: list[str] = []          # matched-format credit-irrelevant arm
    ofat_states: list[str] = []             # one-factor-at-a-time decomposition
    firms: Literal["pilot", "full", "real"]   # "real" = SEC-XBRL battery
                                              # (AMENDMENT #7, referee 1 c1/c2)


class GridCfg(BaseModel):
    seed_master: int
    analysis_seed: int
    budgets: Budgets
    stop_margin_usd: float = 0.05
    max_workers: int = Field(gt=0, default=5)
    max_retries: int = Field(ge=0, default=10)
    judge_temperature: float = 0.0
    rpm_limits: dict[str, float] = Field(default_factory=dict)
    daily_limits: dict[str, int] = Field(default_factory=dict)
    prompt_variants: list[str]
    macro_states: dict[str, int]        # name -> severity index (higher = worse)
    placebo_states: dict[str, int] = {}  # name -> matched severity on a credit-irrelevant axis
    # Severities are REUSED across the five factors here, so no distinctness
    # check applies -- unlike macro_states, where it guards identification.
    ofat_states: dict[str, int] = Field(default_factory=dict)
    subgrids: dict[str, Subgrid]
    pilot_requires_cheap: bool = True

    @model_validator(mode="after")
    def _check_macro(self):
        # severity must be a distinct, ordered integer axis (the regressor)
        vals = list(self.macro_states.values())
        if len(set(vals)) != len(vals):
            raise ValueError("macro_states severities must be distinct")
        return self


# ── the run-time atom ───────────────────────────────────────────────────────
class RatingCell(BaseModel):
    """One unit of capture. Fully identifies a single billable rating call.
    Fundamentals are fixed by firm_id; macro_state is the ONLY perturbation."""
    model_key: str
    prompt_variant: str
    seed_index: int
    firm_id: str
    macro_state: str

    def key(self) -> tuple[str, str, int, str, str]:
        return (self.model_key, self.prompt_variant, self.seed_index,
                self.firm_id, self.macro_state)
