# Environment

The reproducible run regenerates the **analysis** ($0, offline, deterministic) from
the frozen captures in `data/`. It does **not** perform live model capture — that
requires vendor API keys and is intentionally excluded from the reproducible run.

## Pinned versions (produced the committed results)

| Package | Version |
|---|---|
| Python | 3.12 |
| numpy | 2.2.6 |
| scipy | 1.15.3 |
| pydantic | 2.13.4 |
| PyYAML | 6.0.3 |
| matplotlib | 3.10.0 (figures only) |

## Docker (self-contained)

```bash
docker build -t p5-repro -f environment/Dockerfile .
docker run --rm p5-repro            # runs reproduce.sh: regenerate + byte-identical check
```

## Local (Python >= 3.10)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # analysis needs: pydantic, PyYAML, numpy, scipy
bash reproduce.sh                    # regenerate analysis + verify byte-identical
```

Live capture (NOT part of reproduction) additionally needs `openai` and
`google-genai` and API keys in `../API Keys/keys.env.txt`; see `RUNBOOK.md`.
