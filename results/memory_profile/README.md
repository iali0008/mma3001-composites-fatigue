# Peak traced memory (2026-10-24)

Produced by `scripts/memory_profile.py --data-root "data/2.+Composites/2. Composites"` (default
`--repeats 3`), written to `results/rebuilt/memory_profile/` and copied here unchanged. The script
was run from the uncommitted `docs-polish` working tree based on `c2c48d5` (the script itself was
new and not yet committed). Windows 11, CPython 3.13.3, NumPy 2.3.0, SciPy 1.17.1,
scikit-learn 1.9.0 (`summary.json`).

**What the number is.** Peak traced allocations, including allocations registered with
`tracemalloc`; not total process RAM, and not necessarily all native-library allocations.

**How it was measured.** Each repetition ran in a fresh Python process. Modules were imported, and
for fit+predict the saved features (`results/baseline/checkpoint_features.csv`) were loaded,
before `tracemalloc.start()`.

| Workload | What runs inside the measurement | Peaks (bytes) | Median |
|---|---|---|---:|
| `extraction` | `exploratory_regression.main` (serial default) on L1S11 and L1S12, writing into a temporary folder; outputs checked against `results/baseline` afterwards (all matched) | 9,968,630; 9,967,517; 9,963,917 | 9,967,517 (9.51 MiB) |
| `fit_predict_selected` | Selected settings (LinearRegression, path 1→7), fit on one Layup 1 specimen and predict both, both validation directions | 84,535; 84,307; 84,590 | 84,535 (0.081 MiB) |
| `fit_predict_v1_all` | All six v1 comparators (five MLP seeds), both validation directions | 185,865; 185,993; 182,152 | 185,865 (0.177 MiB) |

- **Preprocessing in fit+predict.** Included: converting rows to arrays and the training-only
  scaling inside each model pipeline. Reading the CSV is excluded.
- **Fixed settings.** Model settings are the frozen ones in `config/model_comparison.json`, and BLAS
  threads are limited as in the recorded v1 timings. Nothing was tuned.
- **L2S11 not used.** No L2S11 file was read, and `protocol_v2_test.py` was not run.
