# Progress and decisions

This is a consolidated record of work reported in the project conversation and uploaded outputs, not a claim of contemporaneous Git commits.

## Completed

- Completed the Week 5 four-family comparison on 2026-09-25 under a protocol/configuration written before new scores (`docs/model_comparison_protocol.md`, `config/model_comparison.json`). Used identical median features, targets, checkpoints and specimen splits, plus log-cycle OLS and training-mean Dummy controls. No evaluation-specimen tuning or best-seed selection.
- Corrected reference auditing to use acquisition/waveform criteria independently of target availability; both original cycle-1 references and exact denominators are preserved. Input/target preprocessing is training-only, with predictions returned to published-index units.
- LinearRegression has the lowest evaluation MAE in L1S11 -> L1S12 (0.050532); the three-unit MLP has the lowest in reverse for all five seeds (median 0.020942; range 0.020936--0.021264). There is no single winner across directions. No convergence warnings occurred. Full train/evaluation MAE, RMSE, R², residuals, plots and timings are in `results/model_comparison/`.
- All 19 scientific/reproduction tests passed. Sklearn linear/log-cycle predictions match recorded OLS within tolerance. All four plot images were visually checked. Historical baseline/sensitivity artifact hashes and surveyed original MAT hashes remain unchanged; original raw files remain ignored and untracked/unstaged.
- Measured model fit and batch-prediction runtime with one warm-up, 15 repetitions and 100 prediction calls per repetition. Separately profiled the raw workflow: MAT decoding was the largest self-time cost. Added bounded ordered four-thread prefetch (`--workers 4`, serial default). Three alternating unprofiled pairs showed median 12.769 s serial versus 7.771 s prefetch (1.643x), with every output file byte-identical. Memory usage was not profiled.

- Chose an existing public composites dataset; no new experimental data collection.
- Audited local dataset labels, including missing zeros, repeated labels and strain limitations. Earlier audit implementation and notebooks are now present under `data/audit_stiffness/`.
- Inspected one signal and recorded an unresolved factor-of-ten timing discrepancy.
- Compared two recordings and extracted mean-centred RMS / peak-to-peak features.
- Aggregated L1S11 checkpoints with consistent settings.
- Checked the same settings on L1S12: no exact match because gain/excitation differ. The empty result is preserved in the archive, not presented as the current dataset.
- Defined specimen-specific constant settings and early-reference ratios.
- Ran three OLS models in both transfer directions; kept missing labels and the label jump unchanged.
- Collected code/results into this repository, made raw-data paths configurable and added an independently calculated replay plus regression/leakage checks.
- Connected `origin` to `https://github.com/iali0008/mma3001-composites-fatigue.git`; the existing initial commit is `4f75752`. This task made no commit or push.
- Located the moved NASA download at `data/2.+Composites/2. Composites/`, directly containing all three layups. Explicit ignore rules cover the complete wrapper and sibling archive; `data/README.md` stays tracked. Original dataset files are neither tracked nor staged.
- Reran the portable raw-data pipeline and reproduced recorded median features, references, predictions and metrics before sensitivity fitting.
- Completed median/first/last repeat sensitivity under `results/repeat_sensitivity/`, holding all experiment boundaries and reference denominators fixed. Original logbook timestamps establish order for all 51 eligible recordings; no filename fallback was needed.
- Found that two features remain best for first repeats in both directions and last repeats in L1S11 -> L1S12. Last repeats in L1S12 -> L1S11 favour RMS-only (MAE 0.031399, RMSE 0.034864) over two features (0.033315, 0.038596). Two-feature errors rise relative to medians in all first/last comparisons; see methodology for absolute and percentage changes.
- Validation on 2026-09-25: all 12 baseline/sensitivity tests passed with Python 3.13.3, NumPy 2.3.0, SciPy 1.17.1 and openpyxl 3.1.5. Independent unscaled OLS agrees with every centred-QR fit. All 2,607 original wrapper/archive files are ignored and retain sizes/mtimes; surveyed MAT files match baseline SHA-256 hashes, and logbook/baseline hashes are unchanged. `git diff --check` passed; nothing is staged.

## Remaining

- [ ] Review the already imported audit/feasibility code for portability and bundled dependencies before relying on those historical workflows. Their reference conventions differ from this regression.
- [ ] Record the exact source download URL/version and check required data attribution.
- [ ] Confirm the scoped alternative project with the teaching team if not already approved; approval is not established by this repository.
- [ ] Investigate the physical sampling-rate discrepancy if adding spectral features or time-of-flight.
- [ ] Write the student's interpretation, limitations and AI reflection; align final deliverables with the actual project brief.
- [ ] Obtain additional independent specimens for a future frozen-model validation; neither current specimen is an untouched final test set.
- [ ] Measure peak memory or cross-hardware performance only if a concrete implementation requirement needs it; this task measured runtime and profiled CPU call costs, not memory.

## Working conventions

Preserve `results/baseline` as the first recorded experiment. Put changed analyses in a separate output directory. Commit code, relevant small outputs and an explanation of each material change. Do not edit original experimental files, fill missing labels to enlarge the sample, or select a new feature based on favourable evaluation results without disclosing exploratory selection.
