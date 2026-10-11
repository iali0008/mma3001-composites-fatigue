# Protocol v2: multi-path inputs, model selection and the L2S11 held-out test

Written 2026-10-11, **before any v2 score was computed**. The machine-readable settings are in
`config/protocol_v2.json`; where the two differ, the JSON governs and the difference is a bug to
report. Protocol v1 (`docs/model_comparison_protocol.md`, `config/model_comparison.json`) and all
recorded results stay frozen. Any change after a v2 score has been seen is protocol v3 and must be
disclosed as such.

## 1. What was looked at before writing this

Only acquisition metadata and label-free waveform checks. The audit script
`scripts/audit_acquisition_v2.py` deletes the stiffness-label field from each file immediately
after loading it, and computes no model or score. Its outputs are in
`results/protocol_v2_audit/` (`summary.json`, `recordings.csv`, `pair_settings.csv`,
`source_hashes.json`). Every number in this section comes from those files.

Already known before v2, and therefore not a new look: the v1 scores, the post hoc observation that
log-transformed features score better on L1S11/L1S12 (not adopted), and the L2S11 label table seen
in the earlier audit (`archive/audit/`). No L2S11 model prediction has ever been made.

### 1.1 Path identifiers across specimens

- **Slot order.** The Technical Report (section 3.2, PDF p. 6) lists L1S11 among the coupons whose
  acquisition path convention needed `CHANGEPATH.m`. Appendix A.2 (PDF pp. 11–12, lines 43–75)
  shows that script moves each signal *together with* its actuator, sensor and frequency
  definition into the master slot order. The stored IDs therefore travel with the signals.
- **Audit result.** All 382 PZT files of L1S11 (145), L1S12 (109) and L2S11 (128) have the same
  252-slot order signature, and each holds the full 6 × 6 actuator–sensor grid exactly once at
  150 kHz. The 150 kHz pair-ID sets are identical across the three specimens.
- **Physical consistency.** Whether ID *k* is the same physical position on every coupon cannot be
  proven from the files. A gain-independent check supports it: the sample index of each pair's
  receiver envelope peak at the earliest Loaded checkpoint correlates positively between
  specimens (Spearman 0.61 L1S11–L1S12, 0.76 L1S11–L2S11, 0.40 L1S12–L2S11). Raw amplitude
  patterns do not agree well (Spearman −0.04 to 0.32), but per-pair gain settings differ between
  specimens, so raw amplitudes are not comparable across specimens.
- **Consequence for design.** The multi-path aggregation below (median over all 36 per-pair
  ratios) gives the same value under any relabelling of pairs. It needs IDs and settings to be
  consistent over time *within* a specimen, which the audit confirms, not across specimens. The
  single-path 1→7 baseline does assume cross-specimen consistency, as v1 did.

### 1.2 Sensor layout

Technical Report Figure 1(a) (PDF p. 2) places actuators 6…1 left to right along one SMART Layer
strip and sensors 7…12 left to right along the other, with the notched gauge section between them.
All 36 paths therefore cross the gauge section. This justifies using all 36 pairs instead of a
hand-picked notch-crossing subset, which would add a geometric judgement and would rely on the
cross-specimen ID consistency that cannot be proven.

### 1.3 Acquisition settings

- **Per-pair settings.** Gain and amplitude are set per pair, not per specimen. L1S11 uses
  amplitude 65 with gains from 22 to 43; L1S12 uses amplitudes 30–50 with gains 25–35; L2S11 uses
  amplitude 50 with gains 30–35.
- **Constancy over time.** No pair in L1S11 or L1S12 ever changes setting. In L2S11, 9 pairs use a
  different gain in 12 files, all at cycle 0 or cycle 1. Pair 1→7 is never affected and is 35/50 in
  L2S11, the same as L1S12.
