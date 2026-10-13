# Progress and decisions

This is a consolidated record of work reported in the project conversation and uploaded outputs, not a claim of contemporaneous Git commits.

## Completed

- Completed the Week 5 four-family comparison on 2026-09-25 under a protocol/configuration written before new scores (`docs/model_comparison_protocol.md`, `config/model_comparison.json`). Used identical median features, targets, checkpoints and specimen splits, plus log-cycle OLS and training-mean Dummy controls. No evaluation-specimen tuning or best-seed selection.
- Corrected reference auditing to use acquisition/waveform criteria independently of target availability; both original cycle-1 references and exact denominators are preserved. Input/target preprocessing is training-only, with predictions returned to published-index units.
- LinearRegression has the lowest evaluation MAE in L1S11 -> L1S12 (0.050532); the three-unit MLP has the lowest in reverse for all five seeds (median 0.020942; range 0.020936--0.021264). There is no single winner across directions. No convergence warnings occurred. Full train/evaluation MAE, RMSE, R², residuals, plots and timings are in `results/model_comparison/`.
- All 19 scientific/reproduction tests passed (66 since the October 2026 work; see the session log). Sklearn linear/log-cycle predictions match recorded OLS within tolerance. All four plot images were visually checked. Historical baseline/sensitivity artifact hashes and surveyed original MAT hashes remain unchanged; original raw files remain ignored and untracked/unstaged.
- Measured model fit and batch-prediction runtime with one warm-up, 15 repetitions and 100 prediction calls per repetition. Separately profiled the raw workflow: MAT decoding was the largest self-time cost. Added bounded ordered four-thread prefetch (`--workers 4`, serial default). Three alternating unprofiled pairs showed median 12.769 s serial versus 7.771 s prefetch (1.643x), with every output file byte-identical. Memory usage was not profiled.

- Chose an existing public composites dataset; no new experimental data collection.
- Audited local dataset labels, including missing zeros, repeated labels and strain limitations. Earlier audit implementation and notebooks are now present under `data/audit_stiffness/`.
- Inspected one signal and recorded an unresolved factor-of-ten timing discrepancy.
- Compared two recordings and extracted mean-centred RMS / peak-to-peak features.
- Aggregated L1S11 checkpoints with consistent settings.
- Checked the same settings on L1S12: no exact match because gain/excitation differ. The empty result is preserved in the archive, not presented as the current dataset.
- Defined specimen-specific constant settings and early-reference ratios.
- Ran three OLS models in both transfer directions; kept missing labels and the label jump unchanged.
- Collected code/results into this repository, made raw-data paths configurable and added an independently calculated replay plus regression/leakage checks.
- Connected `origin` to `https://github.com/iali0008/mma3001-composites-fatigue.git`; the existing initial commit is `4f75752`. This task made no commit or push.
- Located the moved NASA download at `data/2.+Composites/2. Composites/`, directly containing all three layups. Explicit ignore rules cover the complete wrapper and sibling archive; `data/README.md` stays tracked. Original dataset files are neither tracked nor staged.
- Reran the portable raw-data pipeline and reproduced recorded median features, references, predictions and metrics before sensitivity fitting.
- Completed median/first/last repeat sensitivity under `results/repeat_sensitivity/`, holding all experiment boundaries and reference denominators fixed. Original logbook timestamps establish order for all 51 eligible recordings; no filename fallback was needed.
- Found that two features remain best for first repeats in both directions and last repeats in L1S11 -> L1S12. Last repeats in L1S12 -> L1S11 favour RMS-only (MAE 0.031399, RMSE 0.034864) over two features (0.033315, 0.038596). Two-feature errors rise relative to medians in all first/last comparisons; see methodology for absolute and percentage changes.
- Validation on 2026-09-25: all 12 baseline/sensitivity tests passed with Python 3.13.3, NumPy 2.3.0, SciPy 1.17.1 and openpyxl 3.1.5. Independent unscaled OLS agrees with every centred-QR fit. All 2,607 original wrapper/archive files are ignored and retain sizes/mtimes; surveyed MAT files match baseline SHA-256 hashes, and logbook/baseline hashes are unchanged. `git diff --check` passed; nothing is staged.

## Remaining

