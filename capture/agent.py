"""The credit-rating call. Builds a constrained-JSON rating prompt (terse / TTC /
PIT), PREPENDS a macro-environment block (the sole perturbation), calls one model
through an OpenAI-compatible / Gemini router with a round-robin key pool + failover,
and parses a STRICT verdict -> {rating_notch, pd_bps} | ERROR (ERROR is first-class).

Design hardening (2026-07 review):
- Macro blocks are GENERIC and NUMBER-CARRIED (GDP / unemployment / spreads /
  default rate / lending standards), matched in tone + length across states, with NO
  historical-era cues, so a model cannot pattern-match to a real crisis (2008/2020)
  instead of responding to the stylized severity gradient (Graham-Harvey-Jha
  contamination warning; DECISIONS D12).
- A matched-format PLACEBO gradient (credit-irrelevant regional conditions with the
  same structure + number density) measures the frame-compliance / suggestibility
  floor; the net economic-minus-placebo coefficient is the demand-effect-adjusted
  cyclicality (D13).
- PD is elicited in BASIS POINTS (D15).
- For OpenAI models, logprobs on the rating token yield a continuous EXPECTED-NOTCH
  measure (effectively many seeds from one call) + the served system_fingerprint is
  logged as a batch-effect covariate (D14).

PILOT_MOCK=1 swaps a deterministic fake rater (procyclical, TTC-dampened, small
placebo slope) so the whole pipeline runs offline for $0. Mock is a validator, NOT a
result (D1).
"""
from __future__ import annotations
import hashlib, json, math, os, re, sys, threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "config"))
import secrets as secretstore  # noqa: E402
from schema import RATING_NOTCH  # noqa: E402

_VALID_RATINGS = tuple(RATING_NOTCH.keys())


class _GeminiVerdict(BaseModel):
    rating: str
    pd_1yr_bps: int
    rationale: str


# ── macro blocks: generic, number-carried, matched tone/length, NO era cues ──
# One template; only the five numeric lines move monotonically with severity.
def _macro(gdp, unemp, spread, deflt, standards) -> str:
    return ("MACRO ENVIRONMENT (current conditions, this fiscal period):\n"
            f"  - Real GDP growth (annualized): {gdp}\n"
            f"  - Unemployment rate: {unemp}\n"
            f"  - Investment-grade corporate credit spread: {spread}\n"
            f"  - Trailing 12-month corporate default rate: {deflt}\n"
            f"  - Bank lending standards: {standards}")


_MACRO_BLOCKS = {
    "boom":             _macro("+4.5%", "3.4%", "95 bps",  "0.6%", "easing broadly"),
    "expansion":        _macro("+2.6%", "4.2%", "135 bps", "1.4%", "modestly easing"),
    "neutral":          _macro("+1.8%", "5.0%", "175 bps", "2.3%", "unchanged"),
    "slowdown":         _macro("-0.8%", "6.4%", "320 bps", "4.1%", "tightening"),
    "severe_recession": _macro("-3.6%", "8.9%", "620 bps", "7.5%", "sharply tightening"),
}

# ── placebo blocks: matched format + number density, credit-IRRELEVANT axis ──
def _placebo(temp, daylight, rainfall, aqi, traffic) -> str:
    return ("REGIONAL CONDITIONS (current, at the company's headquarters region):\n"
            f"  - Average temperature vs seasonal norm: {temp}\n"
            f"  - Daylight hours vs annual mean: {daylight}\n"
            f"  - Monthly rainfall vs normal: {rainfall}\n"
            f"  - Regional air-quality index: {aqi}\n"
            f"  - Commuter traffic congestion: {traffic}")


_PLACEBO_BLOCKS = {
    "placebo_calm":   _placebo("+0.6°C", "+4.5%", "95 mm",  "38", "light"),
    "placebo_mild":   _placebo("+0.2°C", "+2.6%", "135 mm", "52", "moderate"),
    "placebo_normal": _placebo("0.0°C",  "+1.8%", "175 mm", "60", "typical"),
    "placebo_rough":  _placebo("-0.4°C", "-0.8%", "320 mm", "88", "heavy"),
    "placebo_storm":  _placebo("-1.1°C", "-3.6%", "620 mm", "140", "severe"),
}

_MACRO_SEV = {"boom": -2, "expansion": -1, "neutral": 0, "slowdown": 1,
              "severe_recession": 2}
_PLACEBO_SEV = {"placebo_calm": -2, "placebo_mild": -1, "placebo_normal": 0,
                "placebo_rough": 1, "placebo_storm": 2}


