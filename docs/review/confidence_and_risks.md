# Where I am least confident

Written by Claude for Sans's local review. Ordered by how much each item could change a reported
conclusion. "Untested" means no automated test exercises it.

## A. Repository and data-handling risks (need a decision)

- **R1. Third-party material is committed.** Since the initial commit (`4f75752`),
  `data/audit_stiffness/` has contained full-text extractions of the dataset's README, the
  Technical Report and three papers (`*.pdf.txt`), plus a vendored copy of `pypdf`.
  `data/pzt_feasibility/selected_signals.npz` (2.3 MB) appears to hold waveform excerpts from the
  raw data. These may conflict with "never commit raw data" and with redistributing papers. Removing
  them from history requires a history rewrite, which is your call. A zipped clone would include
  them.
- **R2. Unmerged branches.** All October work is on `protocol-v2` and `code-fixes`; `main` is
  still `7d282b2`. The brief requires a functional main branch.
- **R3. Numbers in CLAUDE.md fact 4 without repo outputs.** These are the repeat spread (13% and
  29%), the ±5% reference effect (±0.006 MAE), MLP–linear correlations 0.95–0.99, the Spearman
  values and the RMS-only slopes. They came from the claude.ai review session. Under the working
  rules they cannot go into the report unless a script reproduces them.

## B. Scientific assumptions

- **S1. Label meaning.** "1 − E/E₀" is inferred from the table shape and the README wording. No
  document states it. Every interpretation of the errors as stiffness loss rests on this.
- **S2. Path identity across specimens.** Identical stored IDs and positive envelope-timing
  correlations (0.40–0.76) support consistency but do not prove it. The selected model uses path
  1→7 across specimens, so if the IDs differed physically the cross-specimen comparison would be
  meaningless. The multi-path median does not depend on this.
- **S3. Crosstalk interpretation.** The early-peak pairs are those with an envelope maximum before
  sample 400, a threshold I chose after looking at the waveforms. The crosstalk explanation rests
  on the peak position not changing with path length, plus a timing argument that uses the
  inferred 12 MHz rate. It is plausible, not demonstrated.
- **S4. Reference states differ.** L1S11 and L1S12 reference at cycle 1, after a 0–7 kip static
  ramp at cycle 0. L2S11 references at cycle 3, after ramps to 8 kips at cycle 2. The amount of
  damage already present at the reference differs between specimens and is unknown.
- **S5. Multiplicative normalisation.** Per-path ratios cancel gain and excitation only if their
  effect is a constant multiplier. Gain may be in dB (the README says "20dB"), and coupling can
  drift (the 177k jump).
- **S6. 12 MHz sampling rate.** This rests on the actuator burst being exactly at the nominal
  frequency. With 2,000-sample FFT bins the implied rate is approximate (11.69–12.00 MHz). It
  does not affect any reported score.

## C. Protocol and process caveats

- **P1. Selection rule written after v1 scores were known.** Single-path linear regression was
  already known to be best on worst-case MAE. This is disclosed, but it weakens "predeclared".
- **P2. Smoke test.** It computed the L2S11-independent sanity outcome before the official run
  (disclosed).
- **P3. Pooled final model never validated as pooled.** Validation trained on one specimen; the
  frozen model trained on two.
- **P4. Arbitrary sanity criteria.** C1 compares the mean of five late predictions with a single
  100k prediction. The C2 and C3 bounds are reasonable but arbitrary.
- **P5. Predict-zero baseline is post hoc.** It is the most informative comparison, and it was not
  predeclared.
- **P6. Small samples.** MAE on 8 L2S11 checkpoints and R² on 8–13 correlated points are
  unstable. One checkpoint (cycle 10) rests on a single recording.

## D. Logic that could be subtly wrong

- **L1. Logbook chronology.** `repeat_sensitivity.order_repeats` trusts logbook timestamps, which
  go backwards in 4 places. At L1S11 80,000 cycles the recorded first/last selection may be
  reversed. The historical results are unchanged and flagged, not corrected.
- **L2. Modal setting vector.** The eligibility rule compares each file with the most common
  36-pair setting vector. Ties are broken by file order (untested). This is irrelevant for these
  data, but fragile for new specimens.
- **L3. Labels attached by file name.** `protocol_v2.attach_labels` uses only the eligible files
  of a checkpoint. If an ineligible file at the same cycle carried a different label, it would be
  silently ignored, not reported.
- **L4. Environment fields in the reproduction check.** The `equal_except_environment` category
  ignores data path, git-check and byte-hash fields in JSON receipts. A genuine change in those
  fields would be hidden. CSV contents are compared separately, which limits the risk.
- **L5. The prediction hash.** The recorded hash is of the CRLF working copy; the LF-normalised
  hash is recorded beside it. Anyone checking the original hash in a clone will see a mismatch
  unless they read the note.
- **L6. Profiling numbers are machine-state dependent.** The recorded 12.77 → 7.77 s became
  15.5 → 11.0 s in a later smoke run, not recorded. Present them as local measurements.

## E. Untested or only smoke-tested code

| Code | Exercised by |
|---|---|
| `protocol_v2_validation.main`, `protocol_v2_test.main` | one official run each, plus one smoke run on a scratch copy; no unit test of the end-to-end flow or the guards |
| `audit_acquisition_v2.geometry_consistency`, `per_pair_setting_changes` | run once; outputs inspected manually |
| `dataset_facts.py` | doctest for `peak_bin` only |
| `post_hoc_*.py` | run once each |
| `verify_reproduction.classify` | used in real runs; no unit test of each status |
| `build_docs.py` | doctest for path forms; the output was inspected |
| `model_comparison.benchmark`, `plot_results`; plotting in all scripts | reproduction byte checks only |
| Ranged requirements (newer NumPy and scikit-learn) | not verified; only `requirements-lock.txt` is |

## F. Known cosmetic or non-material issues

- **Cosmetic HTML difference.** Rebuilt HTML can differ from the committed copy by a pdoc
  show-value toggle, which depends on the checkout path length; the content is the same.
- **Global tools.** pytest-html, pdoc, black and pyflakes are also installed in the global Python.
  The README now directs every command to the venv.
