# Interpretation and validation record

The predeclared comparison is complete. These are **exploratory specimen-held-out
validation results**, not final-test performance. MAE is primary. LinearRegression
has the lowest evaluation MAE for L1S11 -> L1S12; all five predeclared MLP seeds have
lower evaluation MAE than linear regression in the reverse direction. RMSE agrees
with these directional rankings. There is no single winner across directions.

## Training and evaluation metrics

MAE and RMSE are in published-index units. MLP rows report each metric's median
across seeds 7, 23, 42, 71 and 101; they are not one selected fit or an ensemble.
All seed-specific metrics, including training values, remain in `metrics.csv`.

| Train -> evaluate | Model | Train MAE | Train RMSE | Train R² | Eval MAE | Eval RMSE | Eval R² |
|---|---|---:|---:|---:|---:|---:|---:|
| L1S11 -> L1S12 | LinearRegression | 0.008395 | 0.009753 | 0.851585 | **0.050532** | **0.058254** | 0.534215 |
| L1S11 -> L1S12 | DecisionTreeRegressor | 0.009196 | 0.010932 | 0.813553 | 0.105158 | 0.117024 | -0.879715 |
| L1S11 -> L1S12 | RBF SVR | 0.007352 | 0.008734 | 0.880979 | 0.111193 | 0.126674 | -1.202483 |
| L1S11 -> L1S12 | MLP (seed median) | 0.008510 | 0.009888 | 0.847461 | 0.078193 | 0.087694 | -0.055551 |
| L1S11 -> L1S12 | Log-cycle OLS | 0.007362 | 0.008966 | 0.874595 | 0.090299 | 0.105431 | -0.525737 |
| L1S11 -> L1S12 | Training-mean Dummy | 0.021370 | 0.025317 | 0.000000 | 0.107731 | 0.119134 | -0.948086 |
| L1S12 -> L1S11 | LinearRegression | 0.023559 | 0.033444 | 0.846479 | 0.029357 | 0.035001 | -0.911314 |
| L1S12 -> L1S11 | DecisionTreeRegressor | 0.020342 | 0.036427 | 0.817868 | 0.045803 | 0.051352 | -3.114093 |
| L1S12 -> L1S11 | RBF SVR | 0.013128 | 0.018638 | 0.952322 | 0.056257 | 0.064136 | -5.417602 |
| L1S12 -> L1S11 | MLP (seed median) | 0.022326 | 0.032693 | 0.853297 | **0.020942** | **0.023866** | 0.111339 |
| L1S12 -> L1S11 | Log-cycle OLS | 0.027626 | 0.038327 | 0.798369 | 0.092013 | 0.098381 | -14.100526 |
| L1S12 -> L1S11 | Training-mean Dummy | 0.080028 | 0.085355 | 0.000000 | 0.083110 | 0.086881 | -10.776416 |

MLP forward evaluation ranges: MAE 0.074266--0.078196, RMSE 0.082907--0.087698,
R² -0.055653--0.056549. Reverse ranges: MAE 0.020936--0.021264,
RMSE 0.023453--0.023872, R² 0.110910--0.141866. These seed ranges are not
confidence intervals. The reported fits took 22--61 L-BFGS iterations. There were
zero convergence warnings in reported, warm-up and repeated timed fits.

## Residual behaviour

Residual means below use prediction minus observation. In L1S11 -> L1S12, mean
residuals are -0.0350 (linear), -0.0820 (tree), -0.0936 (SVR), and -0.0625 (MLP
seed median). Late L1S12 targets exceed the L1S11 training range; the plots show
substantial underestimation, especially for tree and SVR. The low SVR training
MAE of 0.007352 does not translate into useful transfer performance here.

In reverse, linear and MLP remain negatively biased (mean residuals -0.0276 and
-0.0191 respectively); SVR is mostly positively biased (+0.0511). Linear retains
its negative early prediction. MLP improves reverse-direction errors but its
median R² of 0.111339 is modest. Negative R² compares with the scored specimen's
own mean, not the available training-mean Dummy, so those are different baselines.
No prediction was clipped and the published L1S12 label jump was retained.

All four figures use common prediction/residual limits across models and
directions, hollow training marks and filled evaluation marks. All MLP seeds are
shown, with seed/marker legends. They were visually inspected.

