"""Secrets loader for P4. Loads ../API Keys/keys.env.txt. Supports numbered key
POOLS per provider (OPENAI_API_KEY_1/_2/_3, GEMINI_API_KEY_1/_2/_3) plus a bare
name (OPENAI_API_KEY). Blanks/placeholders are skipped. Environment wins over file.
The pool is round-robined by the caller (agent.py), which benches a key on
429/quota and falls back to the next; it aborts only when every key is exhausted."""
from __future__ import annotations
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_KEY_FILENAMES = ("keys.env", "keys.env.txt", "keys.txt")

_PROVIDER_PREFIX = {
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
    "xai": "XAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def _resolve_keys_file() -> Path:
    override = os.environ.get("KEYS_ENV_PATH")
    if override:
        return Path(override).expanduser()
    for base in [_HERE, *_HERE.parents][:6]:
        for d in (base / "API Keys", base):
            for fn in _KEY_FILENAMES:
                c = d / fn
                if c.exists():
                    return c
    return _HERE / "keys.env"


_KEYS_FILE = _resolve_keys_file()


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


_FILE_CACHE = _parse_env_file(_KEYS_FILE)


def _usable(v: str | None) -> bool:
    if not v:
        return False
    if "..." in v:                       # template/placeholder marker
        return False
    if len(v) < 12:
        return False
    return True


def get_raw(var_name: str) -> str | None:
    return (os.environ.get(var_name) or _FILE_CACHE.get(var_name)) or None


def get_pool(provider: str) -> list[str]:
    """Return the ordered list of usable keys for a provider: bare name first, then
    numbered suffixes _1.._9. De-duplicated, placeholders skipped."""
    provider = provider.lower()
    if provider not in _PROVIDER_PREFIX:
        raise KeyError(f"Unknown provider {provider!r}")
    pref = _PROVIDER_PREFIX[provider]
    candidates = [pref] + [f"{pref}_{i}" for i in range(1, 10)]
    seen, pool = set(), []
    for name in candidates:
        v = get_raw(name)
        if _usable(v) and v not in seen:
            seen.add(v)
            pool.append(v)
    return pool


def get_key(provider: str) -> str:
    pool = get_pool(provider)
    if not pool:
        raise RuntimeError(
            f"No usable API key for provider {provider!r}. Expected "
            f"{_PROVIDER_PREFIX[provider.lower()]}(_1/_2/_3) in {_KEYS_FILE} or the env.")
    return pool[0]


def get_base_url(provider: str) -> str | None:
    if provider.lower() == "anthropic":
        return get_raw("ANTHROPIC_BASE_URL")
    return None


if __name__ == "__main__":
    print(f"keys file: {_KEYS_FILE}  present={_KEYS_FILE.exists()}")
    for prov in ("openai", "gemini", "xai", "anthropic"):
        print(f"  {prov:10s}: {len(get_pool(prov))} usable key(s)")