- [ ] Review the already imported audit/feasibility code for portability and bundled dependencies before relying on those historical workflows. Their reference conventions differ from this regression.
- [ ] Record the exact source download URL/version and check required data attribution.
- [ ] Confirm the scoped alternative project with the teaching team if not already approved; approval is not established by this repository.
- [ ] Investigate the physical sampling-rate discrepancy if adding spectral features or time-of-flight.
- [ ] Write the student's interpretation, limitations and AI reflection; align final deliverables with the actual project brief.
- [ ] Obtain additional independent specimens for a future frozen-model validation; neither current specimen is an untouched final test set.
- [ ] Measure peak memory or cross-hardware performance only if a concrete implementation requirement needs it; this task measured runtime and profiled CPU call costs, not memory.

## Working conventions

Preserve `results/baseline` as the first recorded experiment. Put changed analyses in a separate output directory. Commit code, relevant small outputs and an explanation of each material change. Do not edit original experimental files, fill missing labels to enlarge the sample, or select a new feature based on favourable evaluation results without disclosing exploratory selection.

## Session log

Newest entries last. Every Claude session (Claude Code in VS Code or claude.ai) appends an entry here; `CLAUDE.md` holds the standing decisions and plan.

- 2026-10-11 (claude.ai review session): Reviewed all scripts and tests; the 23 tests pass on Linux (Python 3.13.16, NumPy 2.5.3, scikit-learn 1.9.1). No errors found that change reported numbers. Confirmed from the dataset documentation that only L1S11, L1S12 and L2S11 carry stiffness labels, and that the stored 1.2e6 Hz sampling rate is a hard-coded placeholder (actual rate likely ~12 MHz). Decisions: keep the research question; L2S11 becomes the held-out test set; add multi-path features and an unlabelled L1S11 (>100k cycles) sanity check; drop L1S18/L1S19. Code issues and the full plan are recorded in `CLAUDE.md`. Next step: write and commit protocol v2 before computing any new scores.
- 2026-10-11 (Claude Code, VS Code): Plan step 1, protocol v2. Read CLAUDE.md, this log, README,
  methodology, v1 protocol, INTERPRETATION, ASSESSMENT and the project brief
  (`MMA3001_2026_Project_Brief.pdf`, untracked at the repo root). Wrote
  `scripts/audit_acquisition_v2.py`, a label-blind metadata/waveform audit (it deletes the label
  field on load; no model or score), with outputs in `results/protocol_v2_audit/`. Findings: all 382
  files of L1S11/L1S12/L2S11 share one path-slot order and the full 36-pair grid at 150 kHz;
  CHANGEPATH.m moves IDs with signals; envelope-peak timing supports cross-specimen ID consistency
  (Spearman 0.40–0.76) but cannot prove it; gain/amplitude are per pair, constant over time in
  L1S11/L1S12, changed on 9 L2S11 pairs only at cycles 0–1; L2S11 cycles 1–2 are static load
  ramps and its fatigue mean load is 4.571–4.588 kips; pair 1→7 (v1 baseline) peaks at a fixed early
  sample (~292) in all three specimens, suggesting crosstalk-like early energy. Wrote
  `docs/protocol_v2.md` and `config/protocol_v2.json`: joint label-blind eligibility, L2S11 load
  window 4.53–4.63 kips (reference expected at cycle 3, so the −0.012 cycle-1 label is never
  scored), multi-path input = median over 36 per-pair reference ratios, v1 models unchanged,
  selection by lowest worst-direction validation MAE (ties within 0.0005 → simpler model, then
  single path), pooled L1S11+L1S12 final model, one guarded L2S11 run with log-cycle/Dummy
  controls, L1S11 125k–227k sanity criteria C1–C3. No v2 score computed. Tests: 23/23 pass
  (unittest, Windows, Python 3.13.3). Next: Sans reviews protocol (★), then step 2 code fixes.
- 2026-10-11 (Claude Code, VS Code): Sans approved protocol v2. Decisions: (1) log-cycle OLS and
  Dummy stay in the single L2S11 run as fixed, non-selectable reference points; no code reads
  L2S11 labels before step 4. (2) No time-window amendment; report the path 1→7 crosstalk-like
  finding in limitations/discussion, noting that relative PTP on crosstalk-dominated paths mostly
  tracks crosstalk (v1 L1S11 non-reference relative PTP 0.879–1.029, from
  `results/baseline/checkpoint_features.csv`). (3) Brief PDF git-ignored, never committed. (4) L2S11
  scores 8 checkpoints (10, 1,000, 10,000, 20,000–60,000 cycles). Recorded as approval notes in
  `docs/protocol_v2.md` (frozen settings and `config/protocol_v2.json` unchanged) and in CLAUDE.md.
