# Protocol v2 step 4: the single L2S11 test and the L1S11 sanity check

**Headline: no evidence of transfer to L2S11.** The frozen model's L2S11 MAE is 0.0374. By the
predeclared rule it beats log-cycle OLS (0.0946) and the training-mean Dummy (0.1015), but only
because those controls carry Layup 1's higher target level. A post hoc predict-zero baseline has
MAE 0.0362, slightly better than the frozen model. The predeclared comparison and the zero
baseline must always be reported together.

**Mechanism.** Path 1→7 barely responds (likely crosstalk). The multi-path features change
strongly, but on specimen-specific scales. Simple reference-normalised amplitude features do not
transfer between specimens; that is the feasibility finding.

Produced once by `scripts/protocol_v2_test.py` at commit `52169ab` (clean tree, recorded in
`receipt.json`). The frozen model was LinearRegression on `single_path_1_7`
(`../selection.json`), refitted on the 25 pooled L1S11 + L1S12 checkpoints. Log-cycle OLS and the
training-mean Dummy were scored in the same run as fixed, non-selectable controls. Predictions were
written to `predictions_before_labels.csv` (hash in `predictions_before_labels.sha256.json`)
before any L2S11 label was read. Nothing was rerun or changed after scoring.

**Disclosure (smoke test).** Before this run, the script was smoke-tested on a scratch copy, with L1S12 standing
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

## Post hoc diagnostic: the L1S11 jump at 177k cycles (`../post_hoc_step4/logbook_L1S11.json`)

This was computed after the sanity check, at Sans's request. **The C1 fail stands.**

- **Logbook.** The L1S11 logbook (`Layup1/L1_S11_F/L1S11.xlsx`) records no re-mounting, settings,
  cabling or load change at 175k–177k cycles. The only remark from 100k cycles on is a strain-gauge
  note at 227k ("ch2: 0deg, balance high").
- **The sequence suggests handling.** An extra 177,309-cycle entry has only Clamped and Traction
  Free recordings. At 177,000 the order is Traction Free, then Clamped, then Loaded. That is the
  reverse of the usual Loaded-first order after cycling, which is consistent with the coupon having
  been out of the machine. No remark confirms it.
- **Logged dates are unreliable.** The timestamp goes backwards in 4 places (for example, the
  177,000- and 227,000-cycle rows are dated 14–15 July 2011, after 150,000 cycles on 19–20 July).
  The date column therefore cannot establish acquisition chronology here.
- **Every path rises together.** From 175k to 177k, the RMS ratio rises on all 36 paths
  (median ×1.33, minimum ×1.09; ×1.29 on path 1→7). The 1→7 excitation (actuator) signal stays at
  about 220.8 RMS throughout. A simultaneous rise on every path with unchanged excitation is more
  consistent with a global coupling or mounting change than with damage. This is an
  interpretation, not a confirmed cause.
- **Side finding.** Because of the backward timestamps, the recorded repeat-sensitivity first/last
  ordering may be reversed for the L1S11 80,000-cycle checkpoint, where `L1S11_80000_1_2.mat` is
  dated before `L1S11_80000_1_1.mat`. That historical result is unchanged and flagged for review.

## Prediction hash before labels (CRLF/LF)

`predictions_before_labels.sha256.json` holds the SHA-256 of the file exactly as written on Windows,
with CRLF line endings: `4ac9647b…d8a5ab`. The repository's `.gitattributes` stores CSV files with
LF line endings, so the copy in git, and in any fresh clone, has different bytes and hash. The
file was not regenerated. `predictions_before_labels.sha256_lf_normalised.json` records the hash
with every CRLF replaced by LF, `9cc12f55…fda949`, which equals the committed blob. Use that hash
to check a fresh clone. The content is identical; only line endings differ.

## Recommendations

- **Isolate the transmitted wave.** Use features such as S0-mode windowing, time of flight or
  ΔPSD as in Saxena et al. (2011). Any timing feature must use the corrected sampling rate.
- **Add labelled specimens.**
- **Calibrate per specimen.**

## Lesson for methods and the AI reflection

A "no damage" (predict-zero) baseline should have been predeclared alongside the training-mean
Dummy. Without it, beating the controls looked like transfer, when the controls were simply
biased towards Layup 1's target level.

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
