# MMA3001: composite fatigue and ultrasonic stiffness estimation

An exploratory engineering project investigating whether reference-normalised ultrasonic features estimate a published stiffness-degradation index better than a cycle-count baseline.

**Current stage:** the median regression, repeat sensitivity and predeclared four-family regression comparison are complete. Linear regression has the lowest evaluation MAE in L1S11 -> L1S12; the small MLP has the lowest MAE in the reverse direction. These are exploratory specimen-held-out validation results, with no untouched final test specimen.

## Question and scope

Can a linear model using relative RMS and relative peak-to-peak amplitude from one ultrasonic path transfer between two CFRP specimens more accurately than a model using log-cycle count?

- Dataset: NASA composites fatigue data; specimens **L1S11 and L1S12**, Layup 1.
- Input: actuator 1 to receiver 7, nominal 150 kHz, loaded near 4 kips.
- Target: existing `coupon.straingage_data.stiffness_degradation` values. These are published index candidates, not newly validated modulus measurements.
- Evaluation: fit on one specimen and evaluate on the other, then reverse.
- Deployment assumption: an early reference waveform is available for each specimen. It is not assumed undamaged, and its target is not used for calibration.

## Quick start: reproduce the regression without downloading the raw dataset

Run these commands **from this repository**, not the folder containing the NASA data. On Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/reproduce_results.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

On Linux or macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/reproduce_results.py
.venv/bin/python -m unittest discover -s tests -v
```

The replay reads the included checkpoint table and writes new CSVs under `results/reproduced/`. It does not alter the recorded first experiment. It reproduces regression calculations, **not extraction of features from the original waveforms**.

## Rebuild from the NASA files

The local download is in the ignored `data/2.+Composites/` directory. Inspection confirmed that its `2. Composites` child contains `Layup1`, `Layup2` and `Layup3`. Pass that child directory:

```powershell
.\.venv\Scripts\python.exe scripts/exploratory_regression.py --data-root "data/2.+Composites/2. Composites"
```

No re-extraction or moving the NASA files is required. Outputs go to `results/rebuilt/`. The script refuses an output directory within the original data or the recorded baseline.

See [data setup](data/README.md) for the actual layout and exclusions. Raw extraction has now reproduced the recorded baseline locally. Original files remain excluded from Git, including documentation, logbooks and X-rays.

## Repeat-recording sensitivity

```powershell
.\.venv\Scripts\python.exe scripts/repeat_sensitivity.py --data-root "data/2.+Composites/2. Composites"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Original logbook timestamps uniquely order all 51 eligible recordings within their checkpoints. The comparison keeps the 27 checkpoints (25 after excluding references), targets, references and denominators, eligibility, model definitions and specimen splits fixed, and refits each model for median, first and last selection.

The two-feature model remains best on MAE and RMSE for first repeats in both directions and for last repeats in L1S11 -> L1S12. For last repeats in L1S12 -> L1S11, **RMS-only is best** (MAE 0.031399; RMSE 0.034864), ahead of two features (0.033315; 0.038596). Thus the original ranking is sensitive to repeat selection. Full metrics and changes are in [the sensitivity results](results/repeat_sensitivity/README.md). This is still a two-specimen exploratory study.

## First experiment

The original experiment below is preserved. The later model-family comparison uses the same two median signal features and data boundaries; it does not replace these recorded results.

14 labelled nonzero-cycle checkpoints were retained for L1S11 and 13 for L1S12. Removing one reference per specimen leaves **13 and 12 checkpoints** for fitting/scoring. Multiple checkpoints from one specimen remain correlated.

| Train → evaluate | Model inputs | MAE | RMSE |
|---|---|---:|---:|
| L1S11 → L1S12 | log10(cycles) | 0.090299 | 0.105431 |
| L1S11 → L1S12 | Relative RMS | 0.071013 | 0.072705 |
| L1S11 → L1S12 | Relative RMS + relative peak-to-peak | **0.050532** | **0.058254** |
| L1S12 → L1S11 | log10(cycles) | 0.092013 | 0.098381 |
| L1S12 → L1S11 | Relative RMS | 0.056906 | 0.060876 |
| L1S12 → L1S11 | Relative RMS + relative peak-to-peak | **0.029357** | **0.035001** |

Errors are in published-index units. The two-feature model reduces MAE by about 44% and 68% relative to the chosen cycle-count model. These are error reductions, not accuracy percentages. Substantial bias remains, and one two-feature prediction is negative.

![Held-out predictions for the first three models](results/baseline/predicted_vs_observed.png)

## Project files