- 2026-10-11 (Claude Code, VS Code): Plan step 2, code fixes a–d on branch `code-fixes`.
  (a) The extractor chooses the reference label-blind (earliest acquisition-eligible checkpoint).
  (b) `exploratory_regression.py` refactored into documented functions plus `main()`; new
  `tests/test_extraction.py` (sine RMS/PTP, eligibility rules, label-blind reference, missing
  labels, integrity checks, guards). (c) `require()` in `scripts/common.py` replaces asserts; tests
  pass under `python -O`. (d) Constants moved to `config/experiment_v1.json`. All workflow scripts
  take `--output`, default to git-ignored `results/rebuilt/`, and refuse recorded folders.
  `scripts/verify_reproduction.py` reran baseline, repeat sensitivity, model comparison and
  coverage: 50 files byte-identical, 4 equal in content (CRLF line endings or timestamps), 2 timing
  files skipped (`results/reproduction_check/report.json`). Profile and benchmark scripts also ran
  and passed their baseline-equivalence gates (timings not recorded). Updated test counts (e) in
  methodology, INTERPRETATION and progress. Tests: 49/49 pass (unittest, Windows, Python 3.13.3,
  NumPy 2.3.0, scikit-learn 1.9.0). Note: `pyflakes` was used locally for linting only.
- 2026-10-11 (Claude Code, VS Code): Plan step 3, protocol v2 validation on L1S11 ↔ L1S12 (L2S11
  not opened). A feature-only check first confirmed that v2 single-path features equal the v1
  baseline exactly. `scripts/protocol_v2_validation.py` (commit 6ccee92) then fitted the six v1
  comparators on both input sets. Reproduction gate: 500/500 single-path predictions equal the
  recorded v1 values (max difference 0.0). Worst-direction validation MAE: single-path linear
  0.0505 (selected), single-path MLP 0.0782, multi-path MLP 0.0888, multi-path linear 0.0903; no
  tie. Multi-path improved reverse-direction MAE for tree, SVR and MLP (MLP 0.0113) but not the
  worst direction; multi-path linear extrapolates to −0.275 because multi-path ratios barely
  overlap between specimens. Selection frozen in `results/protocol_v2/selection.json`; details in
  `results/protocol_v2/validation/README.md`. Disclosure for the report: single-path scores were
  known (v1) when the rule was written. Tests: 63/63 pass. Next: Sans reviews (★), then step 4.
- 2026-10-11 (Claude Code, VS Code): Plan step 4, single L2S11 test (commit 52169ab, clean tree).
  Before the run, the script was smoke-tested on a scratch copy with L1S12 standing in for L2S11
  (disclosed: this precomputed the L2S11-independent sanity outcome). Frozen LinearRegression
  (single path 1→7, refit on 25 pooled checkpoints): reference cycle 3, 8 scored checkpoints,
  cycle-1 −0.012 reported not scored. L2S11 MAE 0.0374 (RMSE 0.0442, R² −2.27, every residual
  negative) versus log-cycle 0.0946 and Dummy 0.1015, so it beats both controls by the predeclared
  rule. Coverage: all 16 non-reference L2S11 checkpoints outside the pooled training hull. L1S11
  sanity check FAILS on C1 (late mean 0.083 < 0.114 at 100k); C2/C3 pass; predictions drop at 177k.
  Post hoc (`scripts/post_hoc_step4.py`, labelled as such): a constant-zero predictor has MAE
  0.0362 (< 0.0374); Spearman(prediction, label) 0.19; L2S11 path 1→7 ratios stay within
  0.985–1.018 (RMS) and 1.001–1.015 (PTP); L1S11 ratios jump beyond the training range at 177k.
  Conclusion for the report: no demonstrated transfer to L2S11; the specimen-specific
  amplitude-to-damage mapping is the main limitation. Details in
  `results/protocol_v2/test_L2S11/README.md`. Tests: 66/66 pass. Next: Sans reviews (★), then
  steps 5–6.
