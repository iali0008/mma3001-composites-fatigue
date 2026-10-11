# Protocol v2 validation (step 3): L1S11 ↔ L1S12

Produced by `scripts/protocol_v2_validation.py` at commit `6ccee92` under the predeclared
`docs/protocol_v2.md` and `config/protocol_v2.json`. Only L1S11 and L1S12 were read; L2S11 was not
opened. All numbers below are copied from `summary.csv`, `candidates.csv`,
`checkpoint_features.csv` and `reproduction_gate.json` in this folder.

## Integrity

- **Eligibility.** The joint, label-blind rules keep 36 L1S11 and 27 L1S12 recordings. The
  references are cycle 1 for both specimens (`L1S11_1_1_1.mat`, `L1S12_1_1_8.mat`), as the audit
  expected.
- **Scored checkpoints.** 13 L1S11 and 12 L1S12 checkpoints are scored, as in v1. Unlabelled
  eligible checkpoints get features but are never fitted or scored: L1S11 at 125,000–227,000 cycles
  and L1S12 at 2, 3 and 20,000 cycles.
- **Reproduction gate.** All 500 single-path predictions (every model, seed, split and direction)
  equal the recorded v1 predictions, with a maximum absolute difference of 0.0. The gate ran before
  any multi-path score was written.
- **Convergence.** No convergence warnings occurred.

## Evaluation MAE (published-index units)

MLP values are five-seed medians; seed ranges are in `summary.csv`. Lower is better.

| Model | Input set | L1S11 → L1S12 | L1S12 → L1S11 | Worst direction |
|---|---|---:|---:|---:|
| LinearRegression | single path 1→7 | 0.0505 | 0.0294 | **0.0505** |
| LinearRegression | multi-path 36 | 0.0903 | 0.0688 | 0.0903 |
| DecisionTreeRegressor | single path 1→7 | 0.1052 | 0.0458 | 0.1052 |
| DecisionTreeRegressor | multi-path 36 | 0.0907 | 0.0393 | 0.0907 |
| SVR | single path 1→7 | 0.1112 | 0.0563 | 0.1112 |
| SVR | multi-path 36 | 0.0963 | 0.0301 | 0.0963 |
| MLPRegressor | single path 1→7 | 0.0782 | 0.0209 | 0.0782 |
| MLPRegressor | multi-path 36 | 0.0888 | 0.0113 | 0.0888 |
| log-cycle OLS (control) | none | 0.0903 | 0.0920 | 0.0920 |
| training-mean Dummy (control) | none | 0.1077 | 0.0831 | 0.1077 |

## Selection (predeclared rule, applied mechanically)

**Selected: LinearRegression with the single-path 1→7 input.** Its worst-direction MAE, 0.0505, is
the lowest. The next candidate, single-path MLP at 0.0782, is far outside the 0.0005 tie tolerance,
so no tie-break was needed. The selection is recorded in `../selection.json`. The final model is
this configuration refitted on the 25 pooled non-reference checkpoints of L1S11 and L1S12.

## What the results show

- **Multi-path did not win on the declared criterion.** For every family, multi-path is worse
  than the selected model in the forward direction (L1S11 → L1S12). There, all models
  underestimate the late L1S12 targets, which exceed L1S11's training range.
- **Multi-path helps the flexible models in reverse.** In L1S12 → L1S11, multi-path lowers MAE
  for the tree, SVR and MLP; the MLP reaches 0.0113 with R² 0.699. It hurts LinearRegression,
  whose reverse multi-path predictions fall as low as −0.275.
- **The multi-path features shift between specimens.** The non-reference multi-path ratios span
  0.417–0.961 (PTP) on L1S11 but only 0.318–0.606 on L1S12. The single-path 1→7 PTP ratios span
  0.879–1.029 and 0.833–1.060. Multi-path ratios fall much further than 1→7, and their ranges
  barely overlap between the two specimens. An unbounded linear fit therefore extrapolates.
- **Controls.** The selected model beats both controls in both directions.

## Caveats for interpretation

- **Single-path scores were already known.** The single-path candidates are the v1 scores, which
  were known when the selection rule was written; only the multi-path scores are new. The rule
  (worst direction, simpler model on ties) was declared without the multi-path results, but its
  choice of aggregation was made in the knowledge that v1 linear regression had the lowest
  worst-case MAE. This must be disclosed in the report.
- **The selected path may be crosstalk-dominated.** The protocol audit found that pair 1→7 has a
  fixed early (crosstalk-like) envelope peak in all three specimens, and relative PTP on such paths
  may mostly track that early energy. The selected model may therefore partly exploit acquisition
  behaviour rather than wave propagation through damage. This is interpretation only; the
  selection stands.
- **Small evidence base.** Two correlated specimen trajectories with 12–13 checkpoints each give a
  feasibility signal, not a population-level estimate. References are single checkpoints, so
  differences of a few thousandths should not be over-read.

## Files

`receipt.json` (protocol hashes, commit, written before any fit), `recordings.csv`
(per-file eligibility and reasons), `checkpoint_features.csv` (both input sets),
`pair_ratios.csv` (the 36 per-pair ratios behind each multi-path feature), `references.csv`,
`metrics.csv` (every fit, training and evaluation), `summary.csv`, `predictions.csv`,
`candidates.csv`, `reproduction_gate.json`, `source_hashes.json`, and the two prediction plots.