- **Sampling and length.** Every file stores a sampling rate of 1,200,000 and 2,000-sample signals.
  The stored rate is a constant written by the curators' conversion script (Appendix A, line 102);
  the 150 kHz excitation implies about 12 MHz. RMS and peak-to-peak do not depend on the rate.
- **Signals.** Every 150 kHz actuator and receiver signal in all three specimens is finite and
  nonconstant.

### 1.4 L2S11 load and condition

- **Ramps at cycles 1 and 2.** L2S11's Loaded recordings at cycle 1 step from 0.509 to 4.503 kips
  and those at cycle 2 from 0.5 to 8.003 kips. These are static load ramps.
- **Fatigue mean load.** From cycle 3 to 207,000, all Loaded recordings lie between 4.571 and
  4.588 kips (median 4.576), above Layup 1's 3.95–4.05 window.
- **Window.** The L2S11 window is 4.53–4.63 kips, the same ±0.05 kip half-width as Layup 1. It
  admits 32 recordings at 17 checkpoints, from cycle 3 to 207,000, and excludes every ramp
  recording. It also excludes `L2S11_10_2_2.mat`, which has condition text "loaded" but load
  −0.001 kips and a clamped boundary-condition code in its filename.
- **Condition text.** Condition text varies in case ("Loaded", "loaded"), so it is compared after
  stripping whitespace and case-folding, as in v1.

### 1.5 An observation that does not change the design

At the earliest Loaded checkpoint, several pairs have their envelope maximum near sample 292,
about 100 samples after the actuator peak, regardless of path length: 9 pairs in L1S11, 5 in L1S12,
15 in L2S11 (threshold < 400 samples). The fixed early position suggests electrical crosstalk or
another early arrival rather than the transmitted wave; this is an interpretation, not a
confirmed mechanism. **Pair 1→7, the v1 baseline path, is one of them in all three specimens.**
Protocol v2 keeps the full 0–1,999 sample window for both input sets, so that the only difference
between them is path aggregation. A time-windowed variant is *not* part of v2; adding one would
require a protocol amendment before step 3.

## 2. Recording eligibility (label-blind, both input sets)

A recording is used only if all of these hold. Labels and label availability are never read.

| Rule | Value |
|---|---|
| Specimens | L1S11, L1S12 (development); L2S11 (held-out test). L1S18, L1S19 and all others unused. |
| Cycles | Strictly positive |
| Condition | `casefold(strip(condition)) == "loaded"` |
| Load | L1S11, L1S12: 3.95–4.05 kips; L2S11: 4.53–4.63 kips (inclusive) |
| Stored sampling rate | 1,200,000 (stored constant, not a measured rate) |
| Signal length | 2,000 samples, both channels |
| Baseline path | Actuator 1 → sensor 7 at 150 kHz, exactly once, gain/amplitude 33/65 (L1S11), 35/50 (L1S12), 35/50 (L2S11) |
| Multi-path grid | All 36 pairs (actuators 1–6 × sensors 7–12) at 150 kHz, each exactly once |
| Settings | The 36-pair (gain, amplitude) vector equals the specimen's modal vector over all its PZT files |
| Signals | Actuator and receiver signals finite and nonconstant for every used pair |

**Joint eligibility.** Both input sets use the same recordings, checkpoints and references. The
audit shows that L1S11 and L1S12 files all pass the grid and settings rules, so the v1 recording
set for those specimens is unchanged.

## 3. Reference checkpoint

The reference is the **earliest checkpoint with at least one eligible recording**, chosen in the
extraction itself without reading labels (code issue a). Its denominators are medians across its
eligible recordings: one per feature for the baseline, one per feature and pair for multi-path.
All denominators must be positive. The reference checkpoint never enters fitting, scaling or
scoring. It is a chronological anchor, not an undamaged state.

From the audit, the expected references are cycle 1 for L1S11 and L1S12 (as in v1) and **cycle 3
for L2S11**. Because the rule is label-blind, an unlabelled checkpoint can be the reference.

## 4. Input sets

