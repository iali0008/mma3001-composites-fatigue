"""Protocol v2 feature extraction and the predeclared selection rule.

Implements sections 2-4 and 7 of ``docs/protocol_v2.md`` with the settings in
``config/protocol_v2.json``:

* joint, label-blind recording eligibility (both input sets use the same
  recordings, checkpoints and reference);
* the earliest eligible checkpoint as reference, chosen without labels;
* the ``single_path_1_7`` (v1 baseline) and ``multi_path_36`` input sets;
* the worst-direction-MAE selection rule with its tie-break order.

Labels are read only when ``read_labels=True``. With ``read_labels=False`` the
label field is deleted from each MAT structure as soon as it is loaded, so the
held-out specimen can be processed without exposing its labels.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np

from common import ROOT, load_json, require, scalar, waveform_features
from raw_loading import iter_coupons

PROTOCOL_PATH = ROOT / 'config' / 'protocol_v2.json'
PROTOCOL_DOC = ROOT / 'docs' / 'protocol_v2.md'
INPUT_SETS = ('single_path_1_7', 'multi_path_36')
FAMILIES = ('LinearRegression', 'DecisionTreeRegressor', 'SVR', 'MLPRegressor')
CONTROLS = ('log_cycle_OLS', 'DummyRegressor')


def load_protocol(path=PROTOCOL_PATH):
    """Load and sanity-check the protocol v2 configuration.

    Parameters
    ----------
    path : pathlib.Path, optional
        Configuration file; defaults to ``config/protocol_v2.json``.

    Returns
    -------
    dict
        The decoded configuration.

    Raises
    ------
    ValueError
        If the model settings differ from protocol v1 or the version is wrong.
    """
    protocol = load_json(path)
    require(protocol['protocol_version'] == 2, 'Not a protocol v2 configuration')
    v1 = load_json(ROOT / 'config' / 'model_comparison.json')
    for name, params in v1['models'].items():
        require(protocol['models'][name] == params, f'Model settings differ from v1: {name}')
    require(protocol['models']['mlp_seeds'] == v1['mlp_seeds'], 'MLP seeds differ from v1')
    return protocol


def pairs(protocol):
    """Return the 36 (actuator, sensor) pairs of the multi-path grid in fixed order.

    Parameters
    ----------
    protocol : dict
        Output of :func:`load_protocol`.

    Returns
    -------
    list of tuple
        ``(actuator, sensor)`` pairs, actuator-major.
    """
    grid = protocol['eligibility']['multi_path_grid']
    return [(a, s) for a in grid['actuators'] for s in grid['sensors']]


def summarise_file(coupon, specimen, filename, protocol, read_labels):
    """Collect metadata, settings and per-pair features of one MAT file.

    Parameters
    ----------
    coupon : dict
        ``coupon`` structure of one MAT file.
    specimen : str
        Specimen name.
    filename : str
        MAT file name.
    protocol : dict
        Output of :func:`load_protocol`.
    read_labels : bool
        Read the published label; if false the label field is deleted first.

    Returns
    -------
    dict
        File summary. ``pair_counts`` counts records per pair at the protocol
        frequency; ``settings`` maps pair to (gain, amplitude, sampling_rate);
        ``rms``/``ptp`` map pair to receiver features when every check for that
        pair passes; ``bad_pairs`` lists pairs with invalid signals.
    """
    if not read_labels:
        coupon.pop('straingage_data', None)
    rules = protocol['eligibility']
    records = coupon.get('path_data', [])
    records = [records] if isinstance(records, dict) else list(records)
    counts, settings, rms, ptp, bad = Counter(), {}, {}, {}, []
    for p in records:
        if scalar(p.get('frequency', [])) != rules['frequency_khz']:
            continue
        pair = (scalar(p.get('actuator', [])), scalar(p.get('sensor', [])))
        counts[pair] += 1
        settings[pair] = (scalar(p.get('gain', [])), scalar(p.get('amplitude', [])),
                          scalar(p.get('sampling_rate', [])))
        a = np.asarray(p.get('signal_actuator', []), dtype=float).ravel()
        x = np.asarray(p.get('signal_sensor', []), dtype=float).ravel()
        ok = all(len(s) == rules['signal_length_samples'] and np.isfinite(s).all() and np.ptp(s) > 0
                 for s in (a, x))
        if ok:
            rms[pair], ptp[pair] = waveform_features(x)
        else:
            bad.append(pair)
    label = None
    if read_labels:
        label = scalar(coupon.get('straingage_data', {}).get('stiffness_degradation', []))
    return dict(specimen=specimen, filename=filename, cycles=scalar(coupon.get('cycles', [])),
                load_kips=scalar(coupon.get('load', [])),
                condition=str(coupon.get('condition', '')).strip(), published_index=label,
                pair_counts=counts, settings=settings, rms=rms, ptp=ptp, bad_pairs=bad)


def setting_vector(summary, protocol):
    """Return a file's 36-pair (gain, amplitude) vector as a hashable tuple.

    Parameters
    ----------
    summary : dict
        Output of :func:`summarise_file`.
    protocol : dict
        Output of :func:`load_protocol`.

    Returns
    -------
    tuple
        ``(gain, amplitude)`` per pair in :func:`pairs` order (``None`` if absent).
    """
    return tuple(summary['settings'].get(pair, (None, None, None))[:2] for pair in pairs(protocol))


def eligibility_reasons(summary, specimen_rules, modal_vector, protocol):
    """List every protocol v2 rule a file fails; an empty list means eligible.

    Parameters
    ----------
    summary : dict
        Output of :func:`summarise_file`.
    specimen_rules : dict
        ``protocol['specimens'][specimen]``.
    modal_vector : tuple
        The specimen's modal :func:`setting_vector`.
    protocol : dict
        Output of :func:`load_protocol`.

    Returns
    -------
    list of str
        Failed rules. Labels are never consulted.
    """
    rules, reasons = protocol['eligibility'], []
    if summary['cycles'] is None or summary['cycles'] <= 0:
        reasons.append('not a positive-cycle checkpoint')
    if summary['condition'].casefold() != 'loaded':
        reasons.append('condition is not loaded')
    low, high = specimen_rules['load_window_kips']
    if summary['load_kips'] is None or not low <= summary['load_kips'] <= high:
        reasons.append(f'load outside {low}-{high} kips')
    grid = pairs(protocol)
    if any(summary['pair_counts'].get(p, 0) != 1 for p in grid):
        reasons.append('36-pair grid incomplete or duplicated')
    base = (rules['baseline_path']['actuator'], rules['baseline_path']['sensor'])
    if summary['pair_counts'].get(base, 0) != 1:
        reasons.append('baseline path missing or ambiguous')
    elif summary['settings'][base][:2] != (specimen_rules['baseline_gain'],
                                          specimen_rules['baseline_amplitude']):
        reasons.append('baseline gain/amplitude mismatch')
    if any(summary['settings'].get(p, (None,) * 3)[2] != rules['stored_sampling_rate'] for p in grid):
        reasons.append('stored sampling rate mismatch')
    if setting_vector(summary, protocol) != modal_vector:
        reasons.append('setting vector differs from specimen modal vector')
    if any(p in summary['bad_pairs'] or p not in summary['rms'] for p in grid):
        reasons.append('invalid signal (length, nonfinite or constant)')
    return reasons


def extract_specimen(data_root, specimen, protocol, read_labels, workers=1):
    """Screen every PZT file of one specimen with the protocol v2 rules.

    Parameters
    ----------
    data_root : pathlib.Path
        The extracted ``2. Composites`` directory.
    specimen : str
        Specimen name in ``protocol['specimens']``.
    protocol : dict
        Output of :func:`load_protocol`.
    read_labels : bool
        Whether labels may be read (``False`` for the held-out test specimen
        until step 4).
    workers : int, optional
        MAT prefetch workers.

    Returns
    -------
    summaries : list of dict
        One summary per file with ``eligible`` and ``exclusion_reasons`` added.
    hashes : dict
        SHA-256 per file, keyed relative to ``data_root``.
    """
    rules = protocol['specimens'][specimen]
    files = sorted((data_root / rules['folder'] / 'PZT-data').glob(specimen + '_*.mat'))
    require(bool(files), f'No PZT files for {specimen}')
    summaries, hashes = [], {}
    for path, digest_value, coupon in iter_coupons(files, workers):
        hashes[path.relative_to(data_root).as_posix()] = digest_value
        summaries.append(summarise_file(coupon, specimen, path.name, protocol, read_labels))
    modal = Counter(setting_vector(s, protocol) for s in summaries).most_common(1)[0][0]
    for s in summaries:
        reasons = eligibility_reasons(s, rules, modal, protocol)
        s['eligible'], s['exclusion_reasons'] = not reasons, '; '.join(reasons)
    return summaries, hashes


def build_checkpoints(summaries, protocol):
    """Aggregate eligible recordings into checkpoints with both input sets.

    Parameters
    ----------
    summaries : list of dict
        Output of :func:`extract_specimen` for one specimen.
    protocol : dict
        Output of :func:`load_protocol`.

    Returns
    -------
    checkpoints : list of dict
        Every checkpoint with at least one eligible recording, in cycle order,
        with ``relative_rms``/``relative_ptp`` (pair 1 -> 7) and
        ``mp_relative_rms``/``mp_relative_ptp`` (median of 36 per-pair ratios).
        ``published_index`` is ``None`` when unlabelled or labels were not read.
    pair_ratios : list of dict
        Per-checkpoint, per-pair ratios behind the multi-path features.
    reference : dict
        Reference cycle, files and denominators.

    Raises
    ------
    ValueError
        If no recording is eligible, labels conflict within a checkpoint, or a
        reference denominator is not positive.
    """
    eligible = [s for s in summaries if s['eligible']]
    require(bool(eligible), 'No eligible recording')
    specimen = eligible[0]['specimen']
    groups = defaultdict(list)
    for s in eligible:
        groups[s['cycles']].append(s)
    grid = pairs(protocol)
    base = (protocol['eligibility']['baseline_path']['actuator'],
            protocol['eligibility']['baseline_path']['sensor'])
    medians = {}
    for cycle, group in groups.items():
        medians[cycle] = {p: (float(np.median([s['rms'][p] for s in group])),
                              float(np.median([s['ptp'][p] for s in group]))) for p in grid}
    ref_cycle = min(groups)  # earliest eligible checkpoint; labels never consulted
    ref = medians[ref_cycle]
    require(all(v > 0 for p in grid for v in ref[p]), 'Invalid reference denominator')
    reference = dict(specimen=specimen, cycles=int(ref_cycle),
                     filenames='; '.join(s['filename'] for s in groups[ref_cycle]),
                     rms_denominator=ref[base][0], ptp_denominator=ref[base][1])
    checkpoints, pair_ratios = [], []
    for cycle in sorted(groups):
        group = groups[cycle]
        labels = {s['published_index'] for s in group if s['published_index'] is not None}
        require(len(labels) <= 1, f'Conflicting published labels: {specimen}, {cycle}')
        rms_ratio = {p: medians[cycle][p][0] / ref[p][0] for p in grid}
        ptp_ratio = {p: medians[cycle][p][1] / ref[p][1] for p in grid}
        checkpoints.append(dict(
            specimen=specimen, cycles=int(cycle), published_index=labels.pop() if labels else None,
            eligible_repeats=len(group), filenames='; '.join(s['filename'] for s in group),
            load_min_kips=min(s['load_kips'] for s in group),
            load_max_kips=max(s['load_kips'] for s in group),
            is_reference=cycle == ref_cycle, reference_cycles=int(ref_cycle),
            mean_centred_rms=medians[cycle][base][0], peak_to_peak=medians[cycle][base][1],
            relative_rms=medians[cycle][base][0] / ref[base][0],
            relative_ptp=medians[cycle][base][1] / ref[base][1],
            mp_relative_rms=float(np.median(list(rms_ratio.values()))),
            mp_relative_ptp=float(np.median(list(ptp_ratio.values()))),
            log10_cycles=float(np.log10(cycle))))
        for p in grid:
            pair_ratios.append(dict(specimen=specimen, cycles=int(cycle), actuator=int(p[0]),
                                    sensor=int(p[1]), rms_ratio=rms_ratio[p], ptp_ratio=ptp_ratio[p]))
    return checkpoints, pair_ratios, reference


def input_columns(input_set, protocol):
    """Return the feature columns of an input set.

    Parameters
    ----------
    input_set : str
        ``'single_path_1_7'`` or ``'multi_path_36'``.
    protocol : dict
        Output of :func:`load_protocol`.

    Returns
    -------
    list of str
        Two column names.
    """
    return list(protocol['features']['input_sets'][input_set]['columns'])


def select_final(candidates, protocol):
    """Apply the predeclared worst-direction-MAE selection rule.

    Parameters
    ----------
    candidates : list of dict
        One row per (model, input_set) with ``model``, ``input_set`` and
        ``worst_direction_MAE`` (MLP: five-seed median per direction, then max).
    protocol : dict
        Output of :func:`load_protocol`.

    Returns
    -------
    dict
        ``selected`` (the chosen row), ``minimum`` worst-direction MAE and the
        ``tied`` candidates within the tolerance, in tie-break order.

    Raises
    ------
    ValueError
        If the candidate set is not exactly the 8 declared candidates.

    Examples
    --------
    >>> p = {'selection_rule': {'tie_tolerance_mae': 0.0005, 'tie_break_order': {
    ...     'model': list(FAMILIES), 'input_set': list(INPUT_SETS)}}}
    >>> rows = [dict(model=m, input_set=i, worst_direction_MAE=0.1) for m in FAMILIES
    ...         for i in INPUT_SETS]
    >>> rows[-1]['worst_direction_MAE'] = 0.0996   # MLP multi-path, within tolerance
    >>> select_final(rows, p)['selected']['model']
    'LinearRegression'
    """
    rule = protocol['selection_rule']
    require(sorted((c['model'], c['input_set']) for c in candidates) ==
            sorted((m, i) for m in FAMILIES for i in INPUT_SETS), 'Unexpected candidate set')
    best = min(c['worst_direction_MAE'] for c in candidates)
    order_m, order_i = rule['tie_break_order']['model'], rule['tie_break_order']['input_set']
    tied = sorted([c for c in candidates
                   if c['worst_direction_MAE'] - best <= rule['tie_tolerance_mae']],
                  key=lambda c: (order_m.index(c['model']), order_i.index(c['input_set'])))
    return dict(selected=tied[0], minimum=best, tied=tied)


def read_published_labels(data_root, specimen, protocol, workers=1):
    """Read only the published label of every PZT file of one specimen.

    Used for the held-out specimen *after* its predictions have been written,
    so features and predictions are fixed before any label is seen.

    Parameters
    ----------
    data_root : pathlib.Path
        The extracted ``2. Composites`` directory.
    specimen : str
        Specimen name in ``protocol['specimens']``.
    protocol : dict
        Output of :func:`load_protocol`.
    workers : int, optional
        MAT prefetch workers.

    Returns
    -------
    dict
        ``{filename: (cycles, label)}``; ``label`` is ``None`` when missing.
    """
    folder = protocol['specimens'][specimen]['folder']
    files = sorted((data_root / folder / 'PZT-data').glob(specimen + '_*.mat'))
    return {path.name: (scalar(c.get('cycles', [])),
                        scalar(c.get('straingage_data', {}).get('stiffness_degradation', [])))
            for path, _, c in iter_coupons(files, workers)}


def attach_labels(checkpoints, labels):
    """Copy published labels onto checkpoints from their eligible files.

    Parameters
    ----------
    checkpoints : list of dict
        Output of :func:`build_checkpoints` built with ``read_labels=False``.
    labels : dict
        Output of :func:`read_published_labels`.

    Returns
    -------
    list of dict
        Copies with ``published_index`` set (``None`` if no file is labelled).

    Raises
    ------
    ValueError
        If files of one checkpoint carry different labels or a file is unknown.
    """
    out = []
    for cp in checkpoints:
        names = cp['filenames'].split('; ')
        require(all(n in labels for n in names), f"Unknown file at cycle {cp['cycles']}")
        found = {labels[n][1] for n in names if labels[n][1] is not None}
        require(len(found) <= 1, f"Conflicting published labels at cycle {cp['cycles']}")
        out.append(dict(cp, published_index=found.pop() if found else None))
    return out


def sanity_criteria(late_predictions, prediction_at_100k, training_targets, protocol):
    """Evaluate the predeclared plausibility criteria C1-C3 (protocol section 9).

    Parameters
    ----------
    late_predictions : sequence of float
        Frozen-model predictions at the unlabelled late L1S11 checkpoints.
    prediction_at_100k : float
        Frozen-model prediction at the L1S11 100,000-cycle checkpoint.
    training_targets : sequence of float
        Published targets of the pooled training checkpoints.
    protocol : dict
        Output of :func:`load_protocol` (only documents the rule source).

    Returns
    -------
    dict
        Each criterion's inputs and pass flag, and the overall ``pass``.

    Examples
    --------
    >>> r = sanity_criteria([0.2, 0.25], 0.18, [0.05, 0.25], {})
    >>> r['C1']['pass'], r['C2']['pass'], r['C3']['pass'], r['pass']
    (True, True, True, True)
    >>> sanity_criteria([0.5], 0.18, [0.05, 0.25], {})['C3']['pass']
    False
    """
    late = [float(v) for v in late_predictions]
    low, high = min(training_targets), max(training_targets)
    width = high - low
    bounds = (low - 0.5 * width, high + 0.5 * width)
    c1 = dict(mean_late_prediction=float(np.mean(late)), prediction_at_100k=float(prediction_at_100k),
              **{'pass': bool(np.mean(late) >= prediction_at_100k)})
    c2 = dict(bounds=[-0.05, 1.0], min=min(late), max=max(late),
              **{'pass': all(-0.05 <= v <= 1.0 for v in late)})
    c3 = dict(bounds=list(bounds), training_target_range=[low, high], min=min(late), max=max(late),
              **{'pass': all(bounds[0] <= v <= bounds[1] for v in late)})
    return dict(C1=c1, C2=c2, C3=c3, **{'pass': c1['pass'] and c2['pass'] and c3['pass']})
