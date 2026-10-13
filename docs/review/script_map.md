# Script map

Every maintained module in `scripts/`, in workflow order. "Data" means the raw NASA download passed
as `--data-root`. All commands run with the project venv interpreter (see README). Default outputs
under `results/rebuilt/` are git-ignored; recorded folders are refused as outputs unless noted.

## Shared modules

| Module | Purpose | Inputs | Outputs / used by |
|---|---|---|---|
| `common.py` | `require()` (survives `python -O`), SHA-256, CSV/JSON I/O, `scalar()`, `waveform_features()` (RMS, PTP), loading `config/experiment_v1.json` | none | imported by every workflow |
| `raw_loading.py` | Hash and load MAT files, optionally with bounded ordered four-thread prefetch | MAT paths | `(path, sha256, coupon)` tuples for the extractors |
| `protocol_v2.py` | Protocol v2 rules: per-file summary, joint label-blind eligibility, modal setting vector, checkpoints for both input sets, label-blind reference, label read-back, C1–C3 sanity criteria, selection rule | data, `config/protocol_v2.json` | imported by the v2 validation and test scripts |

## Historical (v1) workflows: results recorded before October 2026

| Script | Purpose | Inputs | Produces (recorded) |
|---|---|---|---|
| `exploratory_regression.py` | First experiment: screen L1S11/L1S12 recordings (path 1→7, 150 kHz, Loaded, 3.95–4.05 kips), checkpoint medians, label-blind reference, three OLS models, both directions | data, `config/experiment_v1.json` | `results/baseline/` (recorded from the original script); rebuilds to `results/rebuilt/` |
| `reproduce_results.py` | Refit the exported baseline features with centred QR; no raw data needed | `results/baseline/checkpoint_features.csv` | `results/reproduced/` |
| `repeat_sensitivity.py` | Rebuild the baseline, then refit with median / first / last repeats, ordered by logbook timestamps | data, logbooks, baseline | `results/repeat_sensitivity/` |
| `model_comparison.py` | Label-blind reference audit; six predeclared comparators (linear, tree, SVR, MLP × 5 seeds, log-cycle OLS, Dummy); timing; plots | data, `config/model_comparison.json`, baseline | `results/model_comparison/` |
| `feature_coverage.py` | Training convex-hull membership of evaluation checkpoints, with an independent triangle check | baseline features, comparison preprocessing audit | `results/model_comparison/coverage/` |
| `profile_raw_workflow.py` | cProfile of the raw extraction workflow | data | `results/model_comparison/raw_profile/` |
| `benchmark_raw_workflow.py` | Serial vs four-thread prefetch timings in fresh processes, with byte-equivalence of outputs | data | `results/model_comparison/raw_benchmark/` |

## Protocol v2 workflows (October 2026)

| Script | Purpose | Inputs | Produces |
|---|---|---|---|
| `audit_acquisition_v2.py` | Label-blind metadata and waveform audit (deletes the label field on load): path IDs, settings per pair, loads, early-peak pairs, geometry consistency | data (L1S11, L1S12, L2S11) | `results/protocol_v2_audit/` |
| `protocol_v2_validation.py` | **One-shot.** v2 validation on L1S11 ↔ L1S12 for both input sets; reproduction gate against v1; selection rule | data (L1 only) | `results/protocol_v2/validation/`, `results/protocol_v2/selection.json` |
| `protocol_v2_test.py` | **One-shot, guarded.** Refit the frozen model and controls on 25 pooled checkpoints; predict L2S11 label-free and save the predictions with a hash; read the labels; score; coverage; L1S11 sanity check | data, `selection.json` | `results/protocol_v2/test_L2S11/`, `results/protocol_v2/sanity_L1S11/` |
| `post_hoc_step4.py` | **Post hoc.** Predict-zero MAE, correlations, feature ranges | step-4 and validation outputs | `results/protocol_v2/post_hoc_step4/summary.json` |
| `post_hoc_logbook_l1s11.py` | **Post hoc.** Logbook rows from 100k cycles on, backward timestamps, per-path jump at 175k → 177k, excitation check | data (L1S11 logbook and MAT files), validation outputs | `results/protocol_v2/post_hoc_step4/logbook_L1S11.*` |

## Documentation and verification

| Script | Purpose | Inputs | Produces |
|---|---|---|---|
| `dataset_facts.py` | Label-to-strain-file links, strain-file variables, stored sampling rates, FFT check of the implied sampling rate at all 7 frequencies | data | `results/dataset_facts/facts.json` |
| `verify_reproduction.py` | Rerun baseline, repeat sensitivity, model comparison and coverage into scratch; classify every recorded file (identical / equal content / equal except environment / skipped / DIFFERENT) | data, recorded results | `results/reproduction_check/*.json` |
| `build_docs.py` | pdoc HTML for every module; local paths replaced by `<repository>` | `scripts/` | `docs/html/` |

## Tests (`tests/`, 66 tests)

| File | Tests | Covers |
|---|---:|---|
| `test_extraction.py` | 26 | sine RMS/PTP, `scalar()`, each eligibility rule, label-blind reference, missing labels, conflicting labels, integrity checks, `require()` under `-O`, frozen constants, refusal to overwrite recorded folders, import without side effects |
| `test_protocol_v2.py` | 17 | v2 eligibility rules, label isolation, per-pair normalisation and median, invariance to relabelling pairs, selection rule and ties, label attachment, sanity criteria |
| `test_model_comparison.py` | 7 | specimen separation, training-only scalers, leakage perturbations, sklearn vs recorded OLS, label-blind reference, saved metrics recomputed |
| `test_repeat_sensitivity.py` | 8 | timestamp ordering and fallback, frozen membership/targets/references, leakage, saved provenance |
| `test_reproduction.py` | 4 | recorded baseline metrics and predictions, leakage, duplicate rejection |
| `test_feature_coverage.py` | 4 | hull boundary cases, training-only scaler, duplicates, saved counts |

## Not part of the maintained pipeline

- **`archive/`.** Earlier exploratory scripts (walkthrough, checkpoint comparisons, the original
  extractor). These are kept for history; their conventions differ.
- **`data/audit_stiffness/` and `data/pzt_feasibility/`.** Tracked since the initial commit. They
  hold the original label audit and a feasibility notebook, with vendored `pypdf`. They have not
  been reviewed for portability. See `confidence_and_risks.md`, item R1, for a data-redistribution
  concern.
