# NASA composites fatigue: stiffness-label feasibility

## Decision

**Conditional go for a small exploratory MMA3001 project using Layup 1; no-go for a well-validated stiffness-degradation predictor spanning Layups 1-3.**

There are 39 distinct published scalar specimen-cycle labels across only three coupons. These comprise 35 positive degradation values, three baseline reference zeros, and one negative value requiring review. The 38 nonnegative entries are a numerical screen, **not 38 independently verified mechanical measurements**. Repeated observations along each coupon remain correlated. There are no populated scalar stiffness labels for Layup 3.

The defensible task is to investigate whether a small number of PZT features track the *published stiffness-degradation index*, while documenting label quality and testing transfer between the two labelled Layup 1 coupons. Strong claims about unseen specimens, other layups, failure time, or remaining useful life are unsupported by this label set.

## Scope and preservation

Inspected the three READMEs; the four distinct reports in Documentation; all 13 actual Excel logbooks; all 1,495 PZT MAT files; all 317 converted strain MAT files; the supplied MATLAB conversion script; and the formats/headers of the remaining strain files. Looked inside each layup ZIP without extracting or changing it to check specimen coverage and the missing L3S14 PZT data. Apple resource forks and operating-system metadata are not experimental records.

All outputs are in `audit_stiffness`, outside the original dataset. The initial inventory and final check agree on presence, sizes and last-write timestamps for all 2,571 files under `2.+Composites/2. Composites`. This is a metadata preservation check, not a cryptographic before/after comparison. No source workbooks, archives, MATLAB files or strain files were saved or modified.

## Labels by layup, in inspection order

| Layup | Coupon | PZT MAT files | Distinct scalar labels | Positive labels | Label cycle range | Assessment |
|---|---|---:|---:|---:|---|---|
| 1 | L1S11 | 145 | 15 | 14 | 0-100,000 | Best starting series; later PZT checkpoints are unlabelled. |
| 1 | L1S12 | 109 | 14 | 13 | 0-100,000 | Usable as a published-index candidate; 20,000-cycle label absent; investigate the discontinuity after the recording gap. |
| 1 | L1S18 | 180 | 0 | 0 | -- | Missing stiffness; zero vectors are placeholders; MTS machine files only. |
| 1 | L1S19 | 82 | 0 | 0 | -- | Only three converted strain files; no published scalar target. |
| 2 | L2S11 | 128 | 10 | 8 | 0-60,000 | One baseline and one negative value; only one labelled coupon in this layup. |
| 2 | L2S17 | 108 | 0 | 0 | -- | Empty stiffness fields; machine files without documented strain-gauge data. |
| 2 | L2S18 | 110 | 0 | 0 | -- | Empty/placeholder stiffness and serious logbook-to-MAT metadata conflicts. |
| 2 | L2S20 | 107 | 0 | 0 | -- | Empty stiffness; machine files without documented strain-gauge data. |
| 3 | L3S11 | 122 | 0 | 0 | -- | Early strain exists, but later gauge saturation/disconnection prevents an assumed full trajectory. |
| 3 | L3S13 | 147 | 0 | 0 | -- | Partial early strain, then gauge failures; no published scalar target. |
| 3 | L3S14 | 0 | 0 | 0 | -- | Raw/text/converted strain exists, but no paired PZT files in the directory or Layup3 ZIP. |
| 3 | L3S18 | 134 | 0 | 0 | -- | Machine files without documented strain-gauge data; placeholder labels. |
| 3 | L3S20 | 123 | 0 | 0 | -- | Machine files without documented strain-gauge data; placeholder labels. |
| **Total** | **13 coupons** | **1,495** | **39** | **35** | | **Only three labelled coupons** |

The READMEs list some specimens not present in the supplied layup archives and omit L3S18 from their top-level list. Counts above use actual directory and ZIP contents.

## What makes a label defensible

A published-label candidate must be a finite scalar in `coupon.straingage_data.stiffness_degradation`, attached to an identifiable coupon and fatigue cycle. Deduplicate at `(coupon, cycle)`, preserve condition/load/repeat information for the inputs, and do not convert an empty array or zero vector into a scalar zero.

The technical report, PDF page 5, section 3.1 instruction 4.3 explicitly prescribes a zero-filled STM when stiffness information is absent. Appendix A, pages 7-8, supplies example STM values and copies `STM(2,ind2)` into each PZT record by matching cycle count. Consequently, repeated values across conditions, paths and frequencies are reused labels rather than new mechanical measurements.

Observed field states across the 1,495 PZT files:

| State | PZT files | Interpretation |
|---|---:|---|
| Finite scalar | 255 | Collapse to 39 coupon-cycle checkpoints. |
| Nonempty all-zero vector | 49 | Missing-information placeholder; exclude. |
| Empty array | 1,191 | Missing target; exclude. |

