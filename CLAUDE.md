# CLAUDE.md — shared project brief for every Claude session

This file is the shared memory between Claude sessions on this project (Claude Code in VS Code
and claude.ai chats). Sessions do not share conversation history, so:

- **Read this file, then `docs/progress.md`, at the start of every session.**
- **Append a dated entry to `docs/progress.md` after every working session** (what changed, results,
  test counts, open questions). Update this file only when a decision or established fact changes,
  and note the change in `docs/progress.md`.
- Related claude.ai doc (decision record): "Why the Project Uses Two Labelled Specimens",
  https://claude.ai/code/artifact/3ad004f8-eb3e-4857-860a-0209a04d0912

Project: MMA3001 (Monash, Numerical Methods & Machine Learning), student Sans. Repository:
`iali0008/mma3001-composites-fatigue` (private). Background reading before working:
README.md, docs/methodology.md, docs/progress.md, docs/model_comparison_protocol.md,
results/model_comparison/INTERPRETATION.md, archive/audit/ASSESSMENT.md and the project brief
(ask Sans for it if it is not in the repo). Raw NASA data is at
`data/2.+Composites/2. Composites/` (git-ignored; never modify or commit it). The dataset's own
documentation (README.pdf, Technical Report, papers) is in a Documentation folder in the dataset.

## Decisions already made (do not reopen without Sans)

Recorded 2026-10-11.

- Keep the research question: can simple ultrasonic (PZT) features estimate the published
  stiffness-degradation index, using a regression model trained on another specimen? This is an
  exploratory feasibility study; partial success reported honestly is acceptable under the brief.
- Labelled specimens in the whole dataset: L1S11, L1S12, L2S11 only (39 labels in total; the other
  specimens hold placeholder zeros or have no strain gauges). **L1S18 and L1S19 are not used at all.**
- Split: L1S11 and L1S12 remain the train/validation pair (train on one, validate on the other,
  both directions, as now). **L2S11 is the held-out test set** (9 labelled checkpoints, cycles
  1–60,000, includes a negative value −0.012 at cycle 1). Under the protocol v2 eligibility rules
  **8 checkpoints are scored**: 10, 1,000, 10,000 and 20,000–60,000 cycles (cycle 10 has a single
  eligible recording). Cycle 1 is a load ramp outside the 4.53–4.63 kip window, so −0.012 is
  never scored; the reference is cycle 3. It is cross-layup and its labels were seen in the earlier
  audit, so describe it as "held out from model development", not "untouched". No code reads
  L2S11 labels before step 4; score it exactly once, after the final model is frozen and committed,
  with log-cycle OLS and Dummy as fixed, non-selectable reference points in the same run.
- Add multi-path sensor features as better inputs (not as extra rows).
- Add an unlabelled sanity check on L1S11 checkpoints after 100,000 cycles (plausibility only).
- Never multiply sample size by paths, repeats or boundary conditions as if they were independent
  labels; never random-split recordings; no label interpolation; missing labels stay missing
  (including L1S12 at 20,000 cycles).
- Do not switch models based on evaluation scores. Log-transformed features were found post hoc to
  score better on L1S11/L1S12; they are NOT adopted because that was found after seeing results.

## Established facts (from the 2026-10-11 review; verify, then use)

1. **Sampling rate.** The stored 1.2e6 Hz is hard-coded by the curators' conversion script
   (Technical Report, Appendix A, NEWFILEDEF.m line 102: `path_data(i).sampling_rate=1.2e6`), not
   measured. The 150 kHz actuator signal has exactly 80 samples per period (FFT peak bin 25 of
   2000), implying ~12 MHz; the burst spans ~360 samples, consistent with a ~5-cycle tone burst.
   RMS/PTP features are unaffected; any timing claim must use 12 MHz with this caveat.
2. **Stiffness index.** README: "stiffness value obtained from the strain-gages". Technical Report
   Appendix A shows hand-typed STM tables per coupon, starting at 0 at cycle 0, copied into every
   PZT file at that cycle (`STM(2,ind2)`, line 133); step 4.3 of section 3.1 prescribes zero-filled
   tables when no stiffness data exists. Best-supported interpretation: normalised stiffness loss
   1 − E/E0 relative to the pre-cycling specimen; not confirmed by any document. The Chiachío papers
   define D = E_eff/E0 with Dmax = 0.88 — note the sign-convention difference. Example table T22
   (not in the download) jumps 0.118 → 0.247 at 90k cycles, so the L1S12 jump at 30k is not unique.
3. **Strain-file links.** `coupon.straingage_data.file_location` names the strain files behind each
   label (e.g. `L1_S12_S09_STRAIN_*` at cycle 1, `L1_S12_F17_*` at 50k). Converted strain files hold
   only strain1–4 arrays (no load), so the index cannot be independently recomputed from them.
