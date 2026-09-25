# External dataset

Use the composites fatigue dataset distributed through the [NASA Prognostics Center of Excellence repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/). Retain the citation and provenance in the downloaded documentation. The exact download URL/release identifier should be recorded by the student from the original download; none is invented here.

The existing download is under `D:\Saneeh\Monash\Year 3\MMA3001\Projects\ll`. The `--data-root` argument must point to its extracted `2. Composites` directory, **not necessarily `ll` itself**. The expected paths below it are:

| Specimen | Path relative to `--data-root` |
|---|---|
| L1S11 | `Layup1/L1_S11_F/PZT-data/` |
| L1S12 | `Layup1/L1_S12_F/PZT-data/` |

To locate the parent directory on Windows:

```powershell
Get-ChildItem -LiteralPath "D:\Saneeh\Monash\Year 3\MMA3001\Projects\ll" -Directory -Recurse -Filter Layup1 | Select-Object FullName
```

Use the parent of the matching `Layup1` directory. Preserve the downloaded MATLAB files, workbooks and documentation. The project only reads them; do not upload the large archive to GitHub. `.gitignore` excludes common dataset folders, MAT files and compressed archives.

The first audit reports 1,495 PZT MAT files across 13 specimen folders. Only three specimens contain populated scalar stiffness-index candidates; the core modelling experiment uses two from Layup 1. See `archive/audit/ASSESSMENT.md`. The audit's notebook and full audit scripts were run locally but have not been supplied in this repository: import them from `audit_stiffness` later if needed, preserving provenance.

The published index values and derived tables are provided as small reproducibility artefacts. This project's code licence does not grant rights over the source dataset or research papers. Review the dataset's supplied use and citation terms before redistributing additional material.
