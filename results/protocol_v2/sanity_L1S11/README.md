# L1S11 unlabelled sanity check (protocol v2 section 9): FAIL

`result.json` is the predeclared outcome from the single step-4 run (commit `52169ab`).

- **C1 fails.** The mean prediction over 125k–227k cycles (0.083) is below the prediction at 100k
  cycles (0.114).
- **C2 and C3 pass.** Every late prediction lies within 0.018–0.128.

**This is a fail and stays a fail.**

The predictions drop between 175k and 177k cycles because the path 1→7 ratios jump beyond the
training range there. A **post hoc** diagnostic (`../post_hoc_step4/logbook_L1S11.json`, script
`scripts/post_hoc_logbook_l1s11.py`) found the following:

- **Logbook.** It records no re-mounting, settings, cabling or load change. Its condition order at
  177k is unusual, which is consistent with the coupon having been out of the machine.
- **Waveforms.** The RMS ratio rises on all 36 paths at once (median ×1.33), while the excitation
  signal is unchanged. This is consistent with a global coupling or mounting change rather than
  damage. It is a hypothesis, not a confirmed cause (wording tightened 2026-10-13, finding R6).

See `../test_L2S11/README.md` for details.