All PZT MAT files loaded successfully and contain 252 path records. The sampled paths contain actuator/sensor identifiers, frequency, gain, amplitude, sampling rate and signal arrays. This establishes structure and availability, not comprehensive waveform quality: a feature pipeline must still test clipping, flat signals and condition consistency. Numeric frequency values such as 150 correspond to kHz in the experiment description; do not blindly interpret them as Hz.

For a new mechanical label, define the target explicitly, for example `D(N) = 1 - E(N)/E(reference)`, where E is obtained from a consistent, calibrated axial stress-strain loading segment. The existing field is called stiffness degradation, but the included conversion appendix imports a precomputed table rather than showing its complete mechanical calculation. Do not relabel it as a newly verified elastic modulus, or invert/subtract it again without verifying the convention.

## Layup 1 findings

**L1S11:** all 15 published checkpoint values agree with the technical report's example STM. Fourteen positive values range from 0.045813245 to 0.128221136. There are decreases between some adjacent cycles; preserve these measurements rather than silently enforcing monotonicity. The 80 converted strain files contain only `strain1` through `strain4`, not synchronized load/stress arrays. A logbook note at row 67 says no strain was taken for a particular 30,000-cycle PZT acquisition, while other linked strain measurements exist at that checkpoint. Thus not every repeated PZT record is a fresh strain measurement.

**L1S12:** 14 published checkpoints agree with its example STM. Thirteen positive values range from 0.043288345 to 0.245730332. The label rises from 0.084112497 at 10,000 cycles to 0.233175942 at 30,000 cycles; the intervening 20,000-cycle label is absent. Logbook rows 53-71 show a September-November recording gap, a no-gauges entry for F08, and later resumption of rosette measurements. F08's recorded strain channels are close to zero; it should not be used to reconstruct axial stiffness. This is a specific bad recording, not evidence that all later labels must be deleted. Keep the published labels provisional until the jump and acquisition history are resolved.

**L1S18:** README page 1 explicitly lists it among coupons without strain-gauge information. Its 66 extensionless strain-directory files have MTS binary headers; their presence does not establish strain-based stiffness targets.

**L1S19:** three converted files F001-F003 contain strain arrays but no load/stress arrays. Its logbook references further files, such as F004, that are absent from this strain directory. No scalar stiffness series is provided. The conversion script's example also references F004. Do not infer an entire trajectory from these three early records.

## Layup 2 findings

**L2S11:** ten actual scalar checkpoints, although the example STM in the report lists eleven: it includes cycle 100, whereas the actual PZT/logbook checkpoint is 110 and has an empty label. Do not silently move the 100-cycle value to cycle 110. Cycle 1 has `-0.012213572` (about -1.22% under a fractional-loss interpretation). It could reflect noise/reference effects or apparent stiffening; flag it rather than clipping it to zero. Eight positive checkpoints remain, plus the baseline.

The logbook records loss of axial channels: row 72 has only middle/sensor axial gauges; rows 84-102 document balance-high conditions; row 108 says no strain data; row 114 switches to 90-degree gauges. These are not interchangeable axial stiffness measurements. The 69 converted strain files do not supply synchronized load/stress arrays.

**L2S17/L2S18/L2S20:** the README explicitly reports no strain-gauge information. The strain directories contain 38, 30 and 23 MTS binary files respectively. No populated scalar stiffness labels exist.

**L2S18 metadata:** exact filename joins reveal 89 cycle disagreements and 83 load disagreements between the logbook and the MAT fields. Example: the logbook associates `L2S18_0_0.mat` with a loaded 1.004-kip row, while its MAT load is zero. The pattern suggests a filename-column alignment problem; that cause is an inference, not a repaired mapping. Keep this specimen out of any training join until reconciled. There are two additional load disagreements, one each in L1S18 and L3S11. The three labelled coupons have no cycle/load discrepancies in the exact-name numeric comparisons performed.

## Layup 3 findings and reconstruction limits

**L3S11:** 17 converted strain MAT files. `L3_S11_F08_DAT.mat` channel 1 is exactly constant at 0.03968253968253968 across 92,550 samples. Later F10-F28 channel-1 readings are near zero. This agrees with the logbook's gauge-failure warnings around 10,000-20,000 cycles (rows 61-70). Finite numbers are not sufficient evidence of working gauges. Early data might support a separately validated reconstruction, but no additional validated stiffness labels are counted here.

**L3S13:** 47 converted strain files; the logbook records a failed middle gauge at 10,000/20,000 cycles, other axial gauges saturated at 30,000/40,000, and no strain recording at later checkpoints (rows 65, 71, 78, 84, 96, 102, 108). Its zero vectors do not represent an undamaged trajectory.