def block_for(state: str, kind: str) -> str:
    if kind == "placebo":
        if state not in _PLACEBO_BLOCKS:
            raise KeyError(f"unknown placebo state {state!r}")
        return _PLACEBO_BLOCKS[state]
    if state not in _MACRO_BLOCKS:
        raise KeyError(f"unknown macro state {state!r}")
    return _MACRO_BLOCKS[state]


# ── prompt variants (rating task; JSON-only) ────────────────────────────────
_SCHEMA_LINE = (
    'Respond with ONLY a JSON object and nothing else, in exactly this form: '
    '{"rating": "<one S&P long-term issuer rating from AAA down to D, using +/- '
    'modifiers, e.g. AA-, BBB+, B>", "pd_1yr_bps": <your estimated 1-year '
    'probability of default in BASIS POINTS as an integer, where 100 bps = 1%>, '
    '"rationale": "<=30 words"}.'
)

_VARIANTS = {
    "v_terse": (
        "You are a credit rating analyst. Assign a long-term issuer credit rating to "
        "the company described, based on its fundamentals and the stated operating "
        "environment. " + _SCHEMA_LINE
    ),
    "v_ttc": (
        "You are a credit rating analyst applying a THROUGH-THE-CYCLE methodology. "
        "Assign a long-term issuer credit rating that reflects the company's "
        "creditworthiness over a full economic cycle, deliberately LOOKING THROUGH "
        "transitory macroeconomic conditions rather than the current point in the "
        "cycle. " + _SCHEMA_LINE
    ),
    "v_pit": (
        "You are a credit rating analyst applying a POINT-IN-TIME methodology. Assign "
        "a long-term issuer credit rating that reflects the company's creditworthiness "
        "given CURRENT economic and financial conditions as described. " + _SCHEMA_LINE
    ),
    # Instruction-level PLACEBO: asks for STABILITY with NO rating-philosophy /
    # through-the-cycle reasoning. If v_stable flattens the rating (and the PD) as
    # much as v_ttc, then v_ttc's flattening is generic 'be stable' compliance —
    # anchoring — not through-the-cycle reasoning (DECISIONS D20).
    "v_stable": (
        "You are a credit rating analyst. Assign a long-term issuer credit rating "
        "that is STABLE and does not change much in response to short-term "
        "conditions. " + _SCHEMA_LINE
    ),
}

_USER_TEMPLATE = (
    "{macro}\n\n"
    "COMPANY FUNDAMENTALS (most recent fiscal year):\n"
    "{fundamentals}\n\n"
    "Assign the rating. Return only the JSON verdict."
)


def system_prompt(variant: str) -> str:
    if variant not in _VARIANTS:
        raise KeyError(f"unknown prompt variant {variant!r}; have {sorted(_VARIANTS)}")
    return _VARIANTS[variant]


def build_user(fundamentals: str, state: str, kind: str) -> str:
    return _USER_TEMPLATE.format(macro=block_for(state, kind), fundamentals=fundamentals)


def prompt_hash(system: str, user: str) -> str:
    return hashlib.sha256((system + "\n\x1e\n" + user).encode()).hexdigest()[:16]


# ── strict parse -> notch + pd(bps) ─────────────────────────────────────────
@dataclass
class Verdict:
    rating: str
    notch: int
    pd_bps: int | None
    pd_1yr: float | None
    rationale: str


_RATING_RE = re.compile(r'"rating"\s*:\s*"([A-Za-z]{1,3}[+\-]?)"')
_PD_BPS_RE = re.compile(r'"pd_1yr_bps"\s*:\s*([0-9]*\.?[0-9]+)')
_PD_DEC_RE = re.compile(r'"pd_1yr"\s*:\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)')


def _norm_rating(raw: str) -> str | None:
    if raw is None:
        return None
    r = raw.strip().upper().replace(" ", "")
    r = r.replace("AAA+", "AAA").replace("AAA-", "AAA")
    if r in RATING_NOTCH:
        return r
    if r in ("DEFAULT", "SD", "RD", "DDD", "DD"):
        return "D"
    base = re.match(r"[ABCD]+[+\-]?", r)
    if base and base.group(0) in RATING_NOTCH:
        return base.group(0)
    return None


def _bps_to_dec(bps) -> float | None:
    try:
        v = float(bps)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return min(1.0, v / 10000.0)