Features use the full receiver window, samples 0–1,999, with the v1 formulas:

```text
RMS = sqrt(mean((x - mean(x))^2))        PTP = max(x) - min(x)
```

1. **`single_path_1_7` (baseline, v1).** Median over a checkpoint's eligible recordings of RMS and
   PTP for pair 1→7, divided by the reference medians: `relative_rms`, `relative_ptp`.
2. **`multi_path_36` (new).** For each of the 36 pairs: median over eligible recordings, divided by
   that pair's reference median. Then take the median over the 36 pair ratios:
   `mp_relative_rms`, `mp_relative_ptp`.

Per-pair normalisation cancels each pair's constant gain and amplitude setting under the same
multiplicative assumption as v1. The median over pairs is robust to a minority of atypical pairs
and does not depend on pair labels. Two inputs keep the model dimension identical to v1.

Not adopted: log-transformed features (found post hoc on v1 scores), time windows, per-pair
weighting or selection, extra frequencies. Paths, repeats and boundary conditions are never
treated as extra rows or labels.

## 5. Models

Same six comparators and settings as protocol v1, with no tuning: LinearRegression, depth-2
DecisionTreeRegressor, RBF SVR, three-unit tanh MLP (seeds 7, 23, 42, 71, 101), log-cycle OLS and
training-mean Dummy. Preprocessing is as in v1. Scalers sit inside the sklearn pipeline and are
fitted on training checkpoints only. SVR and MLP use a training-fitted target scaler, inverted
before scoring. Numerical libraries run on one thread. Exact settings are in the JSON.

## 6. Validation on L1S11 ↔ L1S12 (step 3)

- Train on all non-reference labelled checkpoints of one specimen, and evaluate on all
  non-reference labelled checkpoints of the other. Then reverse. The v1 counts are 13 for L1S11 and
  12 for L1S12. The missing L1S12 20,000-cycle label stays missing, and the 30,000-cycle jump stays
  in.
- MAE in published-index units is primary. Also report RMSE, R², mean residual, training metrics
  and per-checkpoint predictions. MLP is summarised by its five-seed median, with every seed
  reported.
- **Reproduction gate.** Before any multi-path score is reported, the `single_path_1_7` predictions
  must reproduce `results/model_comparison/predictions.csv` (rtol 1e-9, atol 1e-10). If they do not,
  stop and report.

## 7. Final-model selection rule (declared now)

- **Candidates.** 8 candidates: 4 model families (LinearRegression, DecisionTreeRegressor, SVR,
  MLP) × 2 input sets. Log-cycle OLS and Dummy are controls and cannot be selected.
- **Criterion.** Choose the candidate with the lowest **worst-direction validation MAE**:
  `max(MAE L1S11→L1S12, MAE L1S12→L1S11)`. MLP enters with its five-seed median MAE in each
  direction.
- **Ties.** Candidates within 0.0005 of the minimum are tied. Prefer the simpler model in the order
  LinearRegression, DecisionTreeRegressor, SVR, MLP. If still tied, prefer `single_path_1_7`, which
  needs one path instead of 36.
- **Why worst-direction.** Each direction is one specimen-to-specimen transfer. A deployed model
  must transfer in whichever direction it meets, and v1 showed the two directions can rank models
  differently. The mean across directions is reported but not used.
- **Freeze.** The rule's output, the full candidate table and the commit hash are committed to
  `results/protocol_v2/selection.json` before L2S11 is processed. The selection is final even if
  it is unintuitive.

## 8. Frozen final model and the L2S11 test (step 4)

- **Training.** Refit the selected model and input set on all non-reference labelled checkpoints
  of L1S11 and L1S12 pooled (expected 25). Use equal checkpoint weights, unchanged hyperparameters,
  and each specimen normalised by its own reference. Pooling widens the training target range. Its
  configuration was validated only in single-specimen training, which is a stated limitation.
- **MLP.** If MLP is selected, fit all five seeds. Report each seed and the seed-median MAE, with
  no seed selection and no ensemble.
