# L1S11 / L1S12 PZT feature feasibility

## Decision

**A small simple-regression experiment is worth attempting, with substantial limits on transfer claims.** The same three paths retain all 29 published specimen-cycle checkpoints (27 nonzero indices plus two baseline references). All 63 selected recordings pass the specified basic signal screens. RMS decreases strongly within each specimen, but zero-lag correlation is repeat-sensitive, the L1S12 label jump remains unresolved, and the physical sampling clock is inconsistent with the excitation metadata. No model was trained and no labels were interpolated.

## Comparable subset and selection rule

The survey covers every path in all 254 L1S11/L1S12 PZT MAT files: 64,008 path records. We choose **traction free**, including the explicitly documented pristine `_0_0` recording even though L1S11 tags that record `Baseline`. This avoids fixture/loading variation. Both pristine references and all selected traction-free recordings have zero recorded load.

Selection used only boundary condition, path metadata, settings, lengths, reference availability and whether labels exist, **never index magnitude, target correlation, prediction error or a held-out outcome**. The rule requires every available labelled cycle and both pristine references with exact settings, chooses the frequency with the largest set of eligible paths (ties: lower frequency), then selects the first three actuator/sensor pairs in numeric order. There were 25 eligible path-frequency settings: 1 at nominal 300 kHz, 2 at 350, 3 at 400 and 19 at 450. Thus the chosen frequency was 450 kHz. This is a small deterministic subset, not a claim that these are the most damage-sensitive paths.

| Actuator → sensor | Nominal frequency | Stored gain | Stored drive amplitude | Exported sample rate | Samples / channel |
|---|---:|---:|---:|---:|---:|
| 1 → 10 | 450 kHz | 20 | 25 | 1,200,000 Hz | 2,000 |
| 2 → 8 | 450 kHz | 20 | 35 | 1,200,000 Hz | 2,000 |
| 2 → 11 | 450 kHz | 20 | 15 | 1,200,000 Hz | 2,000 |

Signals are matched by `(actuator, sensor, frequency)`, with uniqueness asserted per file. Array index is recorded only as an audit field and never used to join signals. No position variation was observed in this two-specimen survey, but the implementation does not assume that ordering. Gain and amplitude are matched exactly within each path across specimens and references; their differing values between paths are not pooled as calibrated amplitudes.

Repeat markers are numbered in logbook worksheet order within each specimen-cycle, excluding the designated pristine reference. Exact filenames and their original repeat suffixes are retained separately. This matters for `L1S11_1000_1_2.mat`: despite its filename's condition code, both its MAT metadata and logbook row 49 say traction free. It is an ordinary 1,000-cycle repeat, not a baseline. Selection follows those condition records rather than guessing from filenames.

| Specimen | Labelled checkpoints retained | Labelled recordings, including reference | Extra unlabelled recordings | Total recordings | Sensor feature rows |
|---|---:|---:|---:|---:|---:|
| L1S11 | 15 / 15 | 32 | 0 | 32 | 96 |
| L1S12 | 14 / 14 | 26 | 5 | 31 | 93 |
| Total | 29 / 29 | 58 | 5 | 63 | 189 |

Of the 189 sensor-feature rows, 174 have published labels. The extra L1S12 records occur at cycles 2, 3 and 20,000 (three repeats at 20,000). Their measured features appear as open markers in the cycle plots and remain absent from index plots. Analysis stops at 100,000 cycles, the shared published-label horizon from the existing audit; later unlabelled PZT recordings are outside this pilot.

L1S11 labelled cycles: 0, 1, 10, 100, 1,000, 10,000, 20,000, 30,000, 40,000, 50,000, 60,000, 70,000, 80,000, 90,000, 100,000.

L1S12 labelled cycles: 0, 1, 10, 100, 1,000, 10,000, 30,000, 40,000, 50,000, 60,000, 70,000, 80,000, 90,000, 100,000.

## Signal-quality results

The selected data comprise 189 sensor traces and 189 paired actuator traces: **378 traces checked**. None has nonfinite values, an unexpected length, a flat trace, a settings mismatch or a clipping-suspicion flag. All arrays have 2,000 samples. The selected gain/amplitude/rate settings stay constant throughout the chosen horizon. Actuator RMS relative to its matching pristine trace ranges from 0.99705 to 1.00657 (approximately -0.30% to +0.66%). This supports reasonably stable recorded excitation amplitude, not complete environmental equivalence.

The explicit screening rules are saved in `selection_plan.json` and implemented in `qc_signal`:

- Flat: peak-to-peak range at most `1e-10 * max(1, abs(min), abs(max))`.
- Possible clipping: at least three consecutive samples equal to an observed extreme, or at least 1% of samples within 0.1% of the trace range of either extreme, excluding already-flat traces.
- Nonfinite: any NaN/infinity; expected length: 2,000 on each channel; exact settings/reference compatibility.