def parse_strict(raw: str) -> Verdict:
    txt = raw.strip()
    if txt.startswith("```"):
        txt = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", txt.strip())
    start = txt.find("{")
    obj = None
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(txt[start:])
        except json.JSONDecodeError:
            obj = None
    pd_bps = None
    pd_dec = None
    if isinstance(obj, dict) and "rating" in obj:
        rating = _norm_rating(str(obj.get("rating")))
        if obj.get("pd_1yr_bps") is not None:
            try:
                pd_bps = int(round(float(obj["pd_1yr_bps"])))
            except (TypeError, ValueError):
                pd_bps = None
        if pd_bps is None and obj.get("pd_1yr") is not None:
            pd_dec = _bps_to_dec(float(obj["pd_1yr"]) * 10000) if _is_num(obj.get("pd_1yr")) else None
        rationale = " ".join(str(obj.get("rationale", "")).split()[:30])
    else:
        m = _RATING_RE.search(txt)
        if not m:
            raise ValueError(f"no parseable 'rating' in response: {raw[:160]!r}")
        rating = _norm_rating(m.group(1))
        bm = _PD_BPS_RE.search(txt)
        if bm:
            try:
                pd_bps = int(round(float(bm.group(1))))
            except ValueError:
                pd_bps = None
        rationale = "(recovered from malformed JSON)"
    if rating is None:
        raise ValueError(f"rating not on the S&P scale: {raw[:160]!r}")
    pd = _bps_to_dec(pd_bps) if pd_bps is not None else pd_dec
    return Verdict(rating=rating, notch=RATING_NOTCH[rating], pd_bps=pd_bps,
                   pd_1yr=pd, rationale=rationale)


def _is_num(x) -> bool:
    try:
        float(x); return True
    except (TypeError, ValueError):
        return False


@dataclass
class AgentResult:
    ok: bool
    verdict: Verdict | None
    raw_response: str
    input_tokens: int
    output_tokens: int
    error: str | None
    prompt_hash: str
    key_id: str = ""
    expected_notch: float | None = None       # continuous notch from logprobs (OpenAI)
    system_fingerprint: str = ""
    logprobs_json: str = ""


# ── deterministic mock rater ────────────────────────────────────────────────
def _u01(*parts) -> float:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return int(h[:12], 16) / 0xFFFFFFFFFFFF


_TIER_BASE = {"high_ig": 20, "low_ig": 16, "crossover": 12, "high_yield": 8,
              "distressed": 4}
_VARIANT_SENS = {"v_terse": 1.1, "v_ttc": 0.35, "v_pit": 1.4, "v_stable": 0.30}
_PLACEBO_SENS = 0.15   # small suggestibility floor the mock injects for placebo cells


def _notch_to_rating(n: int) -> str:
    n = max(1, min(21, int(round(n))))
    for r, v in RATING_NOTCH.items():
        if v == n and r in ("AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+",
                            "BBB", "BBB-", "BB+", "BB", "BB-", "B+", "B", "B-",
                            "CCC+", "CCC", "CCC-", "CC", "C"):
            return r
    return "B"


def _mock_call(model_cfg, firm: dict, variant: str, state: str, kind: str, seed: int):
    tier = firm.get("tier", "crossover")
    fid = firm["firm_id"]
    if kind == "placebo":
        sev = _PLACEBO_SEV.get(state, 0); sens = _PLACEBO_SENS
    else:
        sev = _MACRO_SEV.get(state, 0); sens = _VARIANT_SENS.get(variant, 1.0)
    base = _TIER_BASE.get(tier, 12)
    firm_off = (_u01("firm", fid) - 0.5) * 4.0
    model_off = (_u01("model", model_cfg.get("api_model", "x")) - 0.5) * 1.5
    noise = (_u01("noise", model_cfg.get("api_model", "x"), variant, seed, fid, state) - 0.5) * 0.4
    notch_c = base + firm_off + model_off - sens * sev + noise      # continuous
    notch = int(max(1, min(21, round(notch_c))))
    rating = _notch_to_rating(notch)
    pd = 1.0 / (1.0 + math.exp(0.55 * (notch - 8) - 0.25 * sev))
    pd_bps = int(round(min(9999, max(2, pd * 10000))))
    raw = json.dumps({"rating": rating, "pd_1yr_bps": pd_bps, "rationale": "mock rating"})
    exp_notch = max(1.0, min(21.0, notch_c))                       # "logprobs" surrogate
    return raw, 90, 22, exp_notch


# ── live provider router ────────────────────────────────────────────────────
_POOLS: dict[str, dict] = {}
_POOLS_LOCK = threading.Lock()
_CLIENTS: dict[tuple, Any] = {}
_CLIENTS_LOCK = threading.Lock()


class AllKeysExhausted(RuntimeError):
    pass


_BENCH_COOLDOWN = 30.0


