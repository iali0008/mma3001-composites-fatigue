"""POST HOC diagnostic of the L1S11 path 1->7 jump between 175k and 177k cycles.

Written after the step-4 sanity check failed (C1). It does not change that
result. It reads the L1S11 logbook, the eligible Loaded L1S11 MAT files from
100k cycles on, and the recorded protocol v2 per-pair ratios, and asks:

* does the logbook record an acquisition change (re-mounting, settings,
  cabling, load) around 175k-177k cycles?
* is the logged date/time column usable as chronology?
* did the jump occur on path 1->7 only, or on all 36 paths?
* did the 1->7 actuator (excitation) signal change?

Outputs ``results/protocol_v2/post_hoc_step4/logbook_L1S11.json`` and
``logbook_L1S11_rows.csv``.

Example
-------
``python scripts/post_hoc_logbook_l1s11.py --data-root "data/2.+Composites/2. Composites"``
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import numpy as np
import openpyxl
from scipy.io import loadmat

from common import ROOT, read_csv, require, save_json, write_csv, waveform_features

OUT = ROOT / 'results' / 'protocol_v2' / 'post_hoc_step4'
LOGBOOK = 'Layup1/L1_S11_F/L1S11.xlsx'


def logbook_rows(path):
    """Read the ``Log_fatigue_testing`` worksheet as dictionaries.

    Parameters
    ----------
    path : pathlib.Path
        Logbook workbook (opened read-only, never saved).

    Returns
    -------
    list of dict
        Row number, timestamp (ISO text or ``''``), cycles, load, condition,
        data file, MTS file and remarks.
    """
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = []
        for number, v in enumerate(book['Log_fatigue_testing'].iter_rows(values_only=True), 1):
            if number == 1 or v[3] is None:
                continue
            stamp = ''
            if isinstance(v[0], datetime) and v[1] is not None:
                stamp = datetime.combine(v[0].date(), v[1]).isoformat(' ')
            rows.append(dict(row=number, timestamp=stamp, cycles=v[3], load_kips=v[4],
                             condition=str(v[5]), data_file=str(v[6]).strip(" '\""),
                             mts_file=v[7] or '', remarks=v[8] or ''))
        return rows
    finally:
        book.close()


def path_features(path, pair):
    """Return receiver and actuator RMS/PTP for one pair at 150 kHz.

    Parameters
    ----------
    path : pathlib.Path
        PZT MAT file.
    pair : tuple of int
        ``(actuator, sensor)``.

    Returns
    -------
    dict
        ``receiver_rms``, ``receiver_ptp``, ``actuator_rms``, ``actuator_ptp``.
    """
    coupon = loadmat(path, simplify_cells=True)['coupon']
    match = [p for p in coupon['path_data']
             if (p['actuator'], p['sensor'], p['frequency']) == (*pair, 150)]
    require(len(match) == 1, f'Ambiguous path in {path.name}')
    rr, rp = waveform_features(np.asarray(match[0]['signal_sensor'], float))
    ar, ap = waveform_features(np.asarray(match[0]['signal_actuator'], float))
    return dict(receiver_rms=rr, receiver_ptp=rp, actuator_rms=ar, actuator_ptp=ap)


def main(argv=None):
    """Run the post hoc logbook and waveform checks.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-root', required=True, type=Path)
    args = parser.parse_args(argv)
    data_root = args.data_root.resolve()
    rows = logbook_rows(data_root / LOGBOOK)
    window = [r for r in rows if isinstance(r['cycles'], (int, float)) and r['cycles'] >= 100000]
    stamps = [r['timestamp'] for r in rows if r['timestamp']]
    backwards = [dict(row=rows[i]['row'], previous=stamps[i - 1], current=stamps[i])
                 for i in range(1, len(stamps)) if stamps[i] < stamps[i - 1]]

    # Waveform evidence: eligible Loaded files used by protocol v2 from 100k cycles on.
    features = read_csv(ROOT / 'results' / 'protocol_v2' / 'validation' / 'checkpoint_features.csv')
    late = [r for r in features if r['specimen'] == 'L1S11' and int(r['cycles']) >= 100000]
    folder = data_root / 'Layup1' / 'L1_S11_F' / 'PZT-data'
    waveforms = []
    for r in late:
        for name in r['filenames'].split('; '):
            waveforms.append(dict(cycles=int(r['cycles']), filename=name,
                                  **path_features(folder / name, (1, 7))))
    ratios = read_csv(ROOT / 'results' / 'protocol_v2' / 'validation' / 'pair_ratios.csv')
    pair_summary = {}
    for cycle in (100000, 125000, 150000, 175000, 177000, 227000):
        local = [r for r in ratios if r['specimen'] == 'L1S11' and int(r['cycles']) == cycle]
        rms = np.array([float(r['rms_ratio']) for r in local])
        pair_summary[cycle] = dict(pairs=len(local), median_rms_ratio=float(np.median(rms)),
                                   pairs_with_rms_ratio_above_1=int((rms > 1).sum()),
                                   path_1_7_rms_ratio=next(float(r['rms_ratio']) for r in local
                                                           if (r['actuator'], r['sensor']) == ('1', '7')))
    change = {}
    for pair in [(a, s) for a in range(1, 7) for s in range(7, 13)]:
        get = {int(r['cycles']): float(r['rms_ratio']) for r in ratios if r['specimen'] == 'L1S11'
               and (int(r['actuator']), int(r['sensor'])) == pair}
        change[f'{pair[0]}->{pair[1]}'] = get[177000] / get[175000]
    values = np.array(list(change.values()))
    keywords = ('mount', 'remov', 'cable', 'sensor', 'gain', 'setting', 'reset', 'replac', 'glue',
                'off-center', 'hydrolic', 'resum')
    summary = dict(
        status='POST HOC diagnostic after the step-4 sanity check; the C1 fail stands',
        logbook=LOGBOOK,
        remarks_100k_onwards=[dict(row=r['row'], cycles=r['cycles'], remarks=r['remarks'])
                              for r in window if r['remarks']],
        acquisition_keyword_remarks_whole_log=[dict(row=r['row'], cycles=r['cycles'],
                                                    remarks=r['remarks']) for r in rows
                                               if any(k in r['remarks'].lower() for k in keywords)],
        rows_where_logged_timestamp_goes_backwards=len(backwards),
        backwards_examples=backwards[:10],
        sequence_175k_to_177k=[dict(row=r['row'], timestamp=r['timestamp'], cycles=r['cycles'],
                                    condition=r['condition'], load_kips=r['load_kips'],
                                    file=r['data_file']) for r in window
                               if 175000 <= r['cycles'] <= 177309],
        path_1_7_waveforms=waveforms,
        per_pair_rms_ratio_summary=pair_summary,
        rms_ratio_change_177k_over_175k=dict(
            median=float(np.median(values)), min=float(values.min()), max=float(values.max()),
            pairs_increasing=int((values > 1).sum()), pairs=len(values),
            path_1_7=change['1->7']))
    OUT.mkdir(parents=True, exist_ok=True)
    save_json(OUT / 'logbook_L1S11.json', summary)
    write_csv(OUT / 'logbook_L1S11_rows.csv', window)
    print(summary)


if __name__ == '__main__':
    main()
