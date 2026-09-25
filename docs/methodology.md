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

## Features and reference

For a receiver sequence x with n samples:

```text
peak-to-peak = max(x) - min(x)
mean-centred RMS = sqrt(sum((x - mean(x))^2) / n)
```

Take each feature's median across eligible recordings from the same specimen and cycle. Require labels within each group to agree. Repeated recordings are not independent labels.

Divide each checkpoint feature by its specimen's feature at the earliest eligible checkpoint. Both references are at cycle 1: `L1S11_1_1_1.mat` and `L1S12_1_1_8.mat`. These are chronological references, not undamaged states. Reference targets do not enter the fit, error metrics or a target-offset calibration.

Eligibility currently requires a populated target; in this download the first positive-cycle eligible recording also has that label. If applying the method to unlabelled deployment data, select the early reference from waveform/acquisition criteria alone, not target availability.

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
