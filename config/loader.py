"""Config loader for P5. Parses + validates the three YAMLs into typed views and
resolves a subgrid into the list of rating cells to capture. Enforces the
pilot-cheap-only guard so a flagship can never enter a <=$10 pilot."""
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
import yaml

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from schema import ModelRegistry, FirmsCfg, GridCfg, RatingCell  # noqa: E402

_HERE = Path(__file__).resolve().parent


def _load_yaml(name: str) -> dict:
    return yaml.safe_load((_HERE / name).read_text())


@dataclass(frozen=True)
class Config:
    models: ModelRegistry
    firms: FirmsCfg
    grid: GridCfg
    raw: dict            # the three raw dicts, for hashing

    def config_hash(self) -> str:
        blob = json.dumps(self.raw, sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]


def load_all() -> Config:
    m = _load_yaml("models.yaml")
    f = _load_yaml("firms.yaml")
    g = _load_yaml("grid.yaml")
    cfg = Config(
        models=ModelRegistry.model_validate(m),
        firms=FirmsCfg.model_validate(f),
        grid=GridCfg.model_validate(g),
        raw={"models": m, "firms": f, "grid": g},
    )
    _validate_subgrids(cfg)
    return cfg


def _validate_subgrids(cfg: Config) -> None:
    for name, sg in cfg.grid.subgrids.items():
        for mk in sg.models:
            mc = cfg.models.cfg(mk)   # raises on unknown
            if name == "pilot" and cfg.grid.pilot_requires_cheap and not mc.pilot:
                raise ValueError(
                    f"PILOT GUARD: subgrid 'pilot' references non-pilot (flagship) "
                    f"model {mk!r}. Flagships are reserved for the full run.")
        for v in sg.variants:
            if v not in cfg.grid.prompt_variants:
                raise ValueError(f"subgrid {name!r} uses unknown variant {v!r}")
        for ms in sg.macro_states:
            if ms not in cfg.grid.macro_states:
                raise ValueError(f"subgrid {name!r} uses unknown macro_state {ms!r}")
        for ps in sg.placebo_states:
            if ps not in cfg.grid.placebo_states:
                raise ValueError(f"subgrid {name!r} uses unknown placebo_state {ps!r}")


def subgrid(cfg: Config, name: str):
    if name not in cfg.grid.subgrids:
        raise KeyError(f"unknown subgrid {name!r}; have {sorted(cfg.grid.subgrids)}")
    return cfg.grid.subgrids[name]


def cells_for(cfg: Config, subgrid_name: str, firm_ids: list[str],
              model_key: str | None = None, variant: str | None = None) -> list[RatingCell]:
    """Enumerate rating cells for a subgrid. If model_key/variant given, restrict to
    that model / that prompt variant (orchestrator captures one CSV per
    (model, variant); each row is a firm x macro_state x seed cell)."""
    sg = subgrid(cfg, subgrid_name)
    models = [model_key] if model_key else sg.models
    variants = [variant] if variant else sg.variants
    out: list[RatingCell] = []
    for mk in models:
        for v in variants:
            for si in sg.seed_indices:
                for fid in firm_ids:
                    for ms in sg.macro_states:
                        out.append(RatingCell(model_key=mk, prompt_variant=v,
                                              seed_index=si, firm_id=fid, macro_state=ms))
    return out


if __name__ == "__main__":
    c = load_all()
    print("config_hash:", c.config_hash())
    print("models     :", list(c.models.models))
    print("pilot set  :", c.models.pilot_models())
    print("macro axis :", c.grid.macro_states)
    for name, sg in c.grid.subgrids.items():
        n = (len(sg.models) * len(sg.variants) * len(sg.seed_indices)
             * len(sg.macro_states))
        print(f"  subgrid {name:5s}: {len(sg.models)} models x {len(sg.variants)} var "
              f"x {len(sg.seed_indices)} seed x {len(sg.macro_states)} macro "
              f"x firms={sg.firms}  (cells/firm = {n})")
    print("budgets    :", c.grid.budgets.pilot, "/", c.grid.budgets.full)