These are screening rules. ADC rail specifications are not supplied, and previous filtering/processing could conceal clipping, so zero flags do **not** certify an unclipped analog acquisition. Flat nonzero pretrigger portions of a burst are not classified as a flat *whole trace*. Representative sensor overlays and the actuator burst were visually inspected in the saved plots.

## Sampling units: material unresolved issue

The README describes nominal interrogation frequencies of 150–450 **kHz**. The stored frequency values are 150–450, while sections of the technical report label them Hz; treating `450` as 450 Hz would contradict the experiment description. The export code in the technical report, PDF page 8, hard-codes `sampling_rate=1.2e6` rather than preserving the original acquisition timing configuration.

Every surveyed MAT path reports 1.2 MHz. Nevertheless, the pristine actuator FFT peaks for nominal 450 kHz are 0.0385 cycles/sample in L1S11 and 0.039 in L1S12. Interpreting those at 1.2 MHz gives 46.2 and 46.8 kHz, not 450 kHz. The seven-frequency diagnostic shows a similar roughly tenfold discrepancy across 150–450 kHz and in both channels. The finite burst means FFT peaks are approximate; it does not explain an order-of-magnitude discrepancy.

**Inference, not a correction:** a clock near 12 MHz would approximately reconcile the nominal excitation and sampled actuator oscillation. Resampling, another acquisition clock, or incorrect exported metadata could also explain the inconsistency. The original acquisition setup is not preserved in these converted records. The actual physical time step is therefore **not verified**. We do not substitute 12 MHz or claim physical time-of-flight or energy in joules.

Plots use sample indices for waveforms. Absolute integrated squared amplitudes are saved only as `sensor_integral_metadata_au2_s`, explicitly conditional on the exported rate. Main features use within-path reference ratios, for which a common time-step multiplier cancels. The identical lengths, exported rates, matching settings and stable actuator waveforms support this sample-domain comparison, while an unrecorded clock change cannot be excluded.

## Features and references

Reference for each specimen/path: its own pristine `L1S11_0_0.mat` or `L1S12_0_0.mat`. The documentation identifies these initial zero-load measurements as the undamaged baseline. Each reference matches path identity, nominal frequency, stored gain/amplitude, length and exported rate. L1S11's other cycle-zero traction-free repeats occur after static loading and are **not** averaged into the pristine reference.

For the complete sensor trace `s`, set `x = s - mean(s)` and apply the same centering to reference `r`. No target-chosen window, filter, alignment, resampling, future reference or fitted scaler is used.

| Feature | Calculation | Interpretation / units |
|---|---|---|
| Centered RMS | `sqrt(mean(x**2))` | Signal amplitude in exported arbitrary units; saved raw and divided by reference RMS. |
| Integrated squared amplitude | `sum(x**2) / fs_exported` | Rectangle rule over 2,000 sample bins; a.u.²·s only conditional on the exported clock. Sum of squares also saved. Main plot divides by the identical reference calculation, cancelling the clock factor. |
| Reference correlation | `dot(x,r)/(norm(x)*norm(r))` | Dimensionless, zero-lag, signed waveform similarity in [-1,1]. Sensitive to phase/timing changes; no maximization over lag. |
| Actuator RMS ratio | Same-record centered actuator RMS / pristine actuator RMS | Acquisition diagnostic, not selected as a stiffness predictor. |

At the **individual recording** level, normalized integrated squared amplitude is exactly normalized RMS squared; this identity is checked numerically. They are alternative amplitude features, not two independent predictors. Checkpoint medians are descriptive summaries of repeats; with even numbers of repeats the median implementation averages middle values, so median energy need not equal squared median RMS. All original recording-level values and IDs remain in the CSVs and plots.

Using the held-out specimen's own initial, unlabelled-in-use calibration waveform is permissible only if such a baseline will be available at deployment. Its later stiffness targets must remain unavailable to preprocessing and model selection. This pilot does not demonstrate transfer to specimens without their own compatible baseline.

## L1S12: 10,000 to 30,000 cycles

### Documented observations

