"""Self-test for the hard spend wall — proves the ledger REFUSES to overspend.
Uses REAL prices on synthetic calls (the mock path bills $0, so the cap must be
verified separately). Exercises: (1) pre-flight refusal when projected worst-case
would cross the cap; (2) mid-flight reserve() returning False the instant the next
call would cross (cap - margin); (3) persistence round-trip. Exit 0 on pass.

  python capture/ledger_selftest.py
"""
from __future__ import annotations
import sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ledger as L  # noqa: E402


def main() -> int:
    tmp = Path(tempfile.mkdtemp()) / "ledger_test.json"
    cap, margin = 1.00, 0.05
    # a "model" that costs $0.10 worst-case per call
    price_in, price_out, in_tok, out_tok = 100_000.0, 0.0, 1, 0   # 1 tok * $100k/1M = $0.10
    wc = L.worst_case_cost({"price_in": price_in, "price_out": price_out,
                            "max_tokens": 1}, est_in=1)
    assert abs(wc - 0.10) < 1e-9, wc

    led = L.Ledger.load(tmp, cap=cap, margin=margin)

    # (1) pre-flight: 20 calls * $0.10 = $2.00 worst-case >> $1 cap → must refuse
    ok, proj = led.preflight_ok(wc * 20)
    assert not ok and abs(proj - 2.0) < 1e-9, (ok, proj)
    # a fitting projection is accepted
    ok, proj = led.preflight_ok(wc * 5)
    assert ok, (ok, proj)

    # (2) mid-flight: reserve+commit until the wall bites. cap-margin = $0.95, wc=$0.10
    #     → at most floor(0.95/0.10) = 9 reservations before the 10th is refused.
    granted = 0
    for _ in range(50):
        if not led.reserve(wc):
            break
        led.commit("m", price_in, price_out, in_tok, out_tok, wc)
        granted += 1
    assert granted == 9, f"expected 9 committed before wall, got {granted}"
    assert not led.reserve(wc), "reserve should refuse once no worst-case headroom remains"
    assert led.cum_usd <= (cap - margin) + 1e-9, led.cum_usd   # never crossed the wall
    assert led.remaining() < wc, "no room for another worst-case call"

    # (3) persistence round-trip
    led.save()
    led2 = L.Ledger.load(tmp, cap=cap, margin=margin)
    assert abs(led2.cum_usd - led.cum_usd) < 1e-9, (led2.cum_usd, led.cum_usd)
    assert led2.per_model["m"]["calls"] == 9

    print(f"[ledger-selftest] PASS: preflight refuses over-budget; mid-flight wall "
          f"stops at ${led.cum_usd:.2f} (cap ${cap:.2f}, margin ${margin:.2f}); "
          f"9 calls committed, 10th refused; persistence OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
