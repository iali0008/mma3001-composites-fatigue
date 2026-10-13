# First experiment: methodology

## Scope

Estimate the existing stiffness-degradation index at the time of an ultrasonic recording. This is contemporaneous estimation; no future-cycle information is used as a forecast target. The labels are those in `coupon.straingage_data.stiffness_degradation`, not independently validated modulus loss.

## Selection

Select paths by stored actuator, receiver and frequency fields, not position in an array. The physical configuration must still be interpreted using the supplied experiment documentation.

| Rule | Value |
|---|---|
| Specimens | L1S11, L1S12 |
| Path | Actuator 1 → receiver 7 |
| Nominal frequency | 150 kHz |
| Boundary condition | Loaded; whitespace/case normalised |
| Load | 3.95–4.05 kips inclusive |
| Cycles | Strictly positive |
| Target | Finite numeric scalar; missing/array placeholders excluded |
| L1S11 gain / excitation setting | 33 / 65 |
| L1S12 gain / excitation setting | 35 / 50 |
| Stored sampling rate | 1,200,000; units reported as Hz, physical timing unverified |
| Signal length | 2,000 samples for both channels |
| Feature window | Receiver samples 0–1,999 inclusive |

For these selected specimens all retained non-reference targets are positive. The general scalar check does not establish that every numeric zero in a different specimen is a valid target. All inspected selected signals were finite and nonconstant; this is not comprehensive quality control. The original pipeline flags signal issues and fails if usable checkpoint features/reference denominators are unavailable. It does not establish clipping thresholds.

**v1 screening is historical (finding R7).** v1 records `signal_*_nonfinite` and `signal_*_constant` flags for both channels but does not exclude on them. A recording with an all-NaN actuator, a constant sensor (features 0) or a nonfinite sensor (no features) remains `eligible`. Protocol v2 is stricter: it excludes any pair whose actuator or sensor signal has the wrong length, a nonfinite sample or zero range. The v1 behaviour is kept unchanged so the recorded baseline reproduces. It affects no recorded result: all 51 eligible v1 recordings in `results/baseline/recordings.csv` have all four flags false. `tests/test_extraction.py::HistoricalV1ScreeningTests` pins both facts.

## Features and reference

For a receiver sequence x with n samples:

```text
peak-to-peak = max(x) - min(x)
mean-centred RMS = sqrt(sum((x - mean(x))^2) / n)
```

Take each feature's median across eligible recordings from the same specimen and cycle. Require labels within each group to agree. Repeated recordings are not independent labels.

Divide each checkpoint feature by its specimen's feature at the earliest eligible checkpoint. Both references are at cycle 1: `L1S11_1_1_1.mat` and `L1S12_1_1_8.mat`. These are chronological references, not undamaged states. Reference targets do not enter the fit, error metrics or a target-offset calibration.

The historical extractor requires a populated target when building its reference checkpoint. The later model-comparison workflow corrects reference selection by independently screening acquisition/waveform criteria without reading targets; it verifies that the original references and denominators are unchanged before using the fixed baseline table. Label availability still governs fitting/scoring checkpoints, not the early-reference audit. See the model-comparison section below.

Ratios are dimensionless. A constant multiplicative amplitude factor cancels algebraically, but amplification nonlinearities, coupling changes, noise and different damage at reference can remain. Do not convert gain settings by dividing by 33 or 35, or assume the excitation setting is a calibrated voltage.

## Models and evaluation

Fit ordinary least squares with an intercept for three fixed predictor sets:

1. log10(cycles).
2. Relative RMS.
3. Relative RMS and relative peak-to-peak amplitude.

Fit on all non-reference checkpoints from one specimen and evaluate on all non-reference checkpoints from the other, then reverse. Use equal checkpoint weights. Report both directions separately. Do not randomly split repeated waveforms, paths or frequencies across training and evaluation.

```text
MAE = mean(abs(prediction - target))
RMSE = sqrt(mean((prediction - target)^2))
```

There is no test-dependent hyperparameter search, prediction clipping or label interpolation in this experiment. A negative prediction is retained as a modelling limitation. The L1S12 20,000-cycle target remains absent; its 30,000-cycle jump remains included.

