# Referee-response log — round on "Does AI rate through the cycle?"

Point-by-point record of the reviewer critique and what was changed. All numbers are
claims-gated to `claims.json`; the manuscript is the CAS LaTeX in `paper/latex/`.

| # | Reviewer point | What we did |
|---|---|---|
| **1** | No external benchmark — is 0.43 large? | Reframed via the **joint TTC condition** (promoted to §1): the rating should be sticky while the point-in-time PD moves; the material benchmark is the **capital consequence** (new §4.4), which we quantify. Makes the missing agency data far less conspicuous without conceding ground. |
| **2** | Never compute the capital effect | New **§4.4 "Capital consequences"**: anchor through the **rating** (map notch → stylised agency default rate → Basel IRB corporate formula), not the disclaimed verbalised PD. Pooled capital swing **1.87 pp of exposure** (95% CI [1.73, 2.00]); 3.48 pp for the most sensitive model. Raw-PD variant (2.92 pp) reported as robustness, agreeing in direction. Stated as a **stylised proxy** (LGD 0.45, M 2.5, no SME adj.). `analysis/capital.py`. |
| — | Convexity welds §4.2→§4.3 | Added: capital is convex in PD, so the downside capital increase (1.55 pp) is ~5× the upside (0.32 pp) — wider than the notch asymmetry, so a symmetric rater would swing capital less. |
| **3** | Anchoring finding has no inference | Defined the **joint TTC null** (rating slope ≈ 0 **and** PD slope ≈ point-in-time); measured PD on the **log-odds** scale; bootstrapped **PD retention = 0.38 (95% CI [0.35, 0.40])**, far below 1; reported the **directional split** (downside 0.35, upside 0.38). Kept the calibration caveat but noted within-firm relative use. |
| **4** | "Five frontier models" overclaim; "Gemini 3.5 Flash" unverified | Reworded to **"five production-tier models (two families, two capability tiers)"**; dropped "flagship". Relabelled Gemini by API **alias** (`gemini-flash-latest`, `gemini-flash-lite-latest`) + noted served snapshot/**system_fingerprint** logged per call + run month (July 2026). Removed invented version numbers everywhere (text, tables, figures). |
| **5** | Doesn't cite Hens & Nordlie (FRL's closest prior) | Added as an **active contrast** in §2: they find LLM risk profiles match bankers in level but explain poorly; we find LLMs *move* the level with context a TTC rater should ignore. Also added Fieberg et al. (2025) and Kang & Liu (2023, hallucination). |
| **6** | Placeholders (BIS, Graham, Zenodo DOI, affiliation, stray image) | **Web-verified** and inserted real cites: BIS WP 1194 (Aldasoro, Gambacorta, Korinek, Shreeti & Stein, 2024); Graham, Harvey & Jha, arXiv:2606.13812. Replaced the fake Zenodo DOI with the **live GitHub URL** (+ "Zenodo archive accompanies the published version"). Fixed the affiliation trailing comma. Generated the missing **`thumbnails/cas-email.jpeg`** so the email icon renders (was the stray box). |
| **7** | Table 3 text overclaims probit "agrees in magnitude" | Corrected to "agrees in sign throughout and is of comparable magnitude, **though the two estimators do not perfectly preserve the cross-model rank order**." |
| **8** | Prompts not shown | New **Appendix B (Prompts)** printing the 4 framings + 5 macro + 5 placebo blocks **verbatim**, extracted **programmatically** from `agent.py` (`analysis/make_prompts.py`, wired into `build.sh`) so it cannot differ from the executed instrument. (FRL excludes appendices from the word count — confirmed in the guide.) |
| **9** | Scope validity (deployment may omit a macro block) | Added a sentence: realistic pipelines carry macro context (RAG over news/filings, analyst preambles, market-data conditioning), so the sensitivity we measure is the exposure a deployment inherits. |
| **m1** | "first controlled test" ×4 | Reduced to one assertive use; reworded the others. |
| **m2** | Broken fi/fl ligatures + Type-3 fonts | Added `fontenc[T1]` + `lmodern` + `microtype`; set matplotlib `pdf.fonttype=42`. Verified with `pdffonts`: **0 Type-3 fonts**, all Type-1/TrueType; "fixed"/"significant"/"confidence" now extract intact. |

## Status
Main text **2,025 words** (< 2,500); **31 verified references** (11 of them Finance Research
Letters; 0 placeholders); 0 undefined refs; 0 Type-3 fonts; claims-gate PASS; reproduce.sh --quick PASS.

## Still needs the authors
- **#1 quantitative agency benchmark** — reframed and quantified via capital (§4.4); a *direct*
  agency-slope comparison would need agency ratings on matched fundamentals (future work).
- **Corresponding-author postal address** (Editorial Manager field; not in the manuscript body).
- Mint the **Zenodo DOI** at release and swap the GitHub URL for it.
