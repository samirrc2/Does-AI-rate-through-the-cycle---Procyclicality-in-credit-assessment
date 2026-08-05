# Reproducible environment for P5 — "Do LLMs Rate Through the Cycle?"
#
# This image reproduces the ANALYSIS ($0, offline, deterministic) that regenerates
# claims.json, the tables and figures from the FROZEN captures in data/. It does NOT
# perform live capture (that needs vendor API keys and is intentionally excluded from
# the reproducible run). Versions are pinned to the environment that produced the
# committed results (Python 3.12; numpy 2.2.6; scipy 1.15.3; pydantic 2.13.4;
# PyYAML 6.0.3).
FROM python:3.12-slim

ARG DEBIAN_FRONTEND=noninteractive

# Core analysis dependencies (offline reproduction). The vendor SDKs (openai,
# google-genai) are only needed for live capture and are deliberately omitted here.
RUN pip install -U --no-cache-dir \
    numpy==2.2.6 \
    scipy==1.15.3 \
    pydantic==2.13.4 \
    PyYAML==6.0.3 \
    matplotlib==3.10.0

WORKDIR /repro
COPY . /repro

# Default reproducible run: regenerate analysis from frozen data and verify it is
# byte-identical to the committed claims.json.
CMD ["bash", "reproduce.sh"]