def _pool(provider: str) -> dict:
    with _POOLS_LOCK:
        p = _POOLS.get(provider)
        if p is None:
            p = {"keys": secretstore.get_pool(provider), "idx": 0, "benched": {}}
            _POOLS[provider] = p
        return p


def _next_key(provider: str) -> tuple[str, int]:
    import time
    p = _pool(provider)
    with _POOLS_LOCK:
        now = time.monotonic(); n = len(p["keys"])
        for _ in range(n):
            i = p["idx"] % n; p["idx"] += 1
            recover_at = p["benched"].get(i)
            if recover_at is None or recover_at <= now:
                p["benched"].pop(i, None)
                return p["keys"][i], i
        raise AllKeysExhausted(f"all {n} {provider} keys rate-limited (cooling down)")


def _bench_key(provider: str, key_id: int) -> None:
    import time
    p = _pool(provider)
    with _POOLS_LOCK:
        p["benched"][key_id] = time.monotonic() + _BENCH_COOLDOWN


def _client(provider: str, base_url: str | None, api_key: str, key_id: int):
    ck = (provider, key_id)
    with _CLIENTS_LOCK:
        c = _CLIENTS.get(ck)
        if c is not None:
            return c
        if provider in ("openai", "xai"):
            from openai import OpenAI
            kwargs = {"api_key": api_key, "max_retries": 0}
            if base_url:
                kwargs["base_url"] = base_url
            elif provider == "xai":
                kwargs["base_url"] = "https://api.x.ai/v1"
            c = OpenAI(**kwargs)
        elif provider in ("gemini", "google"):
            from google import genai
            c = genai.Client(api_key=api_key)
        else:
            raise ValueError(f"unknown provider {provider!r}")
        _CLIENTS[ck] = c
        return c


def _is_ratelimit(msg: str) -> bool:
    m = msg.lower()
    return any(k in m for k in ("429", "rate limit", "rate_limit", "quota",
                                "resource_exhausted", "insufficient_quota"))


def _expected_notch_from_logprobs(content: str, lp_content) -> tuple[float | None, str]:
    """Best-effort continuous notch from the rating-token logprob distribution.
    Locates the rating value in the token stream, takes the first value-token's
    top_logprobs, substitutes each alternative for the first token (keeping the rest),
    maps to a valid rating -> notch, and returns the probability-weighted mean notch.
    Returns (expected_notch|None, compact_json_of_alternatives). Robust: None if the
    rating is not cleanly localisable."""
    if not lp_content:
        return None, ""
    text = ""; spans = []
    for t in lp_content:
        tok = getattr(t, "token", "")
        spans.append((len(text), len(text) + len(tok), t)); text += tok
    m = re.search(r'"rating"\s*:\s*"', text)
    if not m:
        return None, ""
    val_start = m.end(); q = text.find('"', val_start)
    if q == -1:
        return None, ""
    val_tokens = [t for (s, e, t) in spans if s < q and e > val_start]
    if not val_tokens:
        return None, ""
    first = val_tokens[0]
    remainder = "".join(getattr(t, "token", "") for t in val_tokens[1:])
    tops = getattr(first, "top_logprobs", None) or []
    dist = []
    for alt in tops:
        cand = (getattr(alt, "token", "") + remainder).strip().strip('"').upper()
        r = _norm_rating(cand)
        if r is not None:
            dist.append((RATING_NOTCH[r], math.exp(getattr(alt, "logprob", -30.0)), cand))
    if not dist:
        return None, ""
    z = sum(w for _, w, _ in dist)
    if z <= 0:
        return None, ""
    exp = sum(n * w for n, w, _ in dist) / z
    compact = json.dumps({c: round(w / z, 4) for _, w, c in dist})[:400]
    return exp, compact


