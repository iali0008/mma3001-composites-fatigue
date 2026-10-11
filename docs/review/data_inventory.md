# Tracked material under `data/` (fix group 2, findings C2 / R3)

Inventory of branch `review-fixes` at `d809925`. Everything here has been tracked since the
initial commit `4f75752`. `data/README.md` is excluded, because it is intended to be tracked. Sizes
are working-copy bytes.

**Dependencies.** No maintained script or test (`scripts/`, `tests/`) reads any file below.
Untracking them changes no workflow, test or recorded result.

**Untracking does not erase.** `git rm --cached` plus a `.gitignore` rule removes files from future
commits and keeps the local copies. They stay in git history (`4f75752` onwards), so anyone with a
clone of the history, or a zip that includes `.git/`, can still recover them. Removing them from
history would need a rewrite, which is out of scope and needs your decision.

## Groups and recommendations

| # | Group | Files | Size | What it is | Recommendation |
|---|---|---|---:|---|---|
| A | Vendored library | `data/audit_stiffness/deps/` (pypdf 6.19.0 and dist-info, 66 files) | 1.73 MB | Third-party PDF library copied in so the old audit could run; BSD licence file included | **Untrack and ignore.** It is available from PyPI, used only by the unmaintained audit, and not project code. If the audit is ever rerun, install `pypdf==6.19.0` instead. |
| B | Extracted third-party text | `data/audit_stiffness/*.pdf.txt`: three README copies (Layup1–3), the Technical Report, and the three papers (STI_9406, STI_9408, Saxena IWSHM 2011) | 0.18 MB | Full text of the dataset's documentation and of copyrighted papers | **Untrack and ignore.** It republishes papers and documentation that `docs/dataset.md` says are not committed; cite them instead. |
| C1 | Raw waveforms | `data/pzt_feasibility/selected_signals.npz` | 2.33 MB | 378 raw 2,000-sample actuator and sensor signals copied from the MAT files (cached by `run_feasibility.py`) | **Untrack and ignore.** This is raw data, which the working rules say is never committed. |
| C2 | Raw logbook dump | `data/audit_stiffness/logbooks.txt` | 0.22 MB | Cell-by-cell dump of every experimental logbook worksheet | **Untrack and ignore.** It is raw experimental records. |
| C3 | Raw structure dump | `data/audit_stiffness/schemas.txt` | 0.08 MB | Folder listings and MAT/strain structure dumps, including byte previews of raw files | **Untrack and ignore.** Mostly raw-file content; it is not needed as evidence. |
| D | Audit outputs (derived) | `data/audit_stiffness/`: `ASSESSMENT.md`, `label_checkpoints.csv`, `specimen_summary.csv`, `metadata_conflicts.csv`, `logbook_remarks.csv`, `pzt_metadata.json`, `strain_channels.csv`, `strain_inventory.csv`, `strain_profile.json`, `inventory.json`, `original_manifest.json`, `source_integrity.json`, `coupon_samples.json` | 1.54 MB | Derived tables and statistics from the label audit. `logbook_remarks.csv` quotes logbook remarks verbatim; `coupon_samples.json` shows a few truncated array values. | **Keep.** This is the evidence behind the label audit (`archive/audit/ASSESSMENT.md`) and the 39-label count. It is derived and small. Document `logbook_remarks.csv` as short quotations from the logbooks. |
| E | Feasibility outputs (derived tables) | `data/pzt_feasibility/*.csv` (15 files, incl. `acquisition_inventory.csv` 6.05 MB of per-path metadata, no signals), `*.json` (`environment`, `verification`, `selection_plan`, `source_hashes_before`) | 6.42 MB | Derived metadata, features and QC tables from the early feasibility study | **Keep**, as historical evidence. Optionally untrack only `acquisition_inventory.csv` (6 MB, regenerable). |
| F | Figures | `data/pzt_feasibility/*.png` (5), `*.svg` (2) | 1.62 MB | Plots of derived features and checks | **Keep.** |
| G | Notebooks | `data/audit_stiffness/audit_review.ipynb`, `data/pzt_feasibility/feasibility.ipynb` (5 embedded images, 1.5 MB) | 1.54 MB | Exploratory notebooks of the early work | **Keep**, labelled historical and unmaintained. Their outputs are not edited. |
| H | Historical code | `data/audit_stiffness/inspect_sources.py`, `summarize.py`; `data/pzt_feasibility/run_feasibility.py`, `requirements.txt`, `ASSESSMENT.md` | 0.07 MB | Scripts and notes of the early audit and feasibility study | **Keep**, labelled unmaintained. Note that `run_feasibility.py` lines 163–172 would recreate the raw-waveform cache locally. |

**Net effect of the recommendation.** Untrack groups A, B and C (76 files, 4.54 MB) and add
ignore rules for them. Keep D–H (46 files, 11.08 MB) of derived evidence and historical code.

## Doc corrections to make after your decision

- **`docs/dataset.md` §1.** Replace "No raw data, logbooks, X-rays or papers are committed" with an
  exact statement of what is tracked, including derived audit tables and short logbook quotations.
  Add that earlier commits still contain the untracked material.
- **`README.md`.** Make the structure table and the "Data download" / attribution text match the
  decision.
- **`data/README.md`.** List what remains under `data/`, mark `audit_stiffness/` and
  `pzt_feasibility/` as historical and unmaintained, and state the history caveat.
