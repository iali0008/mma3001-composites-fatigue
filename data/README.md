# Local dataset (excluded from Git)

Use the composites fatigue dataset distributed through the [NASA Prognostics Center of Excellence repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/). The repository page (accessed 2026-10-11) lists the archive `https://phm-datasets.s3.amazonaws.com/NASA/2.+Composites.zip`, whose name matches this local folder; the download date of the local copy was not recorded. Cite it as: Abhinav Saxena, Kai Goebel, Cecilia C. Larrosa, and Fu-Kuo Chang, "CFRP Composites Data Set", NASA Prognostics Data Repository, NASA Ames Research Center, Moffett Field, CA. No licence is named; see [docs/dataset.md](../docs/dataset.md) for the repository's terms, the label definition and the sampling-rate check.

The download has been moved into this repository. Directory inspection confirmed that all three layups are directly under:

```text
data/2.+Composites/2. Composites/
  Layup1/
  Layup2/
  Layup3/
```

The absolute dataset root on this machine is `D:\Saneeh\Monash\Year 3\MMA3001\Projects\mma3001-composites-fatigue\data\2.+Composites\2. Composites`. Pass that directory, or the repository-relative path above, as `--data-root`. The sibling archive is `data/2.+Composites.zip`. The paths used by this experiment below the dataset root are:

| Specimen | Path relative to `--data-root` |
|---|---|
| L1S11 | `Layup1/L1_S11_F/PZT-data/` |
| L1S12 | `Layup1/L1_S12_F/PZT-data/` |

Run from the repository root after installing `requirements.txt`:

```powershell
.\.venv\Scripts\python.exe scripts/repeat_sensitivity.py --data-root "data/2.+Composites/2. Composites"
.\.venv\Scripts\python.exe -m pytest
```

The sensitivity command first runs the raw-data extractor into a `median_rebuild/` subfolder, checks agreement with the recorded baseline, and then writes the median/first/last comparisons. Since 2026-10-11 its default output is `results/rebuilt/repeat_sensitivity/`; the recorded `results/repeat_sensitivity/` is never overwritten. L2S11 (`Layup2/L2_S11_F/PZT-data/`) is read only by the protocol v2 audit and the one-shot test. It reads the original logbooks `Layup1/L1_S11_F/L1S11.xlsx` and `Layup1/L1_S12_F/L1S12.xlsx` with openpyxl in read-only mode; AppleDouble files beginning `._` are not workbooks and are skipped. No source workbook is saved.

Preserve every downloaded file. Explicit `.gitignore` rules `/data/2.+Composites/` and `/data/2.+Composites.zip` exclude the entire download, including logbooks, X-rays, text, PDFs, metadata and archives. These clarify the pre-existing directory-wide exclusion. `data/README.md` stays tracked. The analysis checks every original file against Git's ignore rules and verifies that none under these raw paths is tracked or staged.

Source preservation is checked through sizes and modification timestamps for the complete download wrapper and archive; all surveyed L1S11/L1S12 MAT files additionally have before/after SHA-256 checks and must match the recorded baseline. Both logbooks and all recorded baseline files are also hash-checked. Other source files are inventoried, not content-hashed. See `results/repeat_sensitivity/verification.json` and `source_inventory.json`.

The first audit reports 1,495 PZT MAT files across 13 specimen folders. Only three specimens contain populated scalar stiffness-index candidates; the core modelling experiment uses two from Layup 1. See `archive/audit/ASSESSMENT.md`. Earlier audit outputs are under `data/audit_stiffness/` and feasibility work under `data/pzt_feasibility/`. Both are historical and unmaintained; their path assumptions and analysis conventions differ, and no maintained script or test reads them. Since 2026-10-12 they contain only derived material: audit tables (including short verbatim logbook remarks in `logbook_remarks.csv`), feasibility tables, figures, notebooks and scripts. The vendored pypdf copy, extracted text of the dataset documentation and papers, the full logbook dump (`logbooks.txt`), raw structure dumps (`schemas.txt`) and raw waveform excerpts (`selected_signals.npz`) were untracked and git-ignored; local copies may exist, and **earlier commits (from `4f75752`) still contain them**. `run_feasibility.py` would recreate the waveform cache locally if rerun.

The published index values and derived tables are provided as small reproducibility artefacts; no raw MAT data, logbook workbook, X-ray, PDF or paper text is in the current tree. This project's code licence does not grant rights over the source dataset or research papers. Review the dataset's supplied use and citation terms before redistributing additional material.
