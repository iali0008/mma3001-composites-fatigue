"""POST HOC descriptive checks on the frozen step-4 outputs (not part of protocol v2).

Written after the single L2S11 test was scored. It reads only the saved step-4
and validation outputs, fits nothing, and changes no recorded result. Its
numbers help interpret the predeclared results; they must never be presented
as predeclared or used to choose a model.

Writes ``summary.json`` to ``--output`` (default ``results/rebuilt/post_hoc_step4/``). The
recorded copy is ``results/protocol_v2/post_hoc_step4/summary.json``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.stats import pearsonr, spearmanr

from common import ROOT, read_csv, require_not_recorded, save_json

BASE = ROOT / 'results' / 'protocol_v2'


def main(argv=None):
    """Compute the post hoc summaries and write them to JSON.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results' / 'rebuilt' / 'post_hoc_step4',
        help='New folder; recorded results are refused.',
    )
    out = require_not_recorded(parser.parse_args(argv).output)
    rows = [r for r in read_csv(BASE / 'test_L2S11' / 'predictions.csv') if r['role'] == 'frozen']
    obs = np.array([float(r['observed']) for r in rows])
    pred = np.array([float(r['predicted']) for r in rows])
    rms = np.array([float(r['relative_rms']) for r in rows])
    ptp = np.array([float(r['relative_ptp']) for r in rows])
    validation = read_csv(BASE / 'validation' / 'checkpoint_features.csv')
    ranges = {}
    for specimen in ('L1S11', 'L1S12'):
        local = [
            r
            for r in validation
            if r['specimen'] == specimen and r['is_reference'] == 'False' and r['published_index']
        ]
        ranges[specimen] = {
            f: [min(float(r[f]) for r in local), max(float(r[f]) for r in local)]
            for f in ('relative_rms', 'relative_ptp', 'mp_relative_rms', 'mp_relative_ptp')
        }
    summary = dict(
        status='POST HOC: computed after the single L2S11 test; descriptive only',
        l2s11_scored_n=len(obs),
        l2s11_observed_range=[float(obs.min()), float(obs.max())],
        l2s11_observed_mean=float(obs.mean()),
        # Post hoc 'no damage' baseline: predicting 0 everywhere has MAE = mean |index|.
        constant_zero_predictor_MAE=float(np.mean(np.abs(obs))),
        frozen_MAE=float(np.mean(np.abs(pred - obs))),
        frozen_prediction_range=[float(pred.min()), float(pred.max())],
        all_frozen_residuals_negative=bool(np.all(pred - obs < 0)),
        spearman_prediction_vs_observed=float(spearmanr(pred, obs).statistic),
        pearson_prediction_vs_observed=float(pearsonr(pred, obs).statistic),
        l2s11_path_1_7_relative_rms_range=[float(rms.min()), float(rms.max())],
        l2s11_path_1_7_relative_ptp_range=[float(ptp.min()), float(ptp.max())],
        development_feature_ranges_non_reference_labelled=ranges,
    )
    out.mkdir(parents=True, exist_ok=True)
    save_json(out / 'summary.json', summary)
    print(summary)


if __name__ == '__main__':
    main()
