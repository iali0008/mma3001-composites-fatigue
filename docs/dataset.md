# Dataset: provenance, terms, label definition, sampling rate and units

This page resolves the open dataset questions (plan step 5). Each number comes from
`results/dataset_facts/facts.json`, produced by `scripts/dataset_facts.py`, unless another source
is named. Page numbers refer to the PDF page in the dataset's own `Documentation` folder.
The files there are `Techical Report.pdf` (filename as supplied), `README.pdf` (top of each layup
folder) and `STI_9408_1368_Final Paper.pdf`.

## 1. Provenance, citation and terms

- **Source.** NASA Prognostics Center of Excellence (PCoE) Data Set Repository, entry "CFRP
  Composites". Experiments were run at the Stanford Structures and Composites Laboratory with NASA
  Ames PCoE.
- **Repository page.** <https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/>,
  accessed 2026-10-11.
- **Download link.** The repository page lists `https://phm-datasets.s3.amazonaws.com/NASA/2.+Composites.zip`.
  The local folder name `2.+Composites` matches that archive. The download date of the local copy
  was not recorded.
- **Citation, as requested by the repository.**
  > Abhinav Saxena, Kai Goebel, Cecilia C. Larrosa, and Fu-Kuo Chang, "CFRP Composites Data Set",
  > NASA Prognostics Data Repository, NASA Ames Research Center, Moffett Field, CA.
- **References cited by the dataset README** (`README.pdf`, pp. 2–3):
  - [3] A. Saxena, K. Goebel, C. C. Larrosa, V. Janapati, S. Roy and F.-K. Chang, "Accelerated
    aging experiments for prognostics of damage growth in composite materials", *Proc. 8th
    International Workshop on Structural Health Monitoring*, Stanford, 2011.
  - [4] M. Chiachío, J. Chiachío, A. Saxena, G. Rus and K. Goebel, "Fatigue damage prognosis in
    FRP composites by combining multi-scale degradation fault modes in an uncertainty Bayesian
    framework", *Proc. 9th International Workshop on Structural Health Monitoring*, Stanford, 2013.
  - [5] J. Chiachío, M. Chiachío, A. Saxena, G. Rus and K. Goebel, "An energy-based prognostic
    framework to predict fatigue damage evolution in composites", *Proc. Annual Conference of the
    PHM Society*, 2013.
- **Terms.** The repository page names no licence. It asks publications to acknowledge the
  repository and the data donors, and states that users employ the data at their own risk and that
  neither NASA nor the donors assume liability. The related data.nasa.gov catalogue entries
  describe the papers, hold no data files, and say "License not specified" (checked 2026-10-11).
- **What this repository contains.** The NASA download itself (MAT files, logbooks, X-rays, PDFs,
  archives) is git-ignored and not committed. The current tree contains only material derived from
  it, kept for reproducibility with the citation above:
  - feature, label and prediction tables under `results/`;
  - the label-audit outputs under `data/audit_stiffness/`. These are derived tables and statistics,
    including short verbatim logbook remarks in `logbook_remarks.csv` and a few truncated array
    values in `coupon_samples.json`;
  - the historical feasibility tables, figures and notebooks under `data/pzt_feasibility/`.
- **Untracked on 2026-10-12.** Raw waveform excerpts (`selected_signals.npz`), a full logbook dump,
  raw structure dumps, extracted text of the dataset documentation and papers, and a vendored copy
  of pypdf were removed from the tree and git-ignored (review finding C2/R3; inventory in
  `docs/review/data_inventory.md`). **They remain in earlier commits** (from `4f75752`), so a clone
  with full history still contains them.
- **Licence of this project.** The MIT licence covers only this project's code and documentation,
  not the dataset, the papers or derived values of the published index.

## 2. What the published stiffness index is

- **Field.** `coupon.straingage_data.stiffness_degradation`, described in `README.pdf` p. 2 as
  "stiffness value obtained from the strain-gages".