| Location | Purpose |
|---|---|
| `scripts/exploratory_regression.py` | Rebuild features, models and plots from the external MAT dataset |
| `scripts/reproduce_results.py` | Independently refit the exported features using centred QR |
| `docs/model_comparison_protocol.md`, `config/model_comparison.json` | Protocol and fixed settings written before running the new comparisons |
| `scripts/model_comparison.py` | Reference audit, six-comparator evaluation, all MLP seeds, repeated timings and plots |
| `results/model_comparison/` | Comparison scores, predictions, warnings, provenance, timing and raw-workflow profiling |
| `results/baseline/` | Recorded first experiment: features, references, predictions, metrics and plot |
| `tests/` | Scientific-result reproduction and checks against target leakage |
| `docs/methodology.md` | Selection rules, equations and validation design |
| `docs/progress.md` | Completed work and remaining tasks |
| `docs/ai-use.md` | Record of AI assistance, for student review |
| `docs/github-setup.md` | Creating the private GitHub remote and normal commit workflow |
| `archive/` | Earlier exploratory scripts, figures and audit summaries |

## Week 5 model-family comparison

Install the updated requirements (including scikit-learn and threadpoolctl), then run:

```powershell
.\.venv\Scripts\python.exe scripts/model_comparison.py --data-root "data/2.+Composites/2. Composites"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

MAE is primary; RMSE and residual patterns support interpretation. All four families use checkpoint-median relative RMS and relative peak-to-peak. The log-cycle OLS and training-mean Dummy are controls. Input scaling is learned on the training specimen only; SVR/MLP target scaling is likewise training-only and predictions are returned to published-index units. The target-independent acquisition/waveform reference audit preserves both original cycle-1 reference files and denominators exactly.

| Model | MAE: L1S11 -> L1S12 | MAE: L1S12 -> L1S11 |
|---|---:|---:|
| LinearRegression | **0.050532** | 0.029357 |
| DecisionTreeRegressor | 0.105158 | 0.045803 |
| RBF SVR | 0.111193 | 0.056257 |
| Small MLP, median across five seeds | 0.078193 | **0.020942** |
| Log-cycle OLS | 0.090299 | 0.092013 |
| Training-mean Dummy | 0.107731 | 0.083110 |

MLP MAE ranges across the fixed seeds are 0.074266--0.078196 and 0.020936--0.021264 respectively. No seed was selected and no convergence warnings occurred. There is no overall winner across directions. Full training/evaluation MAE, RMSE and R², seed-specific results, plots and timing evidence are in [comparison results](results/model_comparison/README.md) and [interpretation](results/model_comparison/INTERPRETATION.md).

Raw-workflow profiling and unprofiled serial/prefetch measurements are separate commands:

```powershell
.\.venv\Scripts\python.exe scripts/profile_raw_workflow.py --data-root "data/2.+Composites/2. Composites"
.\.venv\Scripts\python.exe scripts/benchmark_raw_workflow.py --data-root "data/2.+Composites/2. Composites"
```

**Output folders (since 2026-10-11).** Every workflow script writes to a new folder under the git-ignored `results/rebuilt/` by default, and refuses to overwrite recorded results. To confirm that the recorded results still reproduce, run:

```powershell
.\.venv\Scripts\python.exe scripts/verify_reproduction.py --data-root "data/2.+Composites/2. Composites"
```

The report is written to `results/reproduction_check/report.json`. The test suite has 49 tests.

MAT parsing was the measured bottleneck. A bounded ordered prefetch option is available as `--workers 4` on `scripts/exploratory_regression.py`; default `--workers 1` preserves serial execution. All original hash/selection checks remain enabled. Timing results are local observations, not general hardware benchmarks.

## Limitations

- Only two labelled specimens in the primary experiment; no broad validation across layups, remaining-useful-life prediction or verified failure-time model.
- A nominal 150 kHz signal produces a roughly 15 kHz FFT peak using the stored 1.2 MHz rate. Physical timing is unresolved. Current features use sample indices and do not claim a physical time-of-flight.
- L1S11 uses gain/excitation settings 33/65; L1S12 uses 35/50. Reference ratios remove only constant multiplicative effects under that assumption, not all acquisition differences.
- The L1S12 20,000-cycle label is missing. A label jump after 10,000 cycles is retained and flagged. Targets have not been independently reconstructed from calibrated force-strain data.
- Features and models were explored interactively. This is a development experiment, not a sealed final benchmark. Future model selection should disclose this exploration.
- Checking finite/nonconstant signals does not establish complete waveform quality or absence of clipping.

## Reproducibility and attribution

Numerical replay and tests were checked with Python 3.12.14, NumPy 2.3.5, SciPy 1.17.0 and Matplotlib 3.10.8. `requirements.txt` gives compatible ranges, not an exact environment lock. Automated checks are local; a GitHub-hosted CI run is not claimed.

Dataset source: [NASA PCoE Data Set Repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/). The local technical report, README files and logbooks control file-level interpretation. See [data/README.md](data/README.md) and [AI assistance](docs/ai-use.md).

The MIT licence covers original project code and documentation; third-party dataset material and underlying data rights are not relicensed. Raw MAT files, experimental workbooks and source papers are excluded from this repository.
