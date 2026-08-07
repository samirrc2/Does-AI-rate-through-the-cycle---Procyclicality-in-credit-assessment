"""Freeze the pre-registration: write PREREGISTRATION.freeze.txt with the SHA-256 of
PREREGISTRATION.md (+ config/firms hashes) so the confirmatory (full) run is pinned to
an exact, timestamped contract. Re-run any time you intentionally revise the pre-reg;
the freeze records the bytes that were in force.

  python3 freeze_prereg.py
"""
from __future__ import annotations
import hashlib, sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE / "config"))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    prereg = _HERE / "PREREGISTRATION.md"
    if not prereg.exists():
        print("PREREGISTRATION.md not found"); return 2
    digest = sha(prereg)
    try:
        import loader as C
        cfg = C.load_all()
        config_hash = cfg.config_hash()
    except Exception as e:
        config_hash = f"(unavailable: {e})"
    firms_manifest = _HERE / "manifest" / "firms_manifest.json"
    firms_hash = sha(firms_manifest) if firms_manifest.exists() else "(none)"
    ts = datetime.now(timezone.utc).isoformat()
    body = (
        "PREREGISTRATION FREEZE — P5 (Does AI rate through the cycle?)\n"
        f"frozen_utc         : {ts}\n"
        f"PREREGISTRATION.md : sha256 {digest}\n"
        f"config_hash        : {config_hash}\n"
        f"firms_manifest.json: sha256 {firms_hash}\n"
        "\n"
        "Status: frozen AFTER the exploratory/gating pilot PASS, BEFORE the\n"
        "confirmatory FULL run. The pilot validated the design and measurement; the\n"
        "full run (gpt-4o + Grok + 80 firms) is the confirmatory test against this\n"
        "frozen contract. Any post-freeze change is logged in\n"
        "PREREGISTRATION_AMENDMENTS.md with a new freeze.\n"
        "\n"
        "Verify:  shasum -a 256 PREREGISTRATION.md   # must equal the sha256 above\n"
    )
    (_HERE / "PREREGISTRATION.freeze.txt").write_text(body)
    print(body)
    print("-> PREREGISTRATION.freeze.txt written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