The original raw-data script uses unscaled least squares and checks coefficients using QR. The independent replay fits with training-only centering/scaling and QR, then returns coefficients to the original feature units. These transformations are mathematically equivalent for full-rank OLS.

## Interpretation

Both signal models beat the chosen log-cycle model in this experiment, with the two-feature model lowest on MAE and RMSE. This does not establish superiority over all cycle-based models, a causal relationship, industrially acceptable accuracy, or generalisation across specimens/layups. Two correlated trajectories and previously inspected evaluation labels support a feasibility study only.

Targets in late L1S12 exceed the maximum training target in L1S11. Persistent underestimation and a negative reverse-direction prediction remain visible in the primary plot. Report these with the favourable relative-error comparison.

## Repeat-recording sensitivity (2026-09-25)

The source root is `data/2.+Composites/2. Composites/`. The sensitivity script reruns the unchanged `scripts/exploratory_regression.py` into `results/repeat_sensitivity/median_rebuild/`. Before evaluating alternatives, it checks recording eligibility, checkpoint membership/features/targets, references, predictions and metrics against `results/baseline/` (numeric tolerance rtol 1e-9, atol 1e-10). Surveyed MAT hashes must also match the recorded baseline. The median results reproduced.

Order comes from the original `Log_fatigue_testing` worksheets in `Layup1/L1_S11_F/L1S11.xlsx` and `Layup1/L1_S12_F/L1S12.xlsx`. Join by specimen and exact filename, reject duplicate entries, and cross-check cycles and normalised condition against the MAT records. Combine the logged date and time and sort within each eligible specimen/checkpoint group. All 51 eligible recordings have unique timestamps within their groups, so endpoints are selected by logged timestamp; the chronology is unresolved. Unique dates are not verified acquisition order: the L1S11 logbook dates go backwards in 4 places (`results/protocol_v2/post_hoc_step4/logbook_L1S11.json`), and at L1S11 80,000 cycles `L1S11_80000_1_2.mat` (row 103, 2011-07-14 09:27) is selected as first ahead of `L1S11_80000_1_1.mat` (row 98, 2011-07-20 09:53) (`results/repeat_sensitivity/selection_provenance.csv`). Neither worksheet nor filename order resolves the true order. The historical selections are kept unchanged; describe the first/last variants as endpoint selection by logged timestamp, not as earliest/latest acquisitions. No timezone is supplied. The exported `selection_provenance.csv` records timestamps, worksheet rows and selected endpoints. Missing/tied timestamps would be explicitly marked as filename-ordered selection, not chronology; worksheet or filename order is not silently substituted.

For every non-reference checkpoint, use either the feature-wise median, both features from the first eligible recording, or both from the last eligible recording. Both specimens use the same variant in each fit/evaluation pair. The original cycle-1 reference recordings and exact RMS/PTP denominators are frozen for all variants. Reference targets stay excluded. Keep all 14/13 checkpoints (13/12 for fitting/scoring), published targets, acquisition and eligibility rules, model definitions and specimen-level transfer splits fixed. Fit each model anew using the existing centred-QR evaluator; independently verify predictions with unscaled least squares. The cycle-only predictions/errors are invariant. No label interpolation, prediction clipping or favourable-repeat selection is performed.

| Train -> evaluate | Selection | Two-feature MAE | Change from median | Two-feature RMSE | Change from median |
|---|---|---:|---:|---:|---:|
| L1S11 -> L1S12 | Median | 0.050532 | 0 | 0.058254 | 0 |
| L1S11 -> L1S12 | First | 0.050592 | +0.000060 (+0.12%) | 0.058542 | +0.000288 (+0.49%) |
| L1S11 -> L1S12 | Last | 0.052183 | +0.001651 (+3.27%) | 0.060744 | +0.002490 (+4.28%) |
| L1S12 -> L1S11 | Median | 0.029357 | 0 | 0.035001 | 0 |
| L1S12 -> L1S11 | First | 0.037760 | +0.008403 (+28.62%) | 0.043140 | +0.008139 (+23.25%) |
| L1S12 -> L1S11 | Last | 0.033315 | +0.003958 (+13.48%) | 0.038596 | +0.003595 (+10.27%) |

