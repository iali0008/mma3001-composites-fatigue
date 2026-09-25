# Predeclared Week 5 regression comparison

Written on 2026-09-25 before running the new model comparison. This repository file
and `config/model_comparison.json` are the reviewable protocol; no commit or push
is made in this task. Save their SHA-256 hashes with each run. Do not revise model
settings after viewing evaluation scores. Any later revision is a new experiment.

## Question and fixed data

Compare LinearRegression, DecisionTreeRegressor, RBF SVR and a small MLP on the
same two checkpoint-median inputs: relative RMS and relative peak-to-peak.
Include log10(cycles) OLS and training-mean DummyRegressor as controls.
Read `results/baseline/checkpoint_features.csv`; preserve all existing baseline
and repeat-sensitivity files. Retain the published targets, label exclusions and
30,000-cycle L1S12 jump, equal checkpoint weights and the original references.

Exclude the cycle-1 reference from fitting and scoring. Train on all 13 remaining
L1S11 checkpoints and evaluate on all 12 L1S12 checkpoints; then reverse. No random
checkpoint/repeat split, evaluation-driven search, clipping or label interpolation.
These are exploratory specimen-held-out validation results. Both specimens have
already been inspected and neither is an untouched final test set.

## Reference correction, before comparisons

Audit raw recordings without consulting target values or availability. Require
positive cycles, Loaded condition, load 3.95--4.05 kips, actuator 1 / receiver 7 /
150 kHz, specimen-specific gain/excitation (33/65 and 35/50), stored sampling rate
1,200,000 and both channel lengths 2,000. For usable reference waveforms also
require both signals finite/nonconstant and positive receiver RMS/PTP. Select the
earliest eligible cycle and use feature medians across its acquisition-eligible
recordings. This is the original reference checkpoint convention with target
availability removed, not a claim of an undamaged baseline. Record raw candidate
provenance and compare the selected files, cycles and denominators with the
existing references. If different, report the discrepancy and halt this fixed-
reference comparison rather than silently replacing historical results.

## Fixed model configurations and rationale

All four families receive identical two-feature matrices. Every learned input
transform is inside an sklearn Pipeline fitted only on the training specimen.
Use StandardScaler (mean and variance learned on training checkpoints only) for
linear regression, SVR and MLP. Tree and Dummy use passthrough pipelines. The
log-cycle control uses StandardScaler plus LinearRegression with intercept.

* LinearRegression: fit_intercept=True, positive=False. The unregularised linear
  comparator must reproduce existing two-feature OLS predictions (rtol 1e-9,
  atol 1e-10); log-cycle OLS must also reproduce its baseline.
* DecisionTreeRegressor: criterion=squared_error, splitter=best, max_depth=2,
  min_samples_leaf=3, min_samples_split=6, max_features=None, ccp_alpha=0,
  random_state=42. At most four leaves, with at least three training checkpoints
  per leaf, limits memorisation with only 12--13 observations. No pruning search.
* SVR: kernel=rbf, C=1, epsilon=0.1, gamma=0.5, tol=0.001, shrinking=True,
  cache_size=200, max_iter=-1. Fixed gamma is 1 / number of standardised inputs;
  C and epsilon use training-standardised target units. This is a smooth modest
  default, not a claim that it is optimal for this dataset.
* MLPRegressor: hidden_layer_sizes=(3,), activation=tanh, solver=lbfgs,
  alpha=1.0, max_iter=2000, max_fun=20000, tol=1e-6, early_stopping=False,
  shuffle=False. A single three-unit layer has 13 parameters; L2 regularisation
  and smooth activations constrain this still-flexible small-sample model.
  Full-batch L-BFGS avoids noisy minibatches and random internal validation splits.
  Report every seed in the fixed set [7, 23, 42, 71, 101]; never select a best seed.
* DummyRegressor: strategy=mean, trained on training targets only.

SVR and MLP use TransformedTargetRegressor(StandardScaler) around the input
Pipeline. Fit target scaling on training targets only; inverse-transform all
predictions before scoring. Other models have no target transformation. Record
the full resolved sklearn parameters and package versions. Limit numerical
library threads to one during fits/timings for consistency.

## Outcomes and interpretation

MAE in published-index units is primary. Report training and evaluation MAE,
RMSE and R² separately for both transfer directions. Define residual as prediction
minus observation; include mean residual, most negative prediction and residual
plots against cycle count as supporting evidence. R² can be negative and is not
an accuracy percentage. No pooling to conceal conflicting directional rankings.

For MLP, export every seed's predictions, scores, iterations and all convergence
warnings, including timed fits. Summarise its scores by median and min--max across
the five seeds, not by the best seed. This summary is not an ensemble prediction
or a confidence interval. Plot all five seed predictions/residuals.

## Verification, timing and profiling

Focused tests check specimen separation, exclusion of references, input/target
scalers fitted to training data, invariance of predictions to evaluation-target
changes, reference-selection independence from targets, and sklearn OLS agreement.
Check raw-data exclusion from Git and preserve source metadata plus input hashes.

For each direction, model and MLP seed: perform one untimed warm-up, then 15
independent fresh-estimator fits timed with perf_counter. Exclude estimator
construction, data loading, scoring and plotting. Include learned input/target
preprocessing in fit time. For prediction, time 100 calls on the complete held-out
batch per repetition, divide by 100, and report the 15 per-batch times (median,
25th and 75th percentiles). Keep raw timing samples. These are local warm-process
measurements, not hardware-independent benchmarks; no cold-cache claim.

Separately run cProfile on the original raw extraction/regression/plot workflow
and save cumulative and self-time summaries. Profiling attributes cost and has
instrumentation overhead; it is distinct from repeated elapsed runtime timing.
Only change a component after profiling identifies it as a bottleneck. If a safe
optimisation is justified, measure original and optimised workflows separately
without profiling, retain all source-integrity checks, and verify numerical
outputs and selection provenance are equivalent. Do not optimise model settings
for speed or accuracy. If no justified optimisation is made, state that clearly.

## Deliverables

Use `results/model_comparison/` for protocol/configuration receipts, reference
audit, metrics, per-seed predictions, residual/prediction plots, warnings,
preprocessing audit, timing samples/summaries and raw-workflow profiling evidence.
Update README, methodology and progress. Preserve previous results. Do not
commit, push, or modify original NASA files.

Implementation references: sklearn's [MLPRegressor documentation](https://scikit-learn.org/1.7/modules/generated/sklearn.neural_network.MLPRegressor.html)
describes full-batch L-BFGS and early stopping; the [pipeline and target-transform guide](https://scikit-learn.org/1.8/modules/compose.html)
describes fitted preprocessing and inverse-transformed predictions. Runtime package
versions and fully resolved parameters are recorded separately from these references.