* [Forward predictions](predictions_L1S11_to_L1S12.png)
* [Reverse predictions](predictions_L1S12_to_L1S11.png)
* [Forward residuals](residuals_L1S11_to_L1S12.png)
* [Reverse residuals](residuals_L1S12_to_L1S11.png)

## Two-feature coverage diagnostic

This post-hoc diagnostic uses the same non-reference checkpoint medians as the
comparison: 13 L1S11 checkpoints and 12 L1S12 checkpoints. A StandardScaler is
fitted to the training specimen only in each direction, and its means, scales
and sample count match the recorded comparison preprocessing exactly. The hull
is constructed from training points only. Evaluation coordinates and all target
values play no part in defining the scaler or hull. No regressors were fitted,
no configurations were tuned, and all existing model predictions remain unchanged.

| Train -> evaluate | Training checkpoints | Evaluation outside training hull | Evaluation inside/on hull |
|---|---:|---:|---:|
| L1S11 -> L1S12 | 13 | **12/12** | 0/12 |
| L1S12 -> L1S11 | 12 | **11/13** | 2/13 |

The two reverse-direction evaluation points inside the hull are L1S11 at
**10,000 and 20,000 cycles**. All training points lie inside or on their own hull.
The reported outside-hull counts are therefore independently confirmed.

The primary check evaluates SciPy ConvexHull's half-space inequalities in
training-standardised coordinates. The independent check tests containment in
every nondegenerate triangle formed by training points using barycentric weights;
it does not use Qhull or the primary hull's vertices. In two dimensions, these
triangles cover the convex hull. Both methods agree for every checkpoint,
including a check in unscaled feature coordinates. Boundaries count as inside.
The half-space tolerance is 1e-10 in standardised coordinates and the independent
weight tolerance is 1e-10; all classifications are unchanged at 1e-12 and 1e-8.

The main plot uses dimensionless relative RMS and relative peak-to-peak axes;
the companion plot shows the training-standardised coordinates. Hull membership
is invariant under this nonsingular affine scaling, so the raw-axis plot and
scaled check describe the same coverage. Both plots show all non-reference
training/evaluation points and each direction's training hull.

* [Relative-feature coverage plot](coverage/feature_coverage.png)
* [Training-standardised coverage plot](coverage/feature_coverage_standardised.png)
* [Per-checkpoint flags and coordinates](coverage/checkpoint_coverage.csv)
* [Hull vertices](coverage/training_hull_vertices.csv)
* [Independent checks, scaler audit and preservation hashes](coverage/verification.json)

**Outside-hull membership is not a measure of extrapolation distance.** A point
just beyond an edge and a point far from the training cloud receive the same
outside flag. These counts neither quantify how far predictions extrapolate nor
rank extrapolation severity between directions. They also do not imply that a
point exceeds either feature's individual range: a new combination of two
individually familiar feature values can fall outside the hull. Conversely,
inside-hull membership does not guarantee dense nearby support or accurate
predictions. The high outside counts show limited joint feature coverage, but do
not by themselves explain residual magnitude, prove a model's extrapolation
ability, or establish a causal reason for the directional ranking difference.
This geometric diagnostic does not change the exploratory validation status.

Reproduce with `python scripts/feature_coverage.py` from the repository root.
The script reads exported features and preprocessing provenance; it does not read
or modify the original NASA files. Focused tests cover known interior/boundary/
exterior points, training-only scaling, duplicate training points and the saved
checkpoint membership/counts.

## Reference handling and reproducibility

The independent acquisition/waveform gate does not access target values,
availability, or the historical target-dependent eligible flag. Unlabelled
L1S12 20,000-cycle recordings remain reference candidates, although they are later
than the selected reference and remain excluded from fitting/scoring. Both
original cycle-1 reference recordings and all four denominators are preserved
exactly. Candidate provenance and raw-waveform confirmation are in
`reference_candidates.csv` and `reference_audit.csv`.