- **Scored set.** Every non-reference L2S11 checkpoint with an eligible recording and a finite
  published label.
- **Negative cycle-1 label.** The −0.012 value at cycle 1 cannot be scored, because no cycle-1
  recording is inside the load window. It is reported, never scored and never clipped.
- **Reference.** The expected L2S11 reference is cycle 3, excluded from scoring by the general
  rule.
- **Controls.** Log-cycle OLS and the training-mean Dummy, trained by the same pooled rule, are
  scored in the same single run as fixed reference points. They cannot replace the frozen model.
  The frozen model is described as beating a control only if its L2S11 MAE is lower.
- **Metrics.** MAE (primary), RMSE, R², mean residual and per-checkpoint predictions. Failure is
  recorded in full.
- **Coverage.** Report training-hull membership of L2S11 checkpoints in pooled-training-standardised
  coordinates of the selected input set, as in `results/model_comparison/coverage/`. This is
  descriptive only.
- **Once only.** The scoring script refuses to run if its receipt already exists or the git working
  tree is dirty, and records the commit hash.
- **Status.** L2S11 is cross-layup (Layup 2 at a 4.58 kip mean load versus Layup 1 at 4.0). It is
  described as held out from model development, not untouched. One specimen cannot establish
  cross-layup generalisation.

## 9. Unlabelled sanity check on L1S11 (step 4)

The sanity check applies the frozen final model to the L1S11 checkpoints after 100,000 cycles:
125,000, 150,000, 175,000, 177,000 and 227,000. These have no labels, so the check tests
plausibility, not accuracy. It passes only if all three criteria hold:

- **C1, not decreasing on average.** The mean prediction over the five late checkpoints is at
  least the model's prediction at the L1S11 100,000-cycle checkpoint.
- **C2, physical range.** Every late prediction lies within [−0.05, 1.0]. A normalised stiffness
  loss cannot exceed 1. The lower bound allows small negatives like the published −0.012.
- **C3, no extreme extrapolation.** Every late prediction lies within the pooled training-target
  range, widened by 50% of its width on each side.

Also reported, descriptively only: the least-squares slope of prediction against cycles over the
late checkpoints, and each late checkpoint's relative features against the training feature range.
L1S11 was a training specimen of the final model, so passing shows plausibility under continued
cycling, not transfer.

## 10. Halting and integrity

Stop and report, without changing rules, if any of these occurs:

- an integrity check fails;
- the reproduction gate fails;
- a specimen has no eligible checkpoint;
- a reference denominator is not positive;
- a reference differs from the audit expectation.

Integrity checks use `require()`, not `assert`. Raw NASA files are read-only and never committed.
New outputs go to `results/protocol_v2/`, and earlier results stay unchanged.

## Approval notes (2026-10-11, Sans)

These notes record the review decision. They do not change any frozen setting in this document or
in `config/protocol_v2.json`.

1. **Controls on L2S11.** Approved as written: log-cycle OLS and the training-mean Dummy are fixed,
   non-selectable reference points in the single L2S11 run. L2S11 stays frozen and separate. No
   code reads its labels before step 4, and it is scored exactly once, after the final model is
   frozen and committed.
2. **Time window.** No amendment; both input sets keep the full window. The path 1→7 crosstalk-like
   finding goes into the limitations and discussion. For interpretation only: PTP is set by the
   largest swing, so on crosstalk-dominated paths relative PTP mostly tracks the crosstalk. This
   may explain why v1 L1S11 PTP ratios stay near 1 and why PTP behaves inconsistently across
   specimens.
3. **Project brief.** The brief PDF is git-ignored, so the scoring guard's clean-tree check is not
   affected by it.
4. **L2S11 scored set.** Under these eligibility rules the test scores 8 checkpoints: 10, 1,000,
   10,000 and 20,000–60,000 cycles. Cycle 10 has a single eligible recording.
