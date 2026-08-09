"""Unit tests for claims.json canonical serialization.

Run from repo root:
  python -m unittest tests.test_canonicalize -v
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))
import canonicalize as CAN  # noqa: E402


class TestDumpsClaims(unittest.TestCase):
    def test_same_dict_same_bytes_twice(self):
        payload = {
            "b": 1,
            "a": {"z": 0.1 + 0.2, "y": [1.0 / 3.0, -0.4295]},
            "flag": True,
            "n": None,
            "k": 7,
        }
        once = CAN.dumps_claims(payload)
        twice = CAN.dumps_claims(payload)
        self.assertEqual(once, twice)
        self.assertTrue(once.endswith("\n"))
        # Round-trip parseable; keys sorted at top level
        parsed = json.loads(once)
        self.assertEqual(list(parsed.keys()), ["a", "b", "flag", "k", "n"])

    def test_ulp_noise_collapses_to_identical_bytes(self):
        # Simulate Mac vs Linux ULP drift on the same scientific value
        a = {"x": 4.913046644194434}
        b = {"x": 4.91304664419444}
        self.assertNotEqual(a["x"], b["x"])
        self.assertEqual(CAN.dumps_claims(a), CAN.dumps_claims(b))
        self.assertEqual(CAN.quantize(a["x"]), CAN.quantize(b["x"]))

    def test_fixed_width_decimals(self):
        text = CAN.dumps_claims({"v": 0.4295})
        self.assertIn("0.429500000000", text)

    def test_rejects_nonfinite(self):
        with self.assertRaises(ValueError):
            CAN.dumps_claims({"bad": math.nan})


if __name__ == "__main__":
    unittest.main()
