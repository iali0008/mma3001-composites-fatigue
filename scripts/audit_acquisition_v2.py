"""Label-blind acquisition audit used to write protocol v2.

This script reads PZT metadata and waveforms for L1S11, L1S12 and L2S11 and
summarises acquisition settings, path identifiers and per-path signal checks.
It deletes ``coupon['straingage_data']`` immediately after loading, so no
stiffness label, label availability or model score can influence protocol v2.

Outputs (CSV/JSON) go to ``--output`` (default ``results/rebuilt/protocol_v2_audit/``); the
recorded audit in ``results/protocol_v2_audit/`` is never overwritten.

Example
-------
>>> # python scripts/audit_acquisition_v2.py --data-root "data/2.+Composites/2. Composites"
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

from common import ROOT, require, require_not_recorded, scalar
from raw_loading import iter_coupons

SPECIMENS = {'L1S11': 'Layup1/L1_S11_F', 'L1S12': 'Layup1/L1_S12_F', 'L2S11': 'Layup2/L2_S11_F'}
ACTUATORS = range(1, 7)
SENSORS = range(7, 13)
FREQUENCY_KHZ = 150
EARLY_PEAK_SAMPLES = 400
L2S11_LOAD_WINDOW = (4.53, 4.63)


def horizontal_offset(actuator, sensor):
    """Return the column offset between an actuator and a sensor.

    Uses Technical Report Figure 1(a): actuators 6..1 run left to right along
    one strip and sensors 7..12 run left to right along the other, so actuator
    ``a`` is in column ``7 - a`` and sensor ``s`` is in column ``s - 6``.

    Parameters
    ----------
    actuator : int
        Actuator ID, 1-6.
    sensor : int
        Sensor ID, 7-12.

    Returns
    -------
    int
        ``|13 - actuator - sensor|``; 0 for straight-across pairs, 5 for the
        longest diagonals (for example 1 -> 7).

    Examples
    --------
    >>> horizontal_offset(6, 7), horizontal_offset(1, 7)
    (0, 5)
    """
    # Strip geometry: actuator a faces sensor 13 - a, so this counts how many
    # positions a path is offset from straight across.
    return abs(13 - actuator - sensor)


def path_summary(path):
    """Summarise one path record without computing any learned quantity.

    Parameters
    ----------
    path : dict
        One element of ``coupon['path_data']``.

    Returns
    -------
    dict
        IDs, settings, signal lengths, finite/nonconstant flags and, when the
        receiver signal is finite, mean-centred RMS and peak-to-peak.
    """
    out = {
        k: scalar(path.get(k, []))
        for k in ('actuator', 'sensor', 'frequency', 'gain', 'amplitude', 'sampling_rate')
    }
    for field in ('signal_actuator', 'signal_sensor'):
        x = np.asarray(path.get(field, []), dtype=float).ravel()
        out[field + '_length'] = len(x)
        out[field + '_finite'] = bool(len(x) and np.isfinite(x).all())
        out[field + '_nonconstant'] = bool(out[field + '_finite'] and np.ptp(x) > 0)
        if field == 'signal_sensor' and out[field + '_finite']:
            out['rms'] = float(np.sqrt(np.mean((x - x.mean()) ** 2)))
            out['ptp'] = float(np.ptp(x))
            # Where the largest swing occurs; a fixed early peak suggests crosstalk rather
            # than a wave that travelled through the coupon.
            out['peak_index'] = int(np.argmax(np.abs(x - x.mean())))
    return out


def audit(data_root, workers=1):
    """Audit every PZT file of the three labelled specimens, label-blind.

    Parameters
    ----------
    data_root : pathlib.Path
        The extracted ``2. Composites`` directory.
    workers : int, optional
        MAT prefetch workers passed to :func:`raw_loading.iter_coupons`.

    Returns
    -------
    recordings : list of dict
        One row per MAT file with metadata and 150 kHz grid checks.
    paths : list of dict
        One row per recording and 150 kHz actuator-sensor pair.
    hashes : dict
        SHA-256 of every file read, keyed by path relative to ``data_root``.
    """
    recordings, paths, hashes = [], [], {}
    for specimen, folder in SPECIMENS.items():
        files = sorted((data_root / folder / 'PZT-data').glob(specimen + '_*.mat'))
        require(files, f'No PZT files for {specimen}')
        for file, digest, coupon in iter_coupons(files, workers):
            coupon.pop('straingage_data', None)  # label-blind by construction
            hashes[file.relative_to(data_root).as_posix()] = digest
            records = coupon.get('path_data', [])
            records = [records] if isinstance(records, dict) else list(records)
            triples = [
                (
                    scalar(p.get('actuator', [])),
                    scalar(p.get('sensor', [])),
                    scalar(p.get('frequency', [])),
                )
                for p in records
            ]
            # A short signature of the stored path order, to detect files whose records are
            # arranged differently (the reason paths are matched by ID, not position).
            order = hashlib.sha256(repr(triples).encode()).hexdigest()[:12]
            at150 = [path_summary(p) for p, t in zip(records, triples) if t[2] == FREQUENCY_KHZ]
            pairs = Counter((s['actuator'], s['sensor']) for s in at150)
            full_grid = set(pairs) == {(a, s) for a in ACTUATORS for s in SENSORS} and all(
                v == 1 for v in pairs.values()
            )
            row = dict(
                specimen=specimen,
                filename=file.name,
                cycles=scalar(coupon.get('cycles', [])),
                load_kips=scalar(coupon.get('load', [])),
                condition=str(coupon.get('condition', '')).strip(),
                n_path_records=len(records),
                n_unique_triples=len(set(triples)),
                frequencies='; '.join(
                    str(int(f)) for f in sorted({t[2] for t in triples if t[2] is not None})
                ),
                path_order_signature=order,
                n_150khz=len(at150),
                full_36_pair_grid_150khz=full_grid,
            )
            for key in (
                'gain',
                'amplitude',
                'sampling_rate',
                'signal_actuator_length',
                'signal_sensor_length',
            ):
                row[key + '_values_150khz'] = '; '.join(
                    str(v) for v in sorted({s[key] for s in at150}, key=str)
                )
            row['all_150khz_signals_finite_nonconstant'] = all(
                s['signal_actuator_nonconstant'] and s['signal_sensor_nonconstant'] for s in at150
            )
            recordings.append(row)
            for s in at150:
                paths.append(
                    dict(
                        specimen=specimen,
                        filename=file.name,
                        cycles=row['cycles'],
                        condition=row['condition'],
                        load_kips=row['load_kips'],
                        **s,
                    )
                )
    return recordings, paths, hashes


def pair_settings_table(paths):
    """Tabulate gain/amplitude combinations per specimen and 150 kHz pair.

    Parameters
    ----------
    paths : list of dict
        Output of :func:`audit`.

    Returns
    -------
    list of dict
        One row per specimen, pair and (gain, amplitude) combination with the
        number of recordings and their condition labels.
    """
    table = defaultdict(lambda: {'recordings': 0, 'conditions': Counter()})
    for p in paths:
        key = (p['specimen'], p['actuator'], p['sensor'], p['gain'], p['amplitude'])
        table[key]['recordings'] += 1
        table[key]['conditions'][p['condition']] += 1
    return [
        dict(
            specimen=k[0],
            actuator=k[1],
            sensor=k[2],
            gain=k[3],
            amplitude=k[4],
            recordings=v['recordings'],
            conditions='; '.join(f'{c}:{n}' for c, n in sorted(v['conditions'].items())),
        )
        for k, v in sorted(table.items(), key=lambda kv: str(kv[0]))
    ]


def geometry_consistency(paths, recordings):
    """Check that pair IDs refer to the same geometry in every specimen.

    For each specimen, take the earliest positive-cycle Loaded recordings that
    have a complete 150 kHz grid, compute each pair's median receiver RMS, and
    report (a) Spearman correlation of log RMS with the Figure 1 column offset,
    (b) Spearman correlation of the 36-pair log-RMS patterns between specimens
    and (c) the same for the receiver envelope-peak sample index, which does
    not depend on gain. No label or score is used.

    Parameters
    ----------
    paths, recordings : list of dict
        Outputs of :func:`audit`.

    Returns
    -------
    dict
        Selected files, per-specimen offset correlations and pairwise pattern
        correlations.
    """
    complete = {
        (r['specimen'], r['filename'])
        for r in recordings
        if r['full_36_pair_grid_150khz']
        and r['condition'].casefold() == 'loaded'
        and r['cycles'] is not None
        and r['cycles'] > 0
    }
    result = {
        'selected': {},
        'offset_spearman': {},
        'pattern_spearman': {},
        'peak_index_by_pair': {},
        'peak_index_spearman': {},
        'peak_index_within_50_samples_fraction': {},
    }
    patterns, peaks = {}, {}
    pair_list = [(a, s) for a in ACTUATORS for s in SENSORS]
    for specimen in SPECIMENS:
        rows = [
            p
            for p in paths
            if p['specimen'] == specimen and (p['specimen'], p['filename']) in complete
        ]
        first = min(p['cycles'] for p in rows)
        rows = [p for p in rows if p['cycles'] == first]
        result['selected'][specimen] = dict(
            cycles=first, files=sorted({p['filename'] for p in rows})
        )
        med = {
            pair: float(np.median([p['rms'] for p in rows if (p['actuator'], p['sensor']) == pair]))
            for pair in pair_list
        }
        # Compare amplitude patterns on a log scale so specimens with different gain
        # settings can be ranked against each other.
        patterns[specimen] = np.log([med[pair] for pair in pair_list])
        peaks[specimen] = np.array(
            [
                np.median([p['peak_index'] for p in rows if (p['actuator'], p['sensor']) == pair])
                for pair in pair_list
            ]
        )
        result['peak_index_by_pair'][specimen] = {
            f'{a}->{s}': float(v) for (a, s), v in zip(pair_list, peaks[specimen])
        }
        offsets = [horizontal_offset(a, s) for a, s in pair_list]
        rho = spearmanr(offsets, patterns[specimen]).statistic
        result['offset_spearman'][specimen] = float(rho)
    names = list(SPECIMENS)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            result['pattern_spearman'][f'{a}~{b}'] = float(
                spearmanr(patterns[a], patterns[b]).statistic
            )
            result['peak_index_spearman'][f'{a}~{b}'] = float(
                spearmanr(peaks[a], peaks[b]).statistic
            )
            result['peak_index_within_50_samples_fraction'][f'{a}~{b}'] = float(
                np.mean(np.abs(peaks[a] - peaks[b]) <= 50)
            )
    return result


def per_pair_setting_changes(paths):
    """Find pairs whose gain/amplitude setting changes between recordings.

    Parameters
    ----------
    paths : list of dict
        Output of :func:`audit`.

    Returns
    -------
    dict
        For each specimen: the number of pairs with more than one setting, and
        the recordings whose 36-pair setting vector differs from the modal one.
    """
    out = {}
    for specimen in SPECIMENS:
        rows = [p for p in paths if p['specimen'] == specimen]
        per_pair = defaultdict(set)
        vectors = defaultdict(dict)
        for p in rows:
            per_pair[(p['actuator'], p['sensor'])].add((p['gain'], p['amplitude']))
            vectors[p['filename']][(p['actuator'], p['sensor'])] = (p['gain'], p['amplitude'])
        frozen = {f: tuple(sorted(v.items())) for f, v in vectors.items()}
        # The most common full-grid settings vector; recordings that differ are listed.
        modal = Counter(frozen.values()).most_common(1)[0][0]
        out[specimen] = dict(
            pairs_with_multiple_settings=sum(len(v) > 1 for v in per_pair.values()),
            non_modal_setting_recordings=sorted(f for f, v in frozen.items() if v != modal),
        )
    return out


def fatigue_load_stats(recordings, specimen, window):
    """Describe Loaded positive-cycle recordings inside and outside a load window.

    Parameters
    ----------
    recordings : list of dict
        Output of :func:`audit`.
    specimen : str
        Specimen name.
    window : tuple of float
        Inclusive (low, high) load window in kips.

    Returns
    -------
    dict
        Counts, load range and cycle range inside the window, and the cycles of
        Loaded recordings outside it.
    """
    loaded = [
        r
        for r in recordings
        if r['specimen'] == specimen
        and r['cycles']
        and r['cycles'] > 0
        and r['condition'].casefold() == 'loaded'
    ]
    # The L2S11 window comes from this metadata alone (its fatigue mean load is
    # higher than Layup 1's), never from labels or scores.
    inside = [r for r in loaded if window[0] <= r['load_kips'] <= window[1]]
    return dict(
        window_kips=list(window),
        loaded_positive_cycle=len(loaded),
        inside=len(inside),
        inside_load_min=min(r['load_kips'] for r in inside),
        inside_load_max=max(r['load_kips'] for r in inside),
        inside_cycles=sorted({r['cycles'] for r in inside}),
        median_load_inside=float(np.median([r['load_kips'] for r in inside])),
        outside=sorted(
            (r['cycles'], r['load_kips'], r['filename']) for r in loaded if r not in inside
        ),
    )


def write_csv(path, rows):
    """Write ``rows`` (list of dict) to ``path`` with the union of keys as header.

    Parameters
    ----------
    path : pathlib.Path
        Destination CSV file.
    rows : list of dict
        Rows to write.
    """
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    """Run the audit and write ``recordings.csv``, ``pair_settings.csv``,
    ``summary.json`` and ``source_hashes.json``.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-root', required=True, type=Path)
    parser.add_argument(
        '--output',
        type=Path,
        default=ROOT / 'results' / 'rebuilt' / 'protocol_v2_audit',
        help='New output folder; the recorded results/protocol_v2_audit is refused.',
    )
    parser.add_argument('--workers', type=int, choices=(1, 4), default=4)
    args = parser.parse_args(argv)
    data_root = args.data_root.expanduser().resolve()
    out = require_not_recorded(args.output.expanduser())
    require(
        data_root not in out.parents and out != data_root,
        'Output must be outside the original dataset.',
    )
    out.mkdir(parents=True, exist_ok=True)
    recordings, paths, hashes = audit(data_root, args.workers)

    summary = {'label_blind': True, 'frequency_khz': FREQUENCY_KHZ, 'specimens': {}}
    for specimen in SPECIMENS:
        rs = [r for r in recordings if r['specimen'] == specimen]
        loaded = [r for r in rs if r['condition'].casefold() == 'loaded']
        summary['specimens'][specimen] = dict(
            files=len(rs),
            conditions=dict(Counter(r['condition'] for r in rs)),
            loaded_load_kips_min=min(r['load_kips'] for r in loaded),
            loaded_load_kips_max=max(r['load_kips'] for r in loaded),
            loaded_load_kips_values=dict(Counter(str(r['load_kips']) for r in loaded)),
            cycles_with_loaded_recordings=sorted({r['cycles'] for r in loaded}),
            path_order_signatures=dict(Counter(r['path_order_signature'] for r in rs)),
            full_grid_files=sum(r['full_36_pair_grid_150khz'] for r in rs),
            all_signals_ok_files=sum(r['all_150khz_signals_finite_nonconstant'] for r in rs),
            sampling_rates=sorted({r['sampling_rate_values_150khz'] for r in rs}),
            signal_lengths=sorted({r['signal_sensor_length_values_150khz'] for r in rs}),
            gain_amplitude_by_condition=dict(
                Counter(
                    f"{r['condition']}|gain={r['gain_values_150khz']}"
                    f"|amp={r['amplitude_values_150khz']}"
                    for r in rs
                )
            ),
            loaded_gain_amplitude_by_cycle={
                str(int(r['cycles'])): (
                    f"gain={r['gain_values_150khz']}|amp={r['amplitude_values_150khz']}"
                )
                for r in sorted(loaded, key=lambda r: r['cycles'])
            },
        )
    triple_sets = {}
    for specimen in SPECIMENS:
        sigs = {(r['actuator'], r['sensor']) for r in paths if r['specimen'] == specimen}
        triple_sets[specimen] = sorted(sigs)
    summary['same_150khz_pair_ids_all_specimens'] = (
        len({tuple(v) for v in triple_sets.values()}) == 1
    )
    summary['geometry_consistency'] = geometry_consistency(paths, recordings)
    for specimen, peaks in summary['geometry_consistency']['peak_index_by_pair'].items():
        early = sorted(k for k, v in peaks.items() if v < EARLY_PEAK_SAMPLES)
        summary['specimens'][specimen]['early_peak_pairs'] = early
        summary['specimens'][specimen]['early_peak_pair_count'] = len(early)
    summary['early_peak_threshold_samples'] = EARLY_PEAK_SAMPLES
    summary['per_pair_setting_changes'] = per_pair_setting_changes(paths)
    summary['l2s11_fatigue_load'] = fatigue_load_stats(recordings, 'L2S11', L2S11_LOAD_WINDOW)

    write_csv(out / 'recordings.csv', recordings)
    write_csv(out / 'pair_settings.csv', pair_settings_table(paths))
    (out / 'summary.json').write_text(json.dumps(summary, indent=2, default=str), encoding='utf-8')
    (out / 'source_hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2, default=str))


if __name__ == '__main__':
    main()
