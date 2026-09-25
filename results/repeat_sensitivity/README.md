# Repeat-recording sensitivity

Median baseline reproduced before fitting first/last variants. All variants retain the
same eligibility, checkpoints, targets, reference measurements/denominators, models and
specimen splits. Each model is refitted; equal checkpoint weights; no clipping or tuning.

Ordering: unique original logbook date/time within each checkpoint. Ties or missing
timestamps explicitly fall back to filename-ordered selection (not claimed chronological).
Filename-ordered checkpoints: none. Times have no supplied timezone.

| Train -> evaluate | Variant | Two-feature MAE | Change | Two-feature RMSE | Change |
|---|---|---:|---:|---:|---:|
| L1S11 -> L1S12 | median | 0.050531853 | +0.000000000 | 0.058253681 | +0.000000000 |
| L1S12 -> L1S11 | median | 0.029356990 | +0.000000000 | 0.035001220 | +0.000000000 |
| L1S11 -> L1S12 | first | 0.050591994 | +0.000060141 | 0.058541588 | +0.000287907 |
| L1S12 -> L1S11 | first | 0.037760020 | +0.008403030 | 0.043140310 | +0.008139090 |
| L1S11 -> L1S12 | last | 0.052182653 | +0.001650800 | 0.060744154 | +0.002490473 |
| L1S12 -> L1S11 | last | 0.033314539 | +0.003957548 | 0.038596132 | +0.003594912 |

Two-feature model lowest on both errors in both directions for all variants: False.

See rankings.csv for every variant and direction. With last repeats, L1S12 -> L1S11
favours RMS-only (MAE 0.031399039; RMSE 0.034863701), versus two-feature
MAE 0.033314539 and RMSE 0.038596132. All other variant/direction combinations
favour two features on both errors. Thus the ranking is sensitive to repeat selection.

Errors and absolute changes are in published-index units. These are two correlated
specimen trajectories, not independent repeats or population-level validation.
The missing L1S12 20,000-cycle target stays absent and the 30,000-cycle jump stays included.

Verification: all raw-directory files and the sibling archive retain sizes/mtimes;
the extractor verifies SHA-256 before/after for all surveyed L1S11/L1S12 MAT files,
which also match recorded baseline hashes. Both logbooks and the recorded baseline
retain SHA-256 hashes. Other raw files were inventoried, not content-hashed.
Independent unscaled least squares agrees with centred QR for every variant.
