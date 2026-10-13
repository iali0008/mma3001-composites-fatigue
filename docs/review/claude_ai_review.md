# Second independent review (Claude, claude.ai session)

Reviewed 2026-10-12, branch `code-fixes` at `d9c7372`. Read-only: no script that writes results
was run, L2S11 was not rescored, and no raw file was modified. This review was written before
reading `independent_review.md` (Codex); the comparison section was added afterwards.

## Verdict

The numbers are right and the protocol was followed: the git order supports "protocol before
v2 scores", L2S11 features and predictions are written before its labels are read, and every
headline number reproduces independently. What is not ready is the packaging: a dangerous
cleanup path, raw-waveform and third-party material committed despite docs saying otherwise,
reproduction instructions that cannot run as written, and conclusions worded more strongly than
one cross-layup test supports. None of these require rerunning any experiment.

## Independent recomputation (different environment)

Linux, Python 3.13.16, NumPy 2.5.3, scikit-learn 1.9.1 (project lock: 3.13.3 / 2.3.0 / 1.9.0).

| Check | Result |
|---|---|
| Test suite | 66 passed, 17 subtests |
| v2 LinearRegression, refit from `results/protocol_v2/validation/checkpoint_features.csv` | single path 0.050532 / 0.029357; multi-path 0.090320 / 0.068777 (match `candidates.csv`) |
| Pooled final model refit from exported features, scored on the 8 L2S11 checkpoints | MAE 0.037358; Dummy 0.101531 (match `test_L2S11/metrics.csv`) |
| Predict-zero baseline on L2S11 | MAE 0.036169 (matches `post_hoc_step4/summary.json`) |
| Git chronology | protocol `47b9047` → approval `137cadd` → validation `6ccee92` → selection `a4bfe4b` → scorer `52169ab`; protocol/config hashes in both receipts match the committed files |

Useful for the report: the pooled model is about −0.72·R + 0.61·P + 0.111, so at R = P = 1
("signal unchanged") it predicts about −0.004. The model encodes "no signal change means no
damage". On L2S11 path 1→7 does not change (R 0.985–1.018, P 1.001–1.015) while the index reaches
0.084, so the failure is in the feature, not the regression.

## Findings

| ID | Severity | Location | Finding | Suggested fix |
|---|---|---|---|---|
| C1 | major | `README.md` "Reproduce everything"; `protocol_v2_validation.py:278`, `protocol_v2_test.py:240` | The README says to remove `results/protocol_v2/` in a fresh clone to rerun v2, but deleting tracked files makes `git status` dirty, so both one-shot scripts refuse to start. v2 is not covered by `verify_reproduction.py` either. | Document a working route (scratch branch with the deletion committed), or add a replay mode that writes to `results/rebuilt/` and compares with the record. |
| C2 | major | `docs/dataset.md:36`, `README.md:117`; `data/audit_stiffness/`, `data/pzt_feasibility/` | Docs say no raw data or papers are committed, but the repo tracks a vendored copy of pypdf (66 files), full extracted text of the Technical Report and three papers, and (per Codex) raw waveform excerpts in `selected_signals.npz`. | Untrack these or document them as intentional exceptions; fix the docs. Removing them from the tree does not remove them from history. |
| C3 | major | `README.md` headline and limitations; `CLAUDE.md` step 4 framing | "Simple reference-normalised amplitude features do not transfer between specimens" generalises from one frozen model on one cross-layup specimen. This framing originated in the claude.ai session, not only in the repo. | Say: no evidence that the frozen model transfers to L2S11; crosstalk, mounting and specimen effects are hypotheses consistent with the data. |
| C4 | minor (marks) | all `scripts/` | Inline comments are almost absent: about 58 `#` lines in about 6,600 lines; six modules have none. The brief requires inline comments ("Code should include inline comments and Docstring") and the rubric rewards comments that explain intent. Docstrings are excellent. | Add short intent comments at the non-obvious steps: label-blind reference, per-pair normalisation, gate, once-only guard, label-read order. |
| C5 | minor (marks) | report, README | Brief section 6 asks for profilers and timing "and where appropriate estimates of arithmetic intensity and required number of FLOPS". Profiling and timing are done; FLOPs and memory are not addressed. | One paragraph: estimate the OLS/feature FLOPs (tiny), explain why the workflow is I/O- and MAT-decoding-bound, and state that memory was not measured. |
| C6 | minor | `CLAUDE.md` fact 4 | The 13%/29% repeat spread and ±5% reference-perturbation numbers came from the claude.ai review and have no script in the repo. "RBF SVR cannot succeed forward" is too categorical. | Add a small labelled diagnostic script or keep these numbers out of the report; describe SVR as observed to revert towards the training mean. |
| C7 | minor | `results/protocol_v2/validation/predictions.csv` | Controls are labelled `input_set=single_path_1_7` (a plotting relabel at `protocol_v2_validation.py:379`), but `metrics.csv` labels them `none`. | Note it in the validation README; do not regenerate. |
| C8 | minor | tests | No test covers the once-only guard, the order "predictions written before labels read", or the reproduction gate. | Add mocked tests that never touch real L2S11 data. |
| C9 | note | chat summaries | A Claude Code chat summary said multi-path made the forward direction worse for every family. `candidates.csv` shows it improved the tree (0.1052 → 0.0907) and SVR (0.1112 → 0.0963). The repo files say this correctly. | Use the files, not chat summaries, when writing the report. |

## Comparison with the Codex review

| Topic | Codex | Claude | Assessment |
|---|---|---|---|
| Reproduce instructions cannot run | R5 | C1 | Both found it; real. |
| Committed raw excerpts / third-party text | R3 (incl. `.npz` waveforms) | C2 | Both; Codex found the waveform excerpts I missed. |
| Over-strong conclusion | R6 | C3 | Both; real. |
| Unsupported numbers in CLAUDE.md | R9 | C6 | Both; the numbers came from the claude.ai session. |
| Missing tests for gate / guard / orchestration | R8 | C8 | Both. |
| `--work` can `rmtree` raw data or recorded v2 results | R1 | — | Codex only. Read the code: valid. Fix first. |
| Reproduction gate accepts duplicate or missing rows | R2 | — | Codex only. Valid; the recorded result is still correct. |
| Logbook timestamps treated as chronology | R4 | — | Codex only. Valid; docs overstate repeat chronology. |
| v1 screening does not exclude NaN or constant signals | R7 | — | Codex only. Valid; no current result is affected. |
| Inline comments | rated "met" | C4 | Disagree with Codex: the brief explicitly requires inline comments. |
| FLOPs / memory (brief section 6) | justify omission | C5 | Agree: justify briefly rather than compute in depth. |

## Suggested order of fixes (no experiment is rerun)

1. R1: restrict `--work` deletion to a dedicated scratch folder.
2. C2 / R3: decide what derived material stays in the repo; fix the docs.
3. C1 / R5: rewrite the reproduction section so every listed command works.
4. C3 / R6, R4, C6 / R9: tighten wording in README, methodology and CLAUDE.md.
5. R2, C8 / R8, R7: strengthen the gate and tests; label v1 screening as historical.
6. C4, C5: inline comments; FLOPs/memory paragraph for the report.
7. Then merge to `main`, push, and draft the report.
