# Project-brief checklist

The brief is `MMA3001_2026_Project_Brief.pdf` (git-ignored). Status key: **Met**, **Partial**
(exists but incomplete or needs the report), **Gap** (missing), **Pending** (planned step).

## Project selection and scope (brief pp. 2, 7)

| Requirement | Status | Where |
|---|---|---|
| Self-selected project approved by the teaching team before substantial work | **Unknown** | Not evidenced in the repo; `docs/progress.md` lists it as open. Confirm and record. |
| Engineering problem relevant to mechanical/aerospace engineering | Met | README "Engineering problem"; `archive/audit/ASSESSMENT.md` |
| At least one numerical/ML technique taught in the unit | Met | OLS (QR), decision tree, RBF SVR, MLP, convex hull, FFT: `scripts/model_comparison.py`, `protocol_v2*.py`, `feature_coverage.py`, `dataset_facts.py` |
| Clearly defined inputs and outputs; data ownership/licensing | Met | README; `docs/dataset.md` §1, §4 |
| Credible alternatives can be compared | Met | Six comparators, two input sets, controls |

## Project requirements (brief pp. 4–6)

| Requirement | Status | Where / gap |
|---|---|---|
| 1. Engineering context, problem, why it matters, intended use, scope limits | Partial | README "Engineering problem"; full narrative pending in report (step 7) |
| 2. Inputs/outputs: format, units, domain, meaning, intended use | Met | README; `docs/dataset.md` (units, sampling rate, label definition) |
| 2. Handling of invalid/missing/unsupported inputs | Met | eligibility rules (`docs/protocol_v2.md` §2, `docs/methodology.md`), exclusion counts and reasons in results, tests |
| 2. Function-level inputs/outputs via docstrings | Met | NumPy docstrings on all 105 functions; `docs/html/` |
| 3. Method: how it works, why selected, assumptions, settings, implementation, limitations | Partial | `docs/methodology.md`, `docs/model_comparison_protocol.md`, `docs/protocol_v2.md`, configs; synthesis pending in report |
| 4. Alternatives/baselines compared | Met | v1 comparison, v2 input sets, controls; post hoc predict-zero |
| 4. Comparison on accuracy, robustness, time, interpretability | Partial | accuracy and time in results; robustness (repeat sensitivity); interpretability discussion pending in report; **memory not measured** |
| 5. Validation method justified; metrics; what it cannot establish | Met | specimen-held-out design, protocols, results READMEs |
| 5. Whether validation influenced model selection | Met | `docs/protocol_v2.md` §7; disclosure that single-path scores were known (`results/protocol_v2/validation/README.md`) |
| 5. Withheld test data | Met | L2S11 scored once (`results/protocol_v2/test_L2S11/`) |
| 5. Physical constraints / manual criteria | Met | L1S11 sanity check C1–C3 (failed, recorded) |
| 6. Profilers and timing routines | Met | `results/model_comparison/raw_profile/`, `raw_benchmark/`, model timing CSVs |
| 6. Baseline vs improved solution compared and justified | Met | serial vs prefetch, 12.769 s → 7.771 s, outputs byte-identical (`raw_benchmark/summary.json`) |
| 6. Arithmetic intensity / FLOP estimates "where appropriate" | **Gap** | Not done. A short FLOP estimate for OLS/QR and feature extraction would answer it, or justify why I/O-bound MAT parsing makes it uninformative. |
| 6. Memory requirements | **Gap** | Not measured (stated in progress log) |
| 7. AI use and reflection | **Pending** | Step 8; README has a pointer only; `docs/ai-use.md` does not exist |

## Evidence required (brief pp. 2, 7)

| Item | Status | Where |
|---|---|---|
| Model development | Met | v1, v1 comparison, v2 |
| Validation and verification | Met | protocols; tests; reproduction checks; independent OLS, hull and score recalculation |
| Sensitivity analysis | Partial | repeat-selection sensitivity (`results/repeat_sensitivity/`). The reference ±5% sensitivity and repeat-spread figures in CLAUDE.md fact 4 have **no script output in the repo**: reproduce them or leave them out of the report. |
| Interpretation in engineering context | Partial | results READMEs; report pending |
| Reproducible workflow with version control (GitHub) | Partial | Local git with branches and descriptive commits; **all October work is on unpushed branches**; `main` still at `7d282b2` |
| Appropriate computational tools | Met | Python, NumPy/SciPy/scikit-learn, pytest, pdoc |

## Deliverables (brief p. 8)

| Deliverable | Status | Where / gap |
|---|---|---|
| Written document, 5–10 pages, with sections 1–8 and references | **Pending** | Step 7 (`docs/report/`) |
| GitHub: README | Met | `README.md` |
| GitHub: HTML documentation (pdoc) | Met | `docs/html/`, `scripts/build_docs.py` |
| GitHub: licensing agreement | Met | `LICENSE` (MIT, code and docs only) |
| GitHub: functional main branch | **Gap** | Work is on `protocol-v2` / `code-fixes`; merge to `main` after review |
| Inline comments and docstrings | Met | all modules |
| Test functions and test report | Met | `tests/` (66); `results/test_report/` |
| Zipped clone of the repository to Moodle | Pending | After merge; note the clone excludes the raw data by design |
| Presentation (5 min) and Q&A | Pending | Step 9 |

## Rubric-specific notes (brief pp. 10–15)

- **Branching and commits.** Branches `protocol-v2` and `code-fixes`, each commit with a reason.
  This holds once pushed.
- **Docs in sync with code.** `docs/html` was regenerated from the final code. The rebuilt HTML
  differs only in a cosmetic show-value toggle that depends on checkout path length.
- **Failure modes and unsupported inputs.** These are documented, but the report must state them
  explicitly.
- **AI reflection.** The top band needs evidence that you drove the process: the protocol
  decisions, the reviews, and the corrections you made, such as the predict-zero framing and the
  logbook check.