def _openai_compatible(mcfg, system, user, temperature, seed, want_logprobs):
    provider = mcfg["provider"]
    last = None
    for _attempt in range(max(1, len(_pool(provider)["keys"]))):
        try:
            api_key, key_id = _next_key(provider)
        except AllKeysExhausted as e:
            raise RuntimeError(str(e)) from e
        client = _client(provider, mcfg.get("base_url"), api_key, key_id)
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        base = {"model": mcfg["api_model"], "messages": msgs,
                "response_format": {"type": "json_object"}}
        if seed is not None:
            base["seed"] = seed
        if mcfg.get("reasoning_effort"):
            base["reasoning_effort"] = mcfg["reasoning_effort"]
        if want_logprobs:
            base["logprobs"] = True; base["top_logprobs"] = 20
        max_out = int(mcfg.get("max_tokens", 256))
        for tok_param, with_temp in (("max_completion_tokens", True),
                                     ("max_completion_tokens", False),
                                     ("max_tokens", True)):
            kwargs = dict(base); kwargs[tok_param] = max_out
            if with_temp:
                kwargs["temperature"] = temperature
            try:
                resp = client.chat.completions.create(**kwargs)
            except Exception as e:
                last = e; m = str(e).lower()
                if _is_ratelimit(m):
                    _bench_key(provider, key_id); break
                if "logprobs" in m:
                    base.pop("logprobs", None); base.pop("top_logprobs", None); continue
                if "reasoning_effort" in m:
                    base.pop("reasoning_effort", None); continue
                if "response_format" in m:
                    base.pop("response_format", None); continue
                if any(k in m for k in ("temperature", "max_tokens", "max_completion",
                                        "unsupported", "unknown parameter")):
                    continue
                raise
            u = resp.usage
            content = resp.choices[0].message.content or ""
            if content.strip():
                fp = getattr(resp, "system_fingerprint", "") or ""
                lp = None
                try:
                    lp = resp.choices[0].logprobs.content
                except Exception:
                    lp = None
                exp, lpj = _expected_notch_from_logprobs(content, lp) if lp else (None, "")
                return content, u.prompt_tokens, u.completion_tokens, str(key_id), fp, exp, lpj
            last = RuntimeError(f"empty content (finish={resp.choices[0].finish_reason})")
    raise last or RuntimeError("all openai-compatible attempts failed")


def _call_gemini(mcfg, system, user, temperature, seed):
    from google.genai import types
    provider = "gemini"; last = None
    for _attempt in range(max(1, len(_pool(provider)["keys"]))):
        try:
            api_key, key_id = _next_key(provider)
        except AllKeysExhausted as e:
            raise RuntimeError(str(e)) from e
        client = _client(provider, None, api_key, key_id)
        base = {"system_instruction": system, "temperature": temperature,
                "max_output_tokens": int(mcfg.get("max_tokens", 256)),
                "response_mime_type": "application/json"}
        tb = mcfg.get("thinking_budget")
        if tb is not None:
            try:
                base["thinking_config"] = types.ThinkingConfig(thinking_budget=int(tb))
            except Exception:
                pass
        if seed is not None:
            base["seed"] = seed
        for use_schema in (True, False):
            gc = dict(base)
            if use_schema:
                gc["response_schema"] = _GeminiVerdict
            try:
                resp = client.models.generate_content(
                    model=mcfg["api_model"], contents=user,
                    config=types.GenerateContentConfig(**gc))
            except Exception as e:
                last = e
                if _is_ratelimit(str(e)):
                    _bench_key(provider, key_id); break
                if use_schema and any(k in str(e).lower() for k in
                                      ("schema", "response_schema", "unknown", "invalid")):
                    continue
                raise
            um = resp.usage_metadata
            return ((resp.text or ""), um.prompt_token_count,
                    (um.candidates_token_count or 0), str(key_id), "", None, "")
    raise last or RuntimeError("all gemini attempts failed")


def call_model(mcfg, system, user, temperature, seed):
    provider = mcfg["provider"]
    if provider in ("openai", "xai"):
        return _openai_compatible(mcfg, system, user, temperature, seed,
                                  bool(mcfg.get("logprobs")))
    if provider in ("gemini", "google"):
        return _call_gemini(mcfg, system, user, temperature, seed)
    raise ValueError(f"unknown provider {provider!r}")


def run_agent(model_cfg: dict, firm: dict, variant: str, state: str, kind: str,
              temperature: float, seed: int) -> AgentResult:
    system = system_prompt(variant)
    user = build_user(firm["serialized"], state, kind)
    ph = prompt_hash(system, user)
    key_id = ""; fp = ""; exp = None; lpj = ""
    try:
        if os.environ.get("PILOT_MOCK") == "1":
            raw, in_tok, out_tok, exp = _mock_call(model_cfg, firm, variant, state, kind, seed)
            fp = "mock-fp-v1"
        else:
            raw, in_tok, out_tok, key_id, fp, exp, lpj = call_model(
                model_cfg, system, user, temperature, seed)
    except Exception as e:
        return AgentResult(False, None, "", 0, 0, f"{type(e).__name__}: {e}", ph, key_id)
    try:
        v = parse_strict(raw)
    except Exception as e:
        return AgentResult(False, None, raw, in_tok, out_tok, f"parse: {e}", ph, key_id,
                           system_fingerprint=fp)
    return AgentResult(True, v, raw, in_tok, out_tok, None, ph, key_id,
                       expected_notch=exp, system_fingerprint=fp, logprobs_json=lpj)