- 2026-10-11 (Claude Code, VS Code): Post hoc follow-ups requested after step 4 (step 4 itself
  unchanged). (1) `scripts/post_hoc_logbook_l1s11.py`: the L1S11 logbook records no re-mounting,
  settings, cabling or load change at 175k–177k; the 177k condition order is reversed and a
  177,309-cycle entry exists; logged timestamps go backwards in 4 places. All 36 paths' RMS ratios
  rise 175k→177k (median ×1.33, min ×1.09) with unchanged 1→7 excitation, suggesting a global
  coupling/mounting change (interpretation). C1 fail stands. Side finding flagged: the recorded
  repeat-sensitivity first/last order for L1S11 80,000 cycles may be reversed by a backward
  timestamp (historical result unchanged). (2) Prediction hash: not regenerated; the LF-normalised
  hash (`9cc12f55…`) is recorded beside the original CRLF hash (`4ac9647b…`). Report framing,
  recommendations and the predict-zero lesson recorded in CLAUDE.md and the step 4 README.
- 2026-10-11 (Claude Code, VS Code): Plan step 5. New `docs/dataset.md` resolves the open dataset
  questions with page/line citations, backed by `scripts/dataset_facts.py` →
  `results/dataset_facts/facts.json`. Index: hand-typed STM tables copied by cycle (Technical Report
  PDF p. 7 lines 25–57; p. 8 lines 108, 133; §3.1 step 4.3 p. 5); T22 jump 0.118→0.247 at 90k;
  best interpretation 1 − E/E₀ (not stated anywhere); paper [4] defines D = E_eff/E₀ (p. 3 eq. 6),
  D_max 0.88 (p. 6). Strain files hold only strain1–4 (80/57/69 files), so labels cannot be
  recomputed. Sampling rate: stored 1.2e6 is a constant (line 102); FFT at all 7 frequencies
  implies 11.69–12.00 MHz; 150 kHz burst median 366 samples. Units: raw, unknown; ratios
  dimensionless. Provenance: NASA PCoE repository citation and download URL recorded (accessed
  2026-10-11); no licence named, acknowledge-and-own-risk terms only; data.nasa.gov entries are
  paper records with "License not specified". `data/README.md` updated.
- 2026-10-11 (Claude Code, VS Code): Plan step 6, repository deliverables. (f) NumPy-style
  docstrings on all 105 functions and every module; black (100 columns, quotes kept) applied, long
  strings split into adjacent literals with identical values; behaviour verified unchanged (66
  tests incl. `-O`; reproduction check 50 identical / 4 equal-content / 2 timing-skipped; v2 audit
  and features identical). (g) `requirements-lock.txt` pins the working environment (NumPy 2.3.0,
  SciPy 1.17.1, scikit-learn 1.9.0, Matplotlib 3.10.6, …); `requirements-dev.txt` adds pytest,
  pytest-html, pdoc; `pyproject.toml` holds black/pytest settings. HTML API docs:
  `scripts/build_docs.py` (pdoc, local paths scrubbed) → `docs/html/` (18 modules). Test runner is
  now pytest; reports in `results/test_report/` (junit.xml, report.html): 66 passed. README
  rewritten (purpose, headline, inputs/outputs, structure, setup, download, reproduction table,
  tests/docs, limitations, attribution, AI-use pointer). Fresh-clone verification: cloned
  `code-fixes` to a temp folder, new venv from the lock (versions match exactly), raw data from the
  original location: replay OK, 66 tests pass, reproduction check 10 identical / 40 equal-content
  (LF checkout vs CRLF output) / 3 equal-except-environment (data path, git check, checkout byte
  hashes; new category added to `verify_reproduction.py`) / 3 skipped, audit identical
  (`results/reproduction_check/fresh_clone_report.json`). Note: a fresh install from the ranged
  requirements resolves newer versions (e.g. NumPy 2.5.4); only the lock is verified. Dev tools
  black, pyflakes, pytest-html and pdoc were installed in the global Python. Test counts (e) updated.
  Next: step 7 report draft (★).
