"""Two-specimen OLS comparison. Run: python signal_walkthrough/exploratory_regression.py
Dependencies: numpy, scipy, matplotlib. No tuning, imputation, or source writes.
Reference measurements are chronological anchors, not undamaged baselines.
"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import numpy as np
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path(__file__).resolve().parent / 'exploratory_regression'
OUT.mkdir(exist_ok=True)
BASE = OUT.parent.parent / '2. Composites/Layup1'
SETTINGS = {'L1S11': ('L1_S11_F', 33, 65), 'L1S12': ('L1_S12_F', 35, 50)}
MODELS = {'log10_cycles': ['log10_cycles'], 'relative_rms': ['relative_rms'],
          'relative_rms_and_ptp': ['relative_rms', 'relative_ptp']}

def scalar(v):
    a = np.asarray(v)
    if a.size != 1 or not np.issubdtype(a.dtype, np.number):
        return None
    v = float(a.ravel()[0])
    return v if np.isfinite(v) else None

def save(name, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / name).open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

recordings, checkpoints, references, hashes, exclusions = [], [], [], {}, []
for specimen, (folder, gain, amplitude) in SETTINGS.items():
    local = []
    for path in sorted((BASE / folder / 'PZT-data').glob(specimen + '_*.mat')):
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
        c = loadmat(path, simplify_cells=True)['coupon']
        cycle, load = scalar(c.get('cycles', [])), scalar(c.get('load', []))
        label = scalar(c.get('straingage_data', {}).get('stiffness_degradation', []))
        r = dict(specimen=specimen, filename=path.name, cycles=cycle, load_kips=load,
                 published_index=label, condition=c.get('condition', ''),
                 published_jump_flag=specimen == 'L1S12' and cycle == 30000,
                 peak_to_peak=None, mean_centred_rms=None)
        reasons = []
        if cycle is None or cycle <= 0:
            reasons.append('not a positive-cycle checkpoint')
        if label is None:
            reasons.append('missing/nonfinite/nonscalar published index')
        if str(r['condition']).strip().casefold() != 'loaded':
            reasons.append('condition is not Loaded')
        if load is None or not 3.95 <= load <= 4.05:
            reasons.append('load outside 3.95-4.05 kips')
        paths = c.get('path_data', [])
        if isinstance(paths, dict):
            paths = [paths]
        matches = [p for p in paths if (p.get('actuator'), p.get('sensor'),
                                       p.get('frequency')) == (1, 7, 150)]
        if len(matches) != 1:
            reasons.append('requested path missing or ambiguous')
        else:
            p = matches[0]
            for field, required in [('gain', gain), ('amplitude', amplitude),
                                    ('sampling_rate', 1200000)]:
                r[field] = scalar(p.get(field, []))
                if r[field] != required:
                    reasons.append(f'{field} != {required}')
            signals = {}
            for field in ('signal_actuator', 'signal_sensor'):
                x = np.asarray(p.get(field, []), dtype=float).ravel()
                signals[field] = x
                r[field + '_length'] = len(x)
                r[field + '_nonfinite'] = bool(not np.isfinite(x).all())
                r[field + '_constant'] = bool(len(x) and np.isfinite(x).all() and np.all(x == x[0]))
                if len(x) != 2000:
                    reasons.append(f'{field} length != 2000')
            if not reasons and np.isfinite(signals['signal_sensor']).all():
                x = signals['signal_sensor']
                r['peak_to_peak'] = float(np.ptp(x))
                r['mean_centred_rms'] = float(np.sqrt(np.mean((x - x.mean())**2)))
        r['eligible'] = not reasons
        r['exclusion_reasons'] = '; '.join(reasons)
        local.append(r)
    recordings.extend(local)
    counts = Counter(s for r in local for s in r['exclusion_reasons'].split('; ') if s)
    exclusions.extend(dict(specimen=specimen, reason=k, count=v) for k, v in counts.items())
    groups = defaultdict(list)
    for r in local:
        if r['eligible']:
            groups[r['cycles']].append(r)
    cps = []
    for cycle, repeats in sorted(groups.items()):
        labels = set(r['published_index'] for r in repeats)
        # Do not average conflicting labels or invent a target.
        assert len(labels) == 1, f'Conflicting published labels: {specimen}, {cycle}'
        cp = dict(specimen=specimen, cycles=int(cycle), published_index=labels.pop(),
                  eligible_repeats=len(repeats), filenames='; '.join(r['filename'] for r in repeats),
                  load_min_kips=min(r['load_kips'] for r in repeats),
                  load_max_kips=max(r['load_kips'] for r in repeats),
                  gain=gain, excitation_setting=amplitude, sampling_rate_Hz=1200000,
                  sample_start=0, sample_end_inclusive=1999,
                  published_jump_flag=any(r['published_jump_flag'] for r in repeats))
        for feature in ('mean_centred_rms', 'peak_to_peak'):
            values = [r[feature] for r in repeats if r[feature] is not None]
            cp[feature] = float(np.median(values)) if values else None
            cp[feature + '_valid_repeats'] = len(values)
        cps.append(cp)
    assert cps, f'No eligible checkpoints: {specimen}'
    # Selection uses cycle order ONLY; never inspect or calibrate to the target.
    ref = min(cps, key=lambda r: r['cycles'])
    assert all(ref[f] is not None and ref[f] > 0 for f in ('mean_centred_rms', 'peak_to_peak')), 'Invalid reference denominator'
    references.append(dict(specimen=specimen, cycles=ref['cycles'], filenames=ref['filenames'],
                           rms_denominator=ref['mean_centred_rms'], ptp_denominator=ref['peak_to_peak']))
    for cp in cps:
        assert cp['mean_centred_rms'] is not None and cp['peak_to_peak'] is not None, 'Nonfinite checkpoint features'
        cp['is_reference'] = cp['cycles'] == ref['cycles']
        cp['reference_cycles'] = ref['cycles']
        cp['relative_rms'] = cp['mean_centred_rms'] / ref['mean_centred_rms']
        cp['relative_ptp'] = cp['peak_to_peak'] / ref['peak_to_peak']
        cp['log10_cycles'] = float(np.log10(cp['cycles']))
    checkpoints.extend(cps)

predictions, metrics, coefficients = [], [], []
for train_name, test_name in [('L1S11', 'L1S12'), ('L1S12', 'L1S11')]:
    train = [r for r in checkpoints if r['specimen'] == train_name and not r['is_reference']]
    test = [r for r in checkpoints if r['specimen'] == test_name and not r['is_reference']]
    for model, fields in MODELS.items():
        X = np.array([[1.] + [r[f] for f in fields] for r in train])
        y = np.array([r['published_index'] for r in train])
        Xtest = np.array([[1.] + [r[f] for f in fields] for r in test])
        beta, _, rank, singular = np.linalg.lstsq(X, y, rcond=None)
        assert rank == X.shape[1], 'Rank-deficient design'
        # Check the OLS solution independently using QR decomposition.
        q, upper = np.linalg.qr(X, mode='reduced')
        np.testing.assert_allclose(beta, np.linalg.solve(upper, q.T @ y), rtol=1e-9, atol=1e-10)
        pred = Xtest @ beta  # No clipping, target calibration, or test-dependent tuning.
        observed = np.array([r['published_index'] for r in test])
        residual = pred - observed
        metrics.append(dict(train_specimen=train_name, test_specimen=test_name, model=model,
                            train_checkpoints=len(train), test_checkpoints=len(test),
                            MAE=float(np.mean(abs(residual))), RMSE=float(np.sqrt(np.mean(residual**2)))))
        coefficients.append(dict(train_specimen=train_name, test_specimen=test_name, model=model,
                                 intercept=float(beta[0]), terms='; '.join(fields),
                                 slopes='; '.join(format(b, '.17g') for b in beta[1:]),
                                 design_condition_number=float(singular[0] / singular[-1])))
        for r, prediction in zip(test, pred):
            predictions.append(dict(train_specimen=train_name, test_specimen=test_name, model=model,
                                    cycles=r['cycles'], observed_index=r['published_index'],
                                    predicted_index=float(prediction), residual=float(prediction-r['published_index']),
                                    published_jump_flag=r['published_jump_flag']))

# Specific integrity checks for the requested exclusions and retained jump.
assert not any(r['specimen'] == 'L1S12' and r['cycles'] == 20000 for r in checkpoints)
assert all(r['published_index'] is None for r in recordings if r['specimen'] == 'L1S12' and r['cycles'] == 20000)
assert any(r['specimen'] == 'L1S12' and r['cycles'] == 30000 and r['published_index'] == 0.233175942 for r in checkpoints)
assert all(p['cycles'] != next(r['cycles'] for r in references if r['specimen'] == p['test_specimen']) for p in predictions)
for file, digest in hashes.items():
    assert hashlib.sha256(Path(file).read_bytes()).hexdigest() == digest, file
for name, rows in [('recordings.csv', recordings), ('checkpoint_features.csv', checkpoints),
                   ('references.csv', references), ('predictions.csv', predictions),
                   ('metrics.csv', metrics), ('coefficients.csv', coefficients),
                   ('exclusion_counts.csv', exclusions)]:
    save(name, rows)
(OUT / 'source_hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')

fig, axes = plt.subplots(2, 3, figsize=(14, 9), sharex=True, sharey=True)
all_values = [p[k] for p in predictions for k in ('observed_index', 'predicted_index')]
lo, hi = min(all_values), max(all_values)
pad = (hi-lo)*0.09
limits = (lo-pad, hi+pad)
titles = ['log10(cycle count)', 'Relative RMS', 'Relative RMS + relative peak-to-peak']
for row, (train_name, test_name) in enumerate([('L1S11', 'L1S12'), ('L1S12', 'L1S11')]):
    for col, (model, title) in enumerate(zip(MODELS, titles)):
        ax = axes[row, col]
        ps = [p for p in predictions if p['train_specimen'] == train_name and p['model'] == model]
        ax.plot(limits, limits, '--', color='#777777', lw=1, label='Perfect agreement')
        ax.scatter([p['observed_index'] for p in ps], [p['predicted_index'] for p in ps], color='#24628a', s=30)
        for p in ps:
            if p['published_jump_flag']:
                ax.scatter(p['observed_index'], p['predicted_index'], marker='D', s=65,
                           facecolors='none', edgecolors='#b45e13', linewidths=1.5)
        m = next(m for m in metrics if m['train_specimen'] == train_name and m['model'] == model)
        ax.set(title=f'{train_name} -> {test_name}\n{title}', xlim=limits, ylim=limits,
               xlabel='Observed published index', ylabel='Predicted index')
        ax.text(0.04, 0.96, f"MAE {m['MAE']:.4f}\nRMSE {m['RMSE']:.4f}", transform=ax.transAxes,
                va='top', fontsize=9)
        ax.grid(True, color='#e0e0e0', lw=0.5)
        ax.spines[['top', 'right']].set_visible(False)
        ax.set_aspect('equal', adjustable='box')
fig.suptitle('Exploratory two-specimen OLS comparison | held-out checkpoints only', fontsize=14)
fig.text(0.07, 0.02, 'Each model includes an intercept. References are excluded from fitting and scoring; early reference measurements are required.\n'
         'Dashed line: perfect agreement. Orange diamond: retained L1S12 30,000-cycle index jump. No clipping or label interpolation.', fontsize=9)
fig.tight_layout(rect=(0, 0.07, 1, 0.95))
fig.savefig(OUT / 'predicted_vs_observed.png', dpi=180)
plt.close(fig)

summary = [
    'Exploratory two-specimen comparison requiring an early reference measurement.',
    'Actuator 1 -> receiver 7, nominal 150 kHz; Loaded, 3.95-4.05 kips inclusive.',
    'L1S11 gain 33 / excitation 65; L1S12 gain 35 / excitation 50.',
    'Stored sampling rate 1.2e6 unchanged; both signal lengths 2000; samples 0-1999.',
    'Received PTP=max(x)-min(x); RMS=sqrt(mean((x-mean(x))**2)); then median across eligible repeats.',
    'Relative features = checkpoint median / earliest eligible checkpoint median, selected by cycle order.',
    'Reference targets are never used in fitting, scoring, or calibration; references are not assumed undamaged.',
    'All three models use an intercept and equal checkpoint weights. No tuning on the test specimen.',
    'Missing labels remain missing (including L1S12 20,000); the 30,000-cycle published jump is retained.',
    'No prediction clipping, filtering, alignment, gain correction, or label interpolation.',
    'Raw waveform units unknown; relative features dimensionless; MAE/RMSE in published-index units.',
    'Two specimens cannot establish broad transfer performance or distinguish specimen effects from acquisition-setting effects.',
    'OLS coefficients checked against QR; source SHA-256 hashes verified unchanged.',
    '', 'References:', *[str(r) for r in references], '', 'Coverage:']
for specimen in SETTINGS:
    rs = [r for r in recordings if r['specimen'] == specimen]
    cps = [r for r in checkpoints if r['specimen'] == specimen]
    flagged = sum(any(r.get(k, False) for k in ('signal_actuator_nonfinite', 'signal_actuator_constant',
                                              'signal_sensor_nonfinite', 'signal_sensor_constant')) for r in rs if r['eligible'])
    summary.append(f'{specimen}: {sum(r["eligible"] for r in rs)} eligible recordings; {len(cps)} checkpoints; '
                   f'{len(cps)-1} fit/score checkpoints; {flagged} eligible recordings with signal flags.')
summary += ['', 'Held-out metrics:', *[str(m) for m in metrics]]
text = '\n'.join(summary) + '\n'
(OUT / 'README.txt').write_text(text, encoding='utf-8')
print(text)
