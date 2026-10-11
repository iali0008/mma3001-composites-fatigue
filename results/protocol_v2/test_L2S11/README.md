# Protocol v2 step 4: the single L2S11 test and the L1S11 sanity check

Produced once by `scripts/protocol_v2_test.py` at commit `52169ab` (clean tree, recorded in
`receipt.json`). The frozen model was LinearRegression on `single_path_1_7`
(`../selection.json`), refitted on the 25 pooled L1S11 + L1S12 checkpoints. Log-cycle OLS and the
training-mean Dummy were scored in the same run as fixed, non-selectable controls. Predictions were
written to `predictions_before_labels.csv` (hash in `predictions_before_labels.sha256.json`)
before any L2S11 label was read. Nothing was rerun or changed after scoring.

**Disclosure.** Before this run, the script was smoke-tested on a scratch copy, with L1S12 standing
in for L2S11 and output to a temporary folder. The sanity check does not depend on L2S11, so that
smoke run had already computed its outcome (C1 fail). The official run recomputed it identically.
No L2S11 file was read before the official run.

## Predeclared results (from `result.json`, `metrics.csv`, `../sanity_L1S11/result.json`)

- **Setup as declared.** The reference is cycle 3 (`L2S11_3_1_1.mat`, `L2S11_3_1_2.mat`). Eight
  checkpoints are scored: 10, 1,000, 10,000 and 20,000–60,000 cycles. The −0.012213572 cycle-1
  label is reported and was not scored.

| Model | Role | L2S11 MAE | RMSE | R² | Mean residual |
|---|---|---:|---:|---:|---:|
| LinearRegression, single path 1→7 | frozen model | **0.0374** | 0.0442 | −2.27 | −0.0374 |
| log-cycle OLS | control | 0.0946 | 0.1014 | −16.20 | +0.0946 |
| training-mean Dummy | control | 0.1015 | 0.1044 | −17.25 | +0.1015 |

- **Against the controls.** By the predeclared statement rule, the frozen model beats both
  controls on L2S11 MAE.
- **Bias.** The frozen predictions span only −0.009 to 0.007. Its mean residual equals −MAE, so
  every prediction is below its observation.
- **Coverage.** All 8 scored L2S11 checkpoints lie outside the pooled training hull, and so do the
  8 unlabelled ones. The result is the same at tolerances 1e-12, 1e-10 and 1e-8 (`coverage.csv`,
  `coverage_L2S11.png`).
- **Sanity check on L1S11, 125k–227k cycles: FAIL.**
  - **C1 fails.** The mean late prediction (0.083) is below the prediction at 100,000 cycles (0.114).
  - **C2 and C3 pass.** Every late prediction lies within 0.018–0.128.
  - **The drop.** Predictions are 0.123, 0.124 and 0.128 at 125k, 150k and 175k cycles, then fall to
    0.018 and 0.020 at 177k and 227k.

## Post hoc observations (computed after scoring; `../post_hoc_step4/summary.json`)

These numbers were not predeclared and must not be presented as such.

- **No better than predicting zero.** A constant prediction of zero would have L2S11 MAE 0.0362,
  slightly lower than the frozen model's 0.0374. L2S11 labels are small (0.009–0.084, mean 0.036),
  and the controls carry the higher Layup 1 target level, so beating them does not show skill.
- **Predictions barely track the labels.** The Spearman correlation between frozen predictions and
  L2S11 labels is 0.19 over 8 checkpoints.
- **The selected input does not move on L2S11.** Path 1→7 relative RMS stays within 0.985–1.018
  and relative PTP within 1.001–1.015 across the scored L2S11 checkpoints. The fitted model maps
  ratios near 1 to an index near 0. This is consistent with the audit finding that 1→7 is
  dominated by a fixed early, crosstalk-like burst.
- **Why the sanity check failed.** At 177k and 227k cycles, the L1S11 path 1→7 ratios jump to
  about 1.056 (RMS) and 1.105 (PTP). Both are beyond the pooled training ranges (RMS up to 0.982,
  PTP up to 1.060). The jump happens within 2,000 cycles (175k → 177k), which suggests an
  acquisition change rather than sudden stiffness recovery. That is an interpretation; it has not
  been checked against the logbook.

## Notes for the report (from Sans's step 4 instruction)

- **Multi-path ratios fall much further than path 1→7.** Non-reference multi-path PTP ratios span
  0.318–0.961 across the two development specimens. Path 1→7 PTP ratios span only 0.833–1.060.
  This is consistent with 1→7 being crosstalk-dominated.
- **The fall does not transfer.** The size of the multi-path fall differs between specimens
  (L1S11 0.417–0.961; L1S12 0.318–0.606), so it transfers poorly.
- **Main limitation.** The specimen-specific mapping from amplitude to damage is the main
  limitation, not the choice of feature.

## Files

`receipt.json`, `predictions_before_labels.csv` (+ `.sha256.json`), `checkpoint_features.csv`
(all eligible L2S11 checkpoints, both input sets), `recordings.csv`, `predictions.csv`,
`metrics.csv`, `result.json`, `coverage.csv`, `coverage_L2S11.png`, `predictions_L2S11.png`,
`source_hashes.json`; sanity check in `../sanity_L1S11/result.json`.