- The published index changes from **0.084112497** at 10,000 cycles to **0.233175942** at 30,000: +0.149063445 index units (about 14.91 percentage points if interpreted as fractional loss). The 20,000-cycle target is missing.
- Logbook rows 53–56: 10,000-cycle rosette/PZT measurements were taken on 6 September 2011; a further traction-free PZT recording followed on 14 September.
- Row 58 on 14 September says “no strain gages - using for SHMiA” for the subsequent loaded recording. It does not establish permanent loss of all later gauges.
- Rows 61–65: the three 20,000-cycle traction-free recordings are dated 14 September, 2 November and 14 November. The log records resumed MTS strain acquisition on 14 November. This is a substantial interval at the same recorded cycle count, not a fabricated interpolation point.
- Rows 66–68 on 14 November: rosette file names are present again at 30,000 cycles; the operator records that delamination grew vertically.
- Row 69 on 15 November records a data shift and proposes dye or temperature as a possible cause. The shift is a documented observation; its cause is the operator's hypothesis.
- Exact path-key comparisons across all **252 paths** in these seven traction-free recordings show **zero changes** in stored gain, amplitude, sample rate or either signal length. The selected paths also have zero load throughout. A recorded acquisition-setting switch is therefore not supported as the explanation.
- At 30,000 cycles, selected path A2→S11 correlation with the pristine reference changes from **+0.37745** to **-0.66720** between the two repeats. The index is identical, while their RMS ratios are similar (0.33068 and 0.33338). This illustrates phase/shape sensitivity of zero-lag correlation independently of overall amplitude.

### Possible explanations and limits

Actual damage growth, changes in gauge condition/calibration after the interruption, unrecorded coupling/temperature effects, and dye-related effects are plausible contributors. The available records do not separate them. Recorded delamination supports the presence of damage; it does not by itself quantify the stiffness jump. Matching settings rule out changes in the stored fields, not every unrecorded acquisition effect.

The selected path amplitudes do not show one coherent proportional jump with the index: median RMS ratio declines for A1→S10 but rises for A2→S8 and A2→S11 between 10k and 30k. Repeat-to-repeat changes at the same cycle also occur, including at unlabelled 20k. The jump is retained, with explicit flags and its acquisition context. No points are removed because they disagree with a desired trend.

## What the features support

Using one median per specimen-cycle-path only for description, RMS ratio has Spearman association with the published index of approximately **-0.92 to -0.94 for L1S11** and **-0.86 to -0.96 for L1S12** across the three predetermined paths. These are in-sample descriptive associations, with 15 and 14 checkpoint groups, not validation scores or independent evidence of causation. Strong associations with cycle count also occur; PZT's incremental value over cycle count remains untested.

Reference correlation is less consistent: its index association ranges from about -0.73 to +0.10 for L1S11 and -0.46 to -0.007 for L1S12. Later L1S12 points cluster near index 0.23–0.25 while features and repeats still vary. Baseline normalization does not guarantee an identical feature–stiffness relationship between specimens.

Recommended next experiment: a predeclared, low-dimensional regularized regression using RMS ratios (or energy ratios, **not both**) and optionally a separately assessed correlation feature, compared with a cycle-count-only baseline. Hold out an entire specimen, run both transfer directions and report both; keep all paths/repeats from a checkpoint together. Do not choose the best path from the held-out specimen's scores. For future-cycle prediction, additionally use a forward-time design. Two independent coupons remain insufficient for a reliable population generalization claim.

## Files and rerunning

- `feasibility.ipynb`: executed notebook, methods, tables and embedded figures; runs top-to-bottom from raw MAT sources with an inventory cache that is hash-checked.
- `run_feasibility.py`: deterministic extraction/selection/QC/plotting pipeline. Run `python pzt_feasibility/run_feasibility.py` from the workspace root. Original data are read only; all writes use this output directory.
- `features.csv`: every specimen, cycle, recording filename, repeat ID, path, reference filename, label/missing label, raw and normalized features, QC flags, and logbook row/date.
- `L1S11_features.png/.svg`, `L1S12_features.png/.svg`: separate specimen plots against cycles and index; no lines joining missing labels.
- `L1S12_jump.png`, `L1S12_jump_features.csv`, `L1S12_jump_logbook_rows.csv`, `L1S12_jump_setting_changes.csv`: focused evidence for the gap/jump.
- `signal_qc.csv`, `waveform_check.png`: all selected channel checks and representative waveforms.
- `sampling_check.png`, `sampling_diagnostics.csv`, `baseline_frequency_check.csv`: the unresolved sampling-unit check.
- `selection_plan.json`, `eligible_full_coverage_paths.csv`, `comparable_settings_coverage.csv`, `acquisition_inventory.csv`, `record_inventory.csv`: selection and metadata provenance.
- `checkpoint_medians.csv`, `repeat_ranges.csv`, `descriptive_associations.csv`: derived diagnostic summaries; recording-level data remain authoritative.
- `selected_signals.npz`: compact derived copy of the selected traces for the plots, not a replacement for source files.
- `environment.json`, `requirements.txt`, `verification.json`, `source_hashes_before.json`: reproducibility and preservation evidence.

Source SHA-256 hashes agree before/after for all **254 PZT MAT files**. The existing audit's presence/size/last-write checks still agree for all **2,571 source files**. No model was trained; original data and the existing audit files were not modified. The remaining label-provenance limitations from the original audit still apply.