All preprocessing was fitted on non-reference training checkpoints only.
SVR/MLP target scaling was inverted before scoring. Every fitted scaler's moments,
sample counts and training/evaluation cycle identities are recorded in
`preprocessing_audit.json`. Both sklearn linear models reproduce historical OLS
predictions at rtol 1e-9, atol 1e-10. The 19 focused/reproduction tests pass,
including target/feature leakage perturbations and independent score calculations.
Raw files remain ignored, with no tracked/staged originals. Previous baseline and
repeat-sensitivity artifacts are hash-preserved; source metadata and the 254
surveyed MAT hashes are unchanged. See `verification.json`.

## Runtime measurements

Fit milliseconds below are medians of 15 fresh fits after one warm-up. Prediction
milliseconds refer to the complete held-out batch (12 or 13 checkpoints), with
100 calls averaged per repetition. Scaling/inverse target scaling are included;
estimator construction, loading, scoring and plotting are excluded. Numerical
library threads are limited to one. Each MLP range below spans the five seeds'
timing medians, not their fastest individual run. Per-seed IQRs and all raw samples
are saved in `timing_summary.csv` and `timing_samples.csv`.

| Model | Forward fit ms | Forward predict ms | Reverse fit ms | Reverse predict ms |
|---|---:|---:|---:|---:|
| LinearRegression | 1.919 | 0.369 | 1.884 | 0.365 |
| DecisionTreeRegressor | 1.397 | 0.257 | 1.052 | 0.207 |
| RBF SVR | 3.417 | 0.647 | 3.362 | 0.659 |
| MLP, seed-median range | 13.656--18.197 | 0.604--0.625 | 9.887--14.458 | 0.611--0.626 |
| Log-cycle OLS | 1.781 | 0.355 | 1.844 | 0.354 |
| Training-mean Dummy | 0.477 | 0.045 | 0.495 | 0.045 |

These local measurements depend on runtime/hardware and process/OS state. They
are not cold-cache benchmarks, memory profiles or industrial throughput estimates.
The runtime was Python 3.13.3, sklearn 1.9.0, NumPy 2.3.0 and SciPy 1.17.1.

## Raw-workflow profile and measured optimisation

cProfile attributed 7.745 s self time to SciPy MAT array decoding; 254 loadmat
calls accumulated 10.121 s. That measured parsing cost motivated bounded ordered
prefetch with four threads, leaving all source-hash checks and analysis rules
intact. Cumulative profile times overlap and cannot be added together. Profiling
has instrumentation overhead and is distinct from the elapsed measurements below.

The separate benchmark ran one warm-up per mode followed by three alternating
unprofiled pairs in fresh processes. It includes imports, raw reading/parsing,
hashing, modelling and plot generation. Median serial time was **12.769 s**
(range 12.696--12.918); four-thread prefetch was **7.771 s** (7.724--8.009), a
**1.643x speedup**, or **39.14% lower elapsed time** on this machine. OS caches
were not flushed. This is a concurrency improvement, not reduced algorithmic work.
Prefetch holds at most four pending full coupons plus the currently consumed coupon;
peak memory was not measured. Serial remains the default; opt in with `--workers 4`.

Both modes reproduce baseline CSV values and source hashes, and every resulting
serial/prefetch file is byte-identical, including the plot. Profiling evidence is
in `raw_profile/`; unprofiled samples and equivalence checks are in
`raw_benchmark/`. The original recorded baseline and sensitivity results were not
rewritten by these runs.

## Limitations and remaining work

The requested comparison, reference audit, tests, plots, timings and measured
optimisation are complete. No configuration or MLP seed was selected using the
evaluation specimen. Nevertheless, both trajectories have already influenced
project development: these are not untouched final tests. Only two specimens,
correlated checkpoints and different acquisition settings limit interpretation.
Targets are published index candidates rather than independently validated modulus
loss. Failure/RUL prediction and broad layup transfer have not been established.

Remaining project work:

* Obtain genuinely independent specimens for a future frozen-model validation;
  do not relabel either current specimen as an untouched final test.
* Resolve target interpretation and the stored sampling-rate discrepancy before
  making physical stiffness or time-of-flight claims.
* Confirm exact dataset provenance/attribution and teaching-team scope; complete
  the student's interpretation, AI reflection and course-aligned write-up.
* Memory profiling and broader hardware benchmarking were not performed; they
  are separate future tasks if implementation requirements call for them.

No commit or push was made.