4. **Model-choice evidence (existing results).** LinearRegression has the lowest mean and
   worst-case evaluation MAE across both directions (0.040 / 0.051 vs MLP 0.050 / 0.078); this
   aggregation was not predeclared. 8 of 12 L1S12 targets (≥30k cycles, 0.233–0.246) exceed
   L1S11's maximum target 0.128, so the tree (max prediction 0.116) and Dummy cannot reach them
   forward; RBF SVR is not bounded that way but was observed to revert towards the training mean.
   References are single recordings.
   **Not reproduced in the repo; do not cite** (claude.ai review, no script or output; Sans
   declined a diagnostic, 2026-10-13): repeat spread at a checkpoint up to 13% (L1S11) and 29%
   (L1S12); a ±5% reference change moving linear MAE by ~±0.006.
   **No repo output either; verify before citing** (review pack R3,
   `docs/review/confidence_and_risks.md`): MLP predictions correlate 0.95–0.99 with linear ones;
   Spearman(relative PTP, index) +0.61 on L1S11 vs −0.20 on L1S12; RMS-only slope −0.28 vs −0.74.
5. All 23 existing tests passed on Linux (Python 3.13.16, NumPy 2.5.3, scikit-learn 1.9.1).

## Protocol v2 (approved 2026-10-11)

`docs/protocol_v2.md` and `config/protocol_v2.json` were committed (47b9047) before any v2 score
and approved by Sans. Full 0–1,999 sample window for both input sets, no time-window amendment.
Path 1→7 shows a fixed early (crosstalk-like) peak in all three specimens; report it in
limitations/discussion. PTP is set by the largest swing, so on crosstalk-dominated paths relative
PTP mostly tracks crosstalk; this may explain why v1 L1S11 PTP ratios stay near 1 (0.88–1.03) and
why PTP behaves inconsistently across specimens (interpretation only, no design change).
`MMA3001_2026_Project_Brief.pdf` (repo root) is git-ignored and never committed.

## Step 4 outcome and required framing (Sans, 2026-10-11)

- Headline everywhere (reworded 2026-10-13 after reviews C3/R6): **no evidence that the frozen
  model transfers to L2S11.** The frozen model (L2S11 MAE 0.0374)
  beats log-cycle (0.0946) and Dummy (0.1015) only because the controls carry Layup 1's higher
  target level; the post hoc predict-zero baseline (MAE 0.0362) is slightly better. Always state
  the predeclared comparison and the zero baseline together.
- Observations: path 1→7 barely responds on L2S11; multi-path features change strongly but on
  specimen-specific scales. The model predicts about zero when features are unchanged, so the
  failure is in the feature, not the regression. Crosstalk, mounting/coupling and specimen effects
  are hypotheses consistent with the data, not established causes. Do not claim that amplitude
  features cannot transfer in general: one frozen model was tested on one specimen.
- Recommendations: features isolating the transmitted wave (S0 windowing, time of flight, ΔPSD as
  in Saxena et al. 2011), more labelled specimens, or per-specimen calibration.
- Lesson (methods and AI reflection): a "no damage" (predict-zero) baseline should have been
  predeclared alongside the Dummy.
- L1S11 sanity check: C1 FAIL stands. Post hoc: the 177k jump appears on all 36 paths with
  unchanged excitation (consistent with a global coupling/mounting change; not confirmed); the
  logbook has no remark and its dates go backwards in 4 places.
- Repeat sensitivity: first/last variants are endpoint selection **by logged timestamp, chronology
  unresolved** (e.g. L1S11 80k: `_1_2` dated 14 July is selected before `_1_1` dated 20 July).
  Historical selections stay unchanged.

## Code issues to fix (from the 2026-10-11 review)

Status 2026-10-11: a–d fixed on branch `code-fixes` (historical results verified by
`scripts/verify_reproduction.py`); e, f, g done in step 6 (66 tests, pytest).

a. `scripts/exploratory_regression.py` still selects the reference from LABELLED checkpoints
   (unlabelled recordings are dropped before the earliest checkpoint is chosen);
   `model_comparison.py` only audits that a label-blind rule gives the same result. Make reference
   selection label-blind in the extraction itself.
b. `exploratory_regression.py` runs at import (top-level argparse/logic), so feature extraction is
   untested. Refactor into documented functions + `main()`; add unit tests (sine of amplitude A →
   RMS = A/√2, PTP = 2A; eligibility filters; label-blind reference choice; missing labels).
c. Replace `assert`-based integrity checks with `require()` (asserts vanish under `python -O`).
d. Move specimen-specific constants (gain/excitation per specimen, expected checkpoint counts 13/12,
   hull counts 12/11, the 0.233175942 jump value) into config. Historical frozen experiments must
   still reproduce exactly.