The two-feature model is best on both errors in five of six variant/direction combinations. The exception is last repeats, L1S12 -> L1S11: RMS-only MAE 0.031399 and RMSE 0.034864 beat the two-feature results. Both signal models still beat log-cycle in every combination. These changes quantify sensitivity to repeat selection, not confidence intervals or independent replication. Repeat measurements remain correlated and may span different acquisition times at the same cycle count; the comparison does not isolate a causal source of variation.

The run preserves the recorded baseline and source files. All original download files and the sibling ZIP are checked for unchanged sizes/mtimes; surveyed MAT files and both logbooks receive content-hash checks. Focused tests cover timestamp ordering, explicit fallback, contradictory log metadata, fixed membership/targets/references, baseline reproduction, cycle-model invariance, leakage boundaries and exported scores/selection provenance.

## Four regression families and controls (2026-09-25)

The pre-run protocol is `docs/model_comparison_protocol.md`; explicit settings are in `config/model_comparison.json`. Both were written before calculating the new scores and are hash-recorded in `results/model_comparison/protocol_receipt.json`. No configurations were searched against either evaluation specimen. The protocol explains the depth-2 tree, fixed RBF SVR, single three-unit tanh MLP with alpha=1 and L-BFGS, and unregularised linear comparator. MLP seeds are 7, 23, 42, 71 and 101; no random early-stopping validation split is enabled. The full resolved estimator parameters and actual library versions are saved with the run.

All four methods receive the same two checkpoint-median ratios and identical 13/12 non-reference checkpoints. Controls are log-cycle OLS and a training-mean DummyRegressor. StandardScaler sits inside sklearn pipelines for linear, SVR, MLP and log-cycle OLS; the tree and Dummy use passthrough pipelines. SVR/MLP additionally use TransformedTargetRegressor with training-fitted target StandardScaler. All predictions and errors are in original published-index units. References do not enter fitted input/target scalers, fitting or scoring. No imputation, clipping or target calibration is introduced.

The reference audit reads acquisition metadata for all recordings independently of target presence (including unlabelled L1S12 20,000-cycle candidates). It screens positive cycles, condition/load, the unique 1/7/150 path, gain/excitation, sampling rate, both channel lengths, finite/nonconstant waveforms, then takes the earliest acquisition-eligible checkpoint. It rechecks the selected raw waveforms and compares feature medians to the recorded denominators. Both references remain exactly `L1S11_1_1_1.mat` and `L1S12_1_1_8.mat`, with RMS/PTP denominators 689.383565662073/4922.16552734375 and 658.4574074547975/3645.8231201171875. If the independent selection differs in another download, this workflow writes the discrepancy and halts, preserving the historical results.

MAE is the primary comparison. RMSE weights larger residuals more heavily; R² uses each scored specimen's own target mean in its denominator and can be negative. Consequently the deployable training-mean Dummy need not have evaluation R²=0. Training scores describe fit, not independent validation. Residuals are prediction minus observation. `metrics.csv` reports training and evaluation MAE/RMSE/R² for every fit, and `summary.csv` gives each MLP metric's median and min--max across all seeds. These are neither a selected seed nor an ensemble, and seed ranges are not confidence intervals.

Linear regression ranks first by evaluation MAE and RMSE in L1S11 -> L1S12 (0.050532/0.058254). MLP ranks first in the reverse direction for every declared seed (median 0.020942/0.023866), ahead of linear (0.029357/0.035001). Thus no single family wins both directions. Training errors for tree/SVR are small but their forward evaluation errors are large; the plots show substantial underestimation of late L1S12, beyond the L1S11 training target range. The reverse linear fit retains its negative prediction and R²=-0.911314. MLP's reverse R² is modest (median 0.111339), with persistent underestimation rather than an established deployment-quality model. Detailed tables and residual interpretation are in `results/model_comparison/INTERPRETATION.md`.

Verification includes sklearn linear/log-cycle prediction agreement with recorded OLS at rtol 1e-9, atol 1e-10; specimen/reference separation; exact training-only scaler moments; target inverse-transform checks; invariance to altered evaluation/reference targets and evaluation-feature changes during fitting; target-blind reference candidate selection; every predeclared MLP seed; independent recalculation of exported scores. All 19 tests passed at the time; the suite now has 66 tests (pytest), all passing. No convergence warnings arose in reported, warm-up or timed fits. The four saved plot images were visually inspected for common scales, unclipped marks/labels, negative predictions and all-seed display.