- **How it was written.** The curators' conversion script NEWFILEDEF.m (Technical Report,
  Appendix A.1) holds hand-typed stiffness tables (STM) per coupon (PDF p. 7, lines 25–57). Each
  table starts at 0 at cycle 0. Line 108 (PDF p. 8) finds the file's cycle count in the table, and
  line 133 copies `STM(2,ind2)` into every PZT file at that cycle. Section 3.1, step 4.3 (PDF p. 5)
  says to write a table of zeros when no stiffness information exists.
- **Consequences.** Repeated values across paths, conditions and repeats are one copied value per
  checkpoint, not new measurements. Zeros can be placeholders.
- **Not unique.** Table "T22" (PDF p. 7, lines 35–39; that coupon is not in the download) rises
  from 0.11799544 at 80,000 cycles to 0.247092307 at 90,000. A jump like L1S12's at 30,000 cycles
  therefore also occurs elsewhere in the curators' tables.
- **Best-supported interpretation.** The value is a normalised stiffness loss, 1 − E/E₀, relative
  to the coupon before cycling. It starts at 0 and mostly rises. **No document states this
  formula,** so it remains an interpretation.
- **Sign convention differs from the papers.** Reference [4] defines D = E_eff/E₀
  (`STI_9408_1368_Final Paper.pdf`, PDF p. 3, equation 6), which starts at 1 and falls. It uses
  the threshold D_max = 0.88 (PDF p. 6). The published index behaves like 1 − D, so it must not be
  compared with D without converting.
- **Strain-file links.** `straingage_data.file_location` names the strain files behind a label.
  For example, `L1S12_1_1_8.mat` (cycle 1) links `L1_S12_S09_STRAIN_A/M/S_DAT`, and
  `L1S12_100000_1_1.mat` links `L1_S12_F27_STRAIN_A/M/S_DAT`. Linked labelled files: L1S11 31,
  L1S12 25, L2S11 16.
- **Cannot be recomputed.** Every converted strain file holds only `strain1`–`strain4` (L1S11 80
  files, L1S12 57, L2S11 69). There is no load, stress or time array, so the index cannot be
  independently recomputed from the download.

## 3. Sampling rate

- **The stored value is a constant.** Every path record stores `sampling_rate` = 1,200,000
  (96,264 records across the three labelled specimens). NEWFILEDEF.m line 102 (Technical Report
  PDF p. 8) writes `path_data(i).sampling_rate=1.2e6` as a constant; it is not a measurement.
- **The spectra disagree with it.** The actuator signal of pair 1→7 has its FFT peak at bin 25 of
  2,000 in all 382 files at 150 kHz. That is 80 samples per period. With the stored rate, the peak
  would be at 15 kHz instead of 150 kHz.
- **Implied rate about 12 MHz.** All seven interrogation frequencies (150–450 kHz) imply rates
  between 11.69 and 12.00 MHz (bin resolution limits precision). The true rate is therefore about
  12 MHz, ten times the stored value.
- **Burst length.** At 150 kHz the actuator burst spans a median 366 samples, about 4.6 periods.
  This is consistent with a 5-cycle tone burst.
- **Effect on this project.** RMS and peak-to-peak do not depend on the sampling rate. Any timing
  feature (time of flight, windowing, spectral features) must use about 12 MHz, with this caveat.

## 4. Amplitude units

Signal amplitudes are in **raw acquisition units, which are unknown**. The README calls gain "voltage
value", but no calibration is given. All features used here are ratios to a reference recording of
the same specimen and path, so they are **dimensionless**. Gain and excitation settings are not
converted (dividing by 33 or 35 is not justified), and a constant multiplicative factor cancels
only under the assumption stated in `docs/methodology.md`.

## 5. Reproduce

```text
python scripts/dataset_facts.py --data-root "data/2.+Composites/2. Composites"
```