**L3S14:** 44 converted MAT files, 44 binary recordings and multiple text exports/copies. These are alternative representations, not independent experiments. Some DAT2 exports are empty. The logbook records middle-gauge saturation from 100 cycles, all gauges balance-high at 11,000, a switch to transverse gauges plus an incorrect channel-1 gain at 20,000, and later no strain data (rows 55, 61, 67, 73, 78, 87). No PZT files are present, so even a reconstructed early strain label would not yield a paired PZT training example in this download.

**L3S18/L3S20:** no gauge-derived stiffness information according to the README. L3S18 has 39 MTS binary files; L3S20 has 35 binary files and one seven-column numeric text recording. An export format difference does not establish a calibrated stiffness target.

Every converted MAT strain file has only four strain arrays, and all inspected array elements are finite. None contains a named load, stress, time or cycle array. `MTSDataConvert.m` documents seven original channels and calibration choices (including different strain gains). It also distinguishes continuous fatigue records from stopped-test rosette recordings, whose channel orientations differ. Therefore reconstruction requires more than averaging all strains or using nominal force divided by mean strain. Machine displacement stiffness, local axial gauge stiffness, and laminate modulus should not be silently mixed as one target.

## Recommended project design

1. Use L1S11 and L1S12 as the core pilot: 29 published checkpoints, of which 27 are positive degradation observations and two are baseline references. Describe the outcome as prediction/estimation of the published stiffness-degradation index, with measurement limitations.
2. Start with a very small set of physically interpretable PZT features and a low-complexity regularized regression. Include a cycle-count-only baseline to test whether PZT adds information. Feature choice and performance are future work; no model was trained in this audit.
3. Choose a consistent boundary condition and comparable load/frequency/path configuration. Early static load ramps can cause damage without advancing fatigue cycle count; a single cycle-key label must not be assumed to describe every ramp record equally well.
4. Keep every repeat, path and frequency from the same coupon-cycle in the same partition. For between-coupon transfer, train on L1S11 and test on L1S12, then reverse, reporting both results separately. Two coupons provide a demonstration, not a reliable population-level generalization estimate.
5. Distinguish contemporaneous stiffness estimation from future prediction. For forecasting, use only data available before the target cycle, with forward-time evaluation and no future interpolation, global normalization or future baseline selection.
6. Treat L2S11 as a separate sensitivity/transfer case after reviewing its negative value and gauge history. Do not use it to claim validation across Layup 2; it is the only labelled coupon there. Do not include Layup 3 in supervised stiffness evaluation without independently reconstructed and validated labels.
7. Do not multiply sample size by 252 paths, boundary conditions or repeated acquisitions. Missing labels remain missing; interpolation and model-derived targets are not newly measured ground truth. Avoid a large neural network given only three labelled coupon trajectories.

There is no universal minimum label count. The limiting factor here is independent specimen coverage and mechanical-label validity, rather than storage size or the number of waveforms.

## Evidence files and reproducibility

- `label_checkpoints.csv`: all 39 distinct published labels, baseline/negative flags, repeated PZT filenames and strain-file references. All references attached to these labelled groups resolve to a file after allowing the `.mat` suffix; this does not mean every checkpoint has an independent force-strain measurement.
- `specimen_summary.csv`: specimen-level count reconciliation.
- `pzt_metadata.json`: metadata extracted from every PZT MAT file, including empty/placeholder labels.
- `strain_channels.csv`, `strain_profile.json`, `strain_inventory.csv`: numerical and format profiles.
- `logbook_remarks.csv`, `metadata_conflicts.csv`: exact worksheet rows and join discrepancies.
- `original_manifest.json`, `source_integrity.json`: preservation evidence.
- `audit_review.ipynb`: inspectable computations and assertions over the recorded evidence.
- `inspect_sources.py`, `summarize.py`: extraction and reconciliation scripts. Their dependencies are NumPy, SciPy, openpyxl and pypdf; pypdf was installed only into the audit folder. Reading workbooks may emit an openpyxl unsupported-extension warning; no workbook is saved, so the source extension is not removed.

Controlling sources are the local READMEs, `Documentation/Techical Report.pdf` (filename as supplied), individual logbooks, actual MAT contents and `Layup1/L1_S19_F/StrainData/MTSDataConvert.m`. The additional research papers explain the experiment and modeling context but do not create extra labels for the files present here. NASA's [catalog entry for the accompanying energy-based paper](https://data.nasa.gov/dataset/an-energy-based-prognostic-framework-to-predict-fatigue-damage-evolution-in-composites) corroborates its publication provenance; all reported dataset counts come from this local copy.

Limitations: published stiffness values were reconciled with their documented lookup tables, not independently re-derived from calibrated force-strain traces; vendor binary recordings were identified by their headers, not fully decoded; full waveform-level QC and model validation were not performed. Text extraction of the multi-scale paper's first page is garbled, so it was not used for quantitative label claims. These limitations prevent a stronger claim of mechanically validated ground truth but do not change the observed shortage of independent labelled trajectories.