### Runtime measurement versus profiling

Model timings use one untimed warm-up and 15 fresh-estimator fits for each model/direction/seed with numerical-library threads limited to one. Fit timing includes input/target preprocessing but excludes construction, loading, scoring and plotting. Prediction timing averages 100 calls on the complete held-out batch per repetition. Raw samples and medians/25th/75th percentiles are retained. On this machine linear fits take about 1.9 ms, tree 1.1--1.4 ms, SVR 3.4 ms, MLP 9.9--18.2 ms across seeds/directions, log-cycle 1.8 ms and Dummy 0.5 ms. Prediction batch medians range about 0.045--0.659 ms. These are local warm-process observations with small batches, not universal speed rankings.

Separately, cProfile instruments the original raw extraction/regression/plot workflow. Its self-time table identifies SciPy MAT array decoding (7.745 s self time) as the largest individual cost, with 254 loadmat calls accumulating 10.121 s. Cumulative times overlap and are not additive; profiled times include instrumentation overhead. Bounded ordered four-thread MAT prefetch targets that measured cost while leaving numerical extraction, selection and source hashes unchanged. The unprofiled benchmark uses fresh processes, one warm-up per mode and three alternating measured pairs, including imports, hashing, fitting and plotting; OS caches are not flushed. It verifies all CSV contents/source hashes against baseline and all serial/prefetch output file hashes, including the plot. Exact timing and equivalence evidence are saved separately under `raw_profile/` and `raw_benchmark/`.

## Code maintenance without changing results (2026-10-11)

Four review findings were fixed before any protocol v2 score was computed.

- **Label-blind reference in the extraction.** `scripts/exploratory_regression.py` now chooses the
  reference as the earliest checkpoint with an acquisition-eligible recording, without reading
  labels or label availability. Previously, unlabelled recordings were dropped before the earliest
  checkpoint was chosen, and only `model_comparison.py` audited the label-blind choice. For L1S11
  and L1S12 both rules select the same cycle-1 recordings, so the denominators are unchanged.
- **Testable functions.** The extractor is now a set of documented functions plus `main()`, and
  importing it has no side effects. `tests/test_extraction.py` checks the features on sampled sines
  (RMS = A/√2, PTP = 2A), each eligibility rule, the label-blind reference, missing-label
  handling, the integrity checks and the output guards.
- **`require()` instead of `assert`.** Integrity checks raise `ValueError` through
  `scripts/common.py`, so they still run under `python -O`.
- **Constants in configuration.** Specimen gain/excitation, load window, path, expected checkpoint
  counts (13/12), coverage counts (12/11) and the retained 0.233175942 jump value moved to
  `config/experiment_v1.json`.

Workflow scripts now refuse to write into recorded results folders. Their default outputs are under
the git-ignored `results/rebuilt/`. `scripts/verify_reproduction.py` reruns the baseline,
repeat-sensitivity, model-comparison and coverage workflows into a scratch folder and compares
every output with the recorded files. Its report is `results/reproduction_check/report.json`.
Every deterministic output matched byte-for-byte or in content. Content-only matches were line
endings or timestamps; timing samples are nondeterministic and were not compared.

## Protocol v2: multi-path inputs, model selection and the held-out test (2026-10-11)

The full predeclared protocol is `docs/protocol_v2.md` (settings in `config/protocol_v2.json`),
committed before any v2 score. Results and their write-ups are under `results/protocol_v2/`.

- **Eligibility and reference.** Recordings are screened label-blind; both input sets use the same
  recordings, checkpoints and reference. L2S11's load window (4.53–4.63 kips) comes from its
  metadata, which puts its reference at cycle 3.
- **Inputs.** Path 1→7 (v1 baseline) or the median over the 36 per-path reference ratios.
- **Models.** The six v1 comparators, unchanged and untuned.
- **Selection.** Lowest worst-direction validation MAE on L1S11 ↔ L1S12, with ties broken towards
  the simpler model. It selected LinearRegression on path 1→7. The single-path scores were known
  from v1 when the rule was written.
