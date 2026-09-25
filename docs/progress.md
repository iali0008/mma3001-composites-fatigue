# Progress and decisions

This is a consolidated record of work reported in the project conversation and uploaded outputs, not a claim of contemporaneous Git commits.

## Completed

- Chose an existing public composites dataset; no new experimental data collection.
- Audited local dataset labels, including missing zeros, repeated labels and strain limitations. Assessment and checkpoint inventory supplied here; full local audit implementation remains to be imported.
- Inspected one signal and recorded an unresolved factor-of-ten timing discrepancy.
- Compared two recordings and extracted mean-centred RMS / peak-to-peak features.
- Aggregated L1S11 checkpoints with consistent settings.
- Checked the same settings on L1S12: no exact match because gain/excitation differ. The empty result is preserved in the archive, not presented as the current dataset.
- Defined specimen-specific constant settings and early-reference ratios.
- Ran three OLS models in both transfer directions; kept missing labels and the label jump unchanged.
- Collected code/results into this repository, made raw-data paths configurable and added an independently calculated replay plus regression/leakage checks.

## Remaining

- [ ] Create/connect the private GitHub remote and make the initial import commit under the student's configured identity.
- [ ] Run the portable raw-data entry point on the Windows dataset and compare with the recorded baseline.
- [ ] Import the existing `audit_stiffness` scripts/notebook from the local machine, checking them for paths and large data before committing.
- [ ] Complete the proposed first-recording versus last-recording sensitivity check. It has **not** been run in this repository. Establish chronological order from logs/metadata, not lexicographic filename order.
- [ ] Record the exact source download URL/version and check required data attribution.
- [ ] Confirm the scoped alternative project with the teaching team if not already approved; approval is not established by this repository.
- [ ] Investigate the physical sampling-rate discrepancy if adding spectral features or time-of-flight.
- [ ] Write the student's interpretation, limitations and AI reflection; align final deliverables with the actual project brief.
- [ ] Measure runtime/memory only when assessing a concrete implementation question; no profiling results are claimed yet.

## Working conventions

Preserve `results/baseline` as the first recorded experiment. Put changed analyses in a separate output directory. Commit code, relevant small outputs and an explanation of each material change. Do not edit original experimental files, fill missing labels to enlarge the sample, or select a new feature based on favourable evaluation results without disclosing exploratory selection.
