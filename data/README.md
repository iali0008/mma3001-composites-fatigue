# Local dataset (excluded from Git)

Use the composites fatigue dataset distributed through the [NASA Prognostics Center of Excellence repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/). Retain the citation and provenance in the downloaded documentation. The exact download URL/release identifier should be recorded by the student from the original download; none is invented here.

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
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The sensitivity command first runs the unchanged raw-data extractor into `results/repeat_sensitivity/median_rebuild/`, checks agreement with the recorded baseline, and then writes the median/first/last comparisons into `results/repeat_sensitivity/`. It reads the original logbooks `Layup1/L1_S11_F/L1S11.xlsx` and `Layup1/L1_S12_F/L1S12.xlsx` with openpyxl in read-only mode; AppleDouble files beginning `._` are not workbooks and are skipped. No source workbook is saved.

Preserve every downloaded file. Explicit `.gitignore` rules `/data/2.+Composites/` and `/data/2.+Composites.zip` exclude the entire download, including logbooks, X-rays, text, PDFs, metadata and archives. These clarify the pre-existing directory-wide exclusion. `data/README.md` stays tracked. The analysis checks every original file against Git's ignore rules and verifies that none under these raw paths is tracked or staged.

Source preservation is checked through sizes and modification timestamps for the complete download wrapper and archive; all surveyed L1S11/L1S12 MAT files additionally have before/after SHA-256 checks and must match the recorded baseline. Both logbooks and all recorded baseline files are also hash-checked. Other source files are inventoried, not content-hashed. See `results/repeat_sensitivity/verification.json` and `source_inventory.json`.

The first audit reports 1,495 PZT MAT files across 13 specimen folders. Only three specimens contain populated scalar stiffness-index candidates; the core modelling experiment uses two from Layup 1. See `archive/audit/ASSESSMENT.md`. Earlier audit scripts and notebooks are now present under `data/audit_stiffness/`, with feasibility work under `data/pzt_feasibility/`. Their historical path assumptions and different analysis conventions need review before reuse; they do not govern the fixed regression experiment.

The published index values and derived tables are provided as small reproducibility artefacts. This project's code licence does not grant rights over the source dataset or research papers. Review the dataset's supplied use and citation terms before redistributing additional material.