- **Test.** The frozen model, refitted on the 25 pooled checkpoints, was scored once on L2S11:
  MAE 0.0374, versus log-cycle 0.0946 and Dummy 0.1015. A post hoc predict-zero baseline scores
  0.0362, so there is **no evidence that the frozen model transfers to L2S11**. The L1S11 sanity
  check failed C1.
- **Where it fails.** The model predicts close to zero when the features are unchanged. On L2S11,
  path 1→7 stays within relative RMS 0.985–1.018 and relative PTP 1.001–1.015, and the frozen
  predictions stay within −0.009 to 0.007, while the index reaches 0.084
  (`results/protocol_v2/post_hoc_step4/summary.json`). The failure is in the feature, not the
  regression.
- **Scope.** Crosstalk on path 1→7, coupling or mounting changes, and specimen (layup, load)
  effects are hypotheses consistent with the data, not established causes. One frozen model was
  tested on one specimen; this does not show that amplitude features cannot transfer in general.
- **Lesson.** A "no damage" (predict-zero) baseline should have been predeclared alongside the
  training-mean Dummy. A control can look beatable merely because it carries another specimen's
  target level.


## Computational cost: FLOPs, arithmetic intensity and memory (2026-10-13)

Brief section 6 asks for FLOP and arithmetic-intensity estimates where appropriate. They are
rough order-of-magnitude estimates. Their purpose is to show where the time goes, not to
optimise arithmetic.

- **Feature extraction (v1).** Each of the 254 development MAT files contributes one 2,000-sample
  receiver signal (path 1→7, 150 kHz).
  - Mean-centred RMS costs about 4 FLOP per sample (mean, subtract, square, sum), and
    peak-to-peak about 2 comparisons per sample.
  - The finite and constant checks on both channels add about 8 operations per sample.
  - Total: roughly 2×10⁴ operations per file, or about 5×10⁶ for the whole run.
- **Feature extraction (v2).** The same work is done on all 36 pairs, with both channels checked,
  so about 7×10⁵ operations per file, or about 2×10⁸ for the 254 development files.
- **Model fits.**
  - **OLS.** With n ≤ 25 rows and p ≤ 3 columns, a Householder QR costs about 2np², fewer than
    500 FLOP per fit. The profile records all six v1 `lstsq` calls together at 0.009 s,
    mostly call overhead.
  - **Other families.** The MLP (3 hidden units) and the SVR on 12–25 rows stay below about
    10⁶ FLOP per fit.
- **Arithmetic intensity.**
  - The 254 development files total 672.7 MB on disk (2.64–2.66 MB each;
    `results/repeat_sensitivity/source_inventory.json`).
  - v1 therefore does about 5×10⁶ / 6.7×10⁸ ≈ 0.01 FLOP per byte read, and v2 about 0.3.
  - Both are two to three orders of magnitude below the roughly 10 FLOP/byte needed to keep a
    modern CPU's arithmetic units busy.
  - Neither workflow can be compute-bound. Speeding up the arithmetic (vectorisation, BLAS
    threads, compiled code) cannot help.
- **What the profiler shows.** `results/model_comparison/raw_profile/tottime.txt` matches this
  prediction. Of 16.778 s instrumented time:
  - MAT decoding (`scipy.io.matlab._mio5.read_var_array`, 254 calls) takes 7.745 s of self time;
  - raw file reads take 1.260 s;
  - SHA-256 integrity hashing takes 1.160 s.
- **What the optimisation targets.** The workflow is bound by I/O and MAT decoding. The chosen
  optimisation therefore overlaps file reading and decoding (`raw_loading.iter_coupons`,
  prefetch), not arithmetic. The serial median of 12.77 s fell to a prefetch median of 7.77 s,
  with byte-identical outputs (`results/model_comparison/raw_benchmark/summary.json`). These
  timings were measured once on one machine and are not reproducible numbers.
- **Memory.** Memory was not measured.
  - By construction, the serial loader holds one decoded file at a time. The prefetch loader
    holds at most `workers` pending files plus the one being processed.
  - Only per-recording summaries are kept after decoding.
  - Peak memory therefore scales with a few decoded files, not with the dataset size, but no
    measured figure is reported.