- 2026-10-12 (Claude Code, VS Code): Dev tooling: black and pyflakes added to `requirements-dev.txt`
  and the lock (with black's dependencies); README directs all commands to the project venv; two
  unused test imports removed so pyflakes passes. A clean venv from the lock reproduces the package
  set exactly and passes black, pyflakes and 66 tests; its docs build matches the committed
  `docs/html` except for a pdoc show-value toggle that depends on path length. Review pack written
  in `docs/review/` (script map, brief checklist, confidence and risks). Flagged for decision:
  `data/audit_stiffness/` (text copies of the NASA docs and papers, vendored pypdf) and
  `data/pzt_feasibility/selected_signals.npz` (raw waveform excerpts) are tracked since the initial
  commit; `main` is behind the unpushed branches; CLAUDE.md fact-4 numbers lack repo outputs.
  Not pushed. Waiting for Sans's review before step 7.
- 2026-10-12/13 (Claude Code, VS Code): Review fixes on branch `review-fixes` (off `code-fixes`,
  not pushed or merged). Two independent reviews of `d9c7372` are committed in `docs/review/`
  (`independent_review.md`, Codex, R1–R9; `claude_ai_review.md`, claude.ai, C1–C9). No
  experiment was rerun, L2S11 was not rescored, and no computed file under `results/` changed.
  Only the hand-written README notes in `results/protocol_v2/{validation,test_L2S11,sanity_L1S11}`
  were edited, with dated review-correction notes. Sans's decisions:
  - data inventory: untrack groups A–C, keep D–H (`docs/review/data_inventory.md`);
  - v2 route: a validation replay only, with no L2S11 replay;
  - fact-4 numbers: mark "do not cite"; no diagnostic script;
  - the replay could be run once on real data.

  Results:
  - The validation replay matched the record (12 identical, 1 equal_content, 0 different; all 141
    recorded files under `results/` unchanged).
  - `verify_reproduction.py` after the comment pass: 49 identical, 4 equal_content, 3 skipped,
    0 different.
  - The syntax tree of every script is unchanged by the comment pass.
  - Tests: 100 passed, 75 subtests (was 66).
  - HTML docs and pytest reports rebuilt.

  Corrections to commit messages (history not rewritten):
  - `0cb4815` says "101 passed"; the correct count is 100.
  - `b9c4934` says "about 140 short inline comments"; the correct figure is 93 comments
    (140 comment lines added; 58 → 198).

  | Finding | Outcome | Where |
  |---|---|---|
  | R1 `--work` could delete raw data or v2 results | fixed | `d809925` (`check_work_folder`, 7 tests) |
  | R2 v2 gate accepted duplicate/missing rows | fixed | `0cb4815` (one-to-one keys, specimen and target checks, 7 negative tests, recorded run passes) |
  | R3 raw excerpts and third-party text tracked | fixed (untracked; still in history from `4f75752`) | `d02cd25` |
  | R4 timestamps treated as chronology | documented | `56320f5` ("by logged timestamp, chronology unresolved", L1S11 80k cited) |
  | R5 reproduction section not executable | fixed | `a40e40e`, `223a76d` (sections a/b/c, write locations, `--replay`) |
  | R6 conclusions too general/causal | fixed (wording) | `56320f5` |
  | R7 v1 flags but does not exclude invalid signals | documented, behaviour kept | `0cb4815` (pinned by tests; 51 eligible v1 recordings unflagged) |
  | R8 tests missing or not discriminating | fixed | `0cb4815` (gate, guard, label order, aggregation order, v2 sampling/length/load-window cases) |
  | R9 fact-4 numbers unsupported; SVR "cannot succeed" | documented | `56320f5` ("not reproduced; do not cite"; SVR "observed to revert towards the training mean") |
  | C1 v2 rerun route impossible | fixed | `223a76d` (validation replay; L2S11 test deliberately not rerunnable) |
  | C2 committed material contradicts docs | fixed | `d02cd25` |
  | C3 headline over-generalised | fixed (wording) | `56320f5` |
  | C4 inline comments almost absent | fixed | `b9c4934` |
  | C5 FLOPs/memory not addressed | documented | `b9c4934` (`docs/methodology.md`, memory not measured) |
  | C6 = R9 | documented | `56320f5` |
  | C7 controls' `input_set` label differs | documented | `56320f5` (validation README note; nothing regenerated) |
  | C8 = R8 (guard, label order, gate) | fixed | `0cb4815` |
  | C9 chat summary misreported multi-path effect | declined: no repo change needed | Repo files were already correct; use `candidates.csv`, not chat summaries, for the report |

  Also flagged in CLAUDE.md fact 4 (beyond the request): the MLP–linear correlation, Spearman and
  RMS-only slope numbers also have no repo output (review pack R3), so they are marked "verify
  before citing". Next: Sans reviews `review-fixes`, merges to `main` and pushes; then step 7
  (report draft).
