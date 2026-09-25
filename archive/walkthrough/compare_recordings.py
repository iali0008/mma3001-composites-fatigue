"""Compare only two PZT records; requires numpy, scipy, matplotlib.
Run: python signal_walkthrough/compare_recordings.py
Units: Layup1/README.pdf pp. 1-2 specifies load in kips, rate in Hz,
and nominal interrogation frequencies in kHz. Waveform units are unknown.
"""
from pathlib import Path
import csv
import hashlib
import numpy as np
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out = Path(__file__).resolve().parent
base = out.parent / '2. Composites/Layup1/L1_S11_F/PZT-data'
records = []
for cycles in (10000, 100000):
    source = base / f'L1S11_{cycles}_1_2.mat'
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    coupon = loadmat(source, simplify_cells=True)['coupon']
    matches = [p for p in coupon['path_data'] if
               (p['actuator'], p['sensor'], p['frequency']) == (1, 7, 150)]
    assert len(matches) == 1, 'Path selection must be unique'
    p = matches[0]
    signals = {k: np.asarray(p[k], dtype=float).ravel()
               for k in ('signal_actuator', 'signal_sensor')}
    assert all(np.isfinite(a).all() for a in signals.values())
    row = dict(file=source.name, cycles=coupon['cycles'],
               condition=coupon['condition'], load_kips=coupon['load'],
               gain=p['gain'], excitation_amplitude_setting=p['amplitude'],
               sampling_rate_Hz=p['sampling_rate'],
               actuator_samples=len(signals['signal_actuator']),
               receiver_samples=len(signals['signal_sensor']),
               stiffness_index=coupon['straingage_data']['stiffness_degradation'])
    records.append((source, digest, signals['signal_sensor'], row))

# Same zero-based range, without alignment, resampling or gain correction.
n = min(len(r[2]) for r in records)
assert n > 0
for _, _, signal, row in records:
    x = signal[:n]
    row.update(sample_start=0, sample_end_inclusive=n-1,
               peak_to_peak=float(np.ptp(x)),
               mean_centred_rms=float(np.sqrt(np.mean((x-x.mean())**2))))

lines = ['L1S11: actuator 1 -> receiver 7, nominal 150 kHz',
         f'Common sample range: 0-{n-1} inclusive ({n} samples).',
         'Received waveform amplitude units: unknown.', '', 'Acquisition comparison:']
for key in ('condition', 'load_kips', 'gain', 'excitation_amplitude_setting',
            'sampling_rate_Hz', 'actuator_samples', 'receiver_samples'):
    a, b = [r[3][key] for r in records]
    status = 'SAME' if a == b else 'DIFFERENT'
    delta = f'; delta={b-a:+.9g}' if a != b and isinstance(a, (int, float)) else ''
    lines.append(f'{key}: {a} -> {b}; {status}{delta}')
lines += ['', 'Received-signal metrics:',
          'Peak-to-peak = max(x) - min(x).',
          'Mean-centred RMS = sqrt(mean((x - mean(x))**2)).']
for _, _, _, row in records:
    lines.append(f"{row['file']}: published stiffness index={row['stiffness_index']:.9f}; "
                 f"peak-to-peak={row['peak_to_peak']:.9f}; "
                 f"mean-centred RMS={row['mean_centred_rms']:.9f}")
lines += ['', 'Overlay uses raw exported samples. No filtering, alignment, normalization,',
          'gain correction, sampling-metadata edits, or model training.',
          'Matching stored rates does not resolve the physical timing issue in walkthrough.txt.',
          'Gain and excitation amplitude are reported as stored settings, not waveform units.']

fig, ax = plt.subplots(figsize=(11, 5.5))
for record, color, style in zip(records, ('#24628a', '#b45e13'), ('-', '--')):
    row = record[3]
    ax.plot(np.arange(n), record[2][:n], color=color, linestyle=style,
            linewidth=1.1, label=f"{row['cycles']:,} cycles")
ax.set(title='L1S11 received waveforms | actuator 1 to receiver 7 | nominal 150 kHz',
       xlabel='Sample number (zero-based)', ylabel='Received amplitude (units unknown)',
       xlim=(0, n-1))
ax.grid(True, color='#dddddd', linewidth=0.5)
ax.spines[['top', 'right']].set_visible(False)
ax.legend(frameon=False)
fig.text(0.10, 0.025, f'Common range: samples 0-{n-1}. Raw signals; no alignment or gain correction.\n'
         'Sampling metadata unchanged; physical timing remains unverified.', fontsize=9)
fig.tight_layout(rect=(0, 0.10, 1, 1))
fig.savefig(out / 'received_comparison.png', dpi=180)
plt.close(fig)
for source, digest, _, _ in records:
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, 'Source changed'
    lines.append(f'Unchanged SHA-256: {source.name}: {digest}')
summary = '\n'.join(lines) + '\n'
print(summary)
(out / 'comparison.txt').write_text(summary, encoding='utf-8')
with (out / 'comparison.csv').open('w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=list(records[0][3]))
    writer.writeheader()
    writer.writerows(r[3] for r in records)
