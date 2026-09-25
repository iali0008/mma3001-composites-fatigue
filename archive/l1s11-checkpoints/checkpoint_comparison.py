"""L1S11 exact-setting comparison; run with Python + numpy/scipy/matplotlib.
Only reads original MAT files. All outputs stay beside this script.
Uses stored sample indices 0..1999; waveform amplitude units are unknown.
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

OUT = Path(__file__).resolve().parent
BASE = OUT.parent / '2. Composites/Layup1/L1_S11_F/PZT-data'

def scalar(value):
    a = np.asarray(value)
    if a.size != 1 or not np.issubdtype(a.dtype, np.number):
        return None
    value = float(a.ravel()[0])
    return value if np.isfinite(value) else None

def save_csv(name, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with (OUT / name).open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)

rows, hashes = [], {}
for source in sorted(BASE.glob('L1S11_*.mat')):
    hashes[source.name] = hashlib.sha256(source.read_bytes()).hexdigest()
    c = loadmat(source, simplify_cells=True)['coupon']
    label = scalar(c.get('straingage_data', {}).get('stiffness_degradation', []))
    cycle, load = scalar(c.get('cycles', [])), scalar(c.get('load', []))
    row = dict(filename=source.name, cycles=cycle, load_kips=load,
               published_index=label, condition=c.get('condition', ''),
               actuator=1, receiver=7, nominal_frequency_kHz=150)
    reasons = []
    if cycle is None or cycle <= 0:
        reasons.append('not a positive-cycle checkpoint')
    if label is None:
        reasons.append('missing/nonfinite/nonscalar published index')
    if str(row['condition']).strip().casefold() != 'loaded':
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
        for field, required in [('gain', 33), ('amplitude', 65), ('sampling_rate', 1200000)]:
            row[field] = scalar(p.get(field, []))
            if row[field] != required:
                reasons.append(f'{field} != {required}')
        signals = {}
        for field in ('signal_actuator', 'signal_sensor'):
            x = np.asarray(p.get(field, []), dtype=float).ravel()
            signals[field] = x
            row[field + '_length'] = len(x)
            row[field + '_nonfinite'] = bool(not np.isfinite(x).all())
            row[field + '_constant'] = bool(len(x) and np.isfinite(x).all() and np.all(x == x[0]))
            if len(x) != 2000:
                reasons.append(f'{field} length != 2000')
        if not reasons:
            x = signals['signal_sensor']
            row.update(sample_start=0, sample_end_inclusive=1999)
            # Preserve flagged eligible rows. Never silently drop nonfinite samples.
            valid = np.isfinite(x).all()
            row['peak_to_peak'] = float(np.ptp(x)) if valid else None
            row['mean_centred_rms'] = float(np.sqrt(np.mean((x-x.mean())**2))) if valid else None
    row['eligible'] = not reasons
    row['exclusion_reasons'] = '; '.join(reasons)
    rows.append(row)

eligible = sorted((r for r in rows if r['eligible']), key=lambda r: (r['cycles'], r['filename']))
groups = defaultdict(list)
for row in eligible:
    groups[row['cycles']].append(row)
checkpoints = []
for cycle, repeats in sorted(groups.items()):
    labels = sorted(set(r['published_index'] for r in repeats))
    cp = dict(cycles=int(cycle), eligible_repeats=len(repeats),
              published_index=labels[0] if len(labels) == 1 else None,
              label_conflict=len(labels) != 1,
              published_indices='; '.join(map(str, labels)),
              filenames='; '.join(r['filename'] for r in repeats))
    for feature in ('peak_to_peak', 'mean_centred_rms'):
        values = [r[feature] for r in repeats if r[feature] is not None]
        cp[feature + '_median'] = float(np.median(values)) if values else None
        cp[feature + '_valid_repeats'] = len(values)
    checkpoints.append(cp)

save_csv('checkpoint_recordings.csv', rows)  # All candidates, repeats, flags and exclusions.
save_csv('checkpoint_eligible_recordings.csv', eligible)
save_csv('checkpoint_medians.csv', checkpoints)

fig, axes = plt.subplots(1, 2, figsize=(15, 6))
for ax, feature, title in zip(axes, ('peak_to_peak', 'mean_centred_rms'),
                            ('Received peak-to-peak amplitude', 'Received mean-centred RMS')):
    for j, cp in enumerate(checkpoints):
        x, y = cp['published_index'], cp[feature + '_median']
        if x is None or y is None:
            continue
        ax.scatter(x, y, color='#24628a', s=35)
        offsets = {30000: (-45, 20), 40000: (-45, -24), 50000: (8, -30),
                   60000: (-25, 36), 70000: (12, -12), 80000: (10, 24),
                   90000: (-20, 15), 100000: (8, 10)}
        ax.annotate(f"{cp['cycles']:,}", (x, y), xytext=offsets.get(cp['cycles'], (5, 7)),
                    textcoords='offset points', fontsize=8,
                    arrowprops=dict(arrowstyle='-', color='#999999', lw=0.6))
    ax.set(title=title, xlabel='Published stiffness-degradation index',
           ylabel='Median across eligible repeats (units unknown)')
    ax.margins(x=0.18, y=0.18)
    ax.grid(True, color='#dddddd', linewidth=0.5)
    ax.spines[['top', 'right']].set_visible(False)
fig.suptitle('L1S11 | actuator 1 to receiver 7 | nominal 150 kHz', fontsize=14)
fig.text(0.06, 0.025, f'{len(eligible)} eligible recordings; {len(checkpoints)} distinct checkpoints. Labels are fatigue cycle counts.\n'
         'Samples 0-1999; exact requested settings; no model fitted. Sampling metadata unchanged.', fontsize=10)
fig.tight_layout(rect=(0, 0.10, 1, 0.95))
fig.savefig(OUT / 'checkpoint_features.png', dpi=180)
plt.close(fig)

counts = Counter(reason for row in rows for reason in row['exclusion_reasons'].split('; ') if reason)
flags = {key: sum(r.get(key, False) for r in eligible) for key in
         ('signal_actuator_nonfinite', 'signal_actuator_constant',
          'signal_sensor_nonfinite', 'signal_sensor_constant')}
for name, digest in hashes.items():
    assert hashlib.sha256((BASE / name).read_bytes()).hexdigest() == digest, name
(OUT / 'checkpoint_source_hashes.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
summary = '\n'.join([
    f'Scoped to {len(rows)} L1S11 MAT recordings; no other specimens inspected.',
    f'Eligible recordings (including repeats): {len(eligible)}',
    f'Distinct eligible nonzero-cycle checkpoints: {len(checkpoints)}',
    f'Excluded recordings: {len(rows)-len(eligible)}',
    'Exclusion reason counts (overlapping): ' + json.dumps(dict(counts)),
    'Eligible signal flags: ' + json.dumps(flags),
    'Label-conflict checkpoints: ' + str(sum(c['label_conflict'] for c in checkpoints)),
    'Peak-to-peak = max(x)-min(x); centred RMS = sqrt(mean((x-mean(x))**2)).',
    'Both use received samples 0-1999 inclusive, with no filtering or alignment.',
    'Constant finite signals remain flagged with zero features. Nonfinite received signals',
    'remain in eligible output with blank features; summary counts disclose valid repeats.',
    'Conflicting repeat labels are flagged and not combined into an invented plot target.',
    'Each checkpoint feature is the median across its eligible finite repeats.',
    'Amplitude units unknown. Stored sampling metadata is not changed or corrected.',
    'Loaded/loaded are matched case-insensitively; original condition text is retained.',
    'All inspected source SHA-256 hashes verified unchanged. No model or label imputation.',
    '', 'Checkpoint summaries:', *[str(c) for c in checkpoints]]) + '\n'
(OUT / 'checkpoint_summary.txt').write_text(summary, encoding='utf-8')
print(summary)