e. Stale docs: methodology.md, progress.md and INTERPRETATION.md say 19 tests; update counts.
f. Docstrings: 32 of 41 functions have none; use NumPy-style docstrings everywhere (parameters,
   returns, raises, examples where useful). Keep lines ≤ 100 characters where practical.
g. Pin exact package versions (e.g. `requirements-lock.txt`) alongside the ranged requirements.txt.

## Plan, in order — stop and report to Sans at each ★

1. ★ **Protocol v2, before computing any new scores.** Write `docs/protocol_v2.md` and
   `config/protocol_v2.json` and commit them first:
   - Multi-path inputs: define the path set and aggregation without looking at targets or scores.
     Prefer a geometry-free rule (e.g. all 36 actuator–sensor pairs at 150 kHz, per-path reference
     normalisation, then the median across paths of relative RMS and relative PTP), or a justified
     notch-crossing subset from the sensor layout. The Technical Report says L1S11 (and others)
     needed CHANGEPATH.m remapping: verify actuator/sensor IDs are consistent across L1S11, L1S12
     and L2S11 before matching paths across specimens.
   - Keep the original single-path 1→7 features as the baseline. Same six models and settings as
     protocol v1 (no tuning), plus the v2 inputs.
   - L2S11 acquisition rules: audit its gain/excitation/load/condition metadata and choose
     eligibility from metadata only (its load may differ from Layup 1's 3.95–4.05 kips). Decide in
     advance how the negative cycle-1 value and the reference checkpoint are handled.
   - Final-model selection rule declared before validation (e.g. lowest worst-direction validation
     MAE on L1S11↔L1S12; ties → simpler model), and that only the frozen model (trained by a
     stated rule) is scored on L2S11, once.
   - Unlabelled sanity check: L1S11 checkpoints from 125k to 227k cycles only, with predeclared
     plausibility criteria (e.g. predictions non-decreasing on average beyond 100k, within a
     plausible range, no extreme extrapolation). Plausibility, not accuracy.
2. Implement code fixes a–d with tests; confirm all historical results still reproduce bit-for-bit
   (baseline, repeat sensitivity, model comparison, coverage). Commit on a feature branch with
   clear messages.
3. ★ Run v2 validation on L1S11↔L1S12 (both directions), apply the predeclared selection rule,
   then freeze and commit the final model choice.
4. ★ Score the frozen model on L2S11 exactly once and record everything, including failure. Run the
   unlabelled L1S11 sanity check. Add L2S11 coverage diagnostics like the existing hull analysis.
5. Resolve the remaining open questions in docs: index definition (facts 2–3, citing report page
   and line), sampling rate (fact 1), amplitude units ("raw acquisition units, unknown; ratios are
   dimensionless"), dataset provenance/attribution/terms (NASA PCoE Prognostics Data Repository
   "CFRP Composites" dataset, Saxena et al.; cite the README's references [3]–[5]; check the NASA
   repository page for the exact citation and licence and record URL and access date — ask Sans if
   web access fails).
6. Repository deliverables: NumPy docstrings everywhere (f); HTML docs with pdoc into `docs/html`
   (build command in README); pytest with a saved test report (`--junitxml` and/or pytest-html
   into `results/test_report/`); pinned versions (g); README covering purpose, structure, setup,
   data download, full reproduction commands and outputs; fresh-clone verification (clone to a temp
   folder, new venv, point at raw data, run everything and the tests, compare outputs); fix (e).
7. ★ Draft the written report (5–10 pages) in `docs/report/`: engineering context, inputs/outputs,
   methods (relevant MMA3001 weeks), validation design (why specimen-held-out; why not random
   splits; pseudo-replication), results (v1, v2, L2S11 test, sanity check), sensitivity, profiling
   (12.77 → 7.77 s, 39% less elapsed time, byte-identical outputs), limitations, recommendation.
8. Draft the AI reflection: ChatGPT/Codex and Claude (Claude Code in VS Code and claude.ai)
   contributed substantially to code, analysis and documentation; what Sans verified; where AI was
   wrong or corrected; how protocol pre-declaration guarded against AI-assisted p-hacking. Leave
   placeholders for Sans's own reflections rather than inventing them.
9. Draft a 5-minute presentation outline and likely Q&A ("why only two specimens?", "why linear
   regression?", "is L2S11 a fair test?", "what would you do with more data?").

## Working rules

- Ask Sans before anything irreversible or ambiguous; otherwise proceed and summarise.
- Never commit raw data; keep recorded results immutable (new experiments go to new folders).
- Every number in docs must come from a script output in the repo.
- Run the full test suite after each stage and report pass counts.
- Log every session in `docs/progress.md` (date, what changed, results, test count, next step).
