"""Plot one recording. Requires numpy, scipy, matplotlib.
Run: python signal_walkthrough/walkthrough.py
Sources: Layup1/README.pdf pp. 1-2; Documentation/Techical Report.pdf p. 8.
README specifies sampling_rate in Hz and interrogation frequencies in kHz.
The report's export code hard-codes 1.2e6; waveform amplitude units are unknown.
"""
from pathlib import Path
import hashlib
import numpy as np
from scipy.io import loadmat
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

out = Path(__file__).resolve().parent
source = out.parent / '2. Composites/Layup1/L1_S11_F/PZT-data/L1S11_10000_1_2.mat'
before = hashlib.sha256(source.read_bytes()).hexdigest()
c = loadmat(source, simplify_cells=True)['coupon']
# Select by metadata, not by filename suffix or assumed array position.
matches = [(i, p) for i, p in enumerate(c['path_data'])
           if p['actuator'] == 1 and p['sensor'] == 7 and p['frequency'] == 150]
assert len(matches) == 1
i, p = matches[0]
act, received = [np.asarray(p[k], dtype=float).ravel()
                 for k in ('signal_actuator', 'signal_sensor')]
assert len(act) == len(received) and np.isfinite([act, received]).all()
fs = float(p['sampling_rate'])  # Hz, not kHz: README p. 2
t_us = np.arange(len(act)) / fs * 1e6
target = float(c['straingage_data']['stiffness_degradation'])
# Diagnostic only: centering for FFT does not alter the plotted raw signals.
peaks = [np.fft.rfftfreq(len(a), d=1/fs)[1 + np.argmax(
         np.abs(np.fft.rfft(a-a.mean()))[1:])] for a in (act, received)]
summary = f'''File: {source.name}
Cycle count: {c['cycles']}
Load: {c['load']} kips
Boundary condition: {c['condition']}
Published stiffness-degradation index / regression target: {target:.9f}
Target field: coupon.straingage_data.stiffness_degradation
Path: actuator {p['actuator']} -> receiver {p['sensor']}; frequency {p['frequency']} kHz
Path entry: Python index {i} (MATLAB linear index {i+1})
Other stored settings: amplitude={p['amplitude']}, gain={p['gain']}
Sampling rate: {fs:g} Hz; sample interval: {1e6/fs:.9f} microseconds
Samples per signal: {len(act)}; plotted time: 0 to {t_us[-1]:.6f} microseconds
FFT peaks at stored rate: actuator {peaks[0]:g} Hz; receiver {peaks[1]:g} Hz
Timing caveat: ~15 kHz observed versus nominal 150 kHz. Physical time is unverified.
The plot uses the documented stored rate, without silently substituting 12 MHz.
Waveform amplitude units: unknown; settings are not waveform calibration.
Actuator signal: stored excitation-channel trace for the PZT launching Lamb waves.
Received signal: stored receiver response after wave propagation through the coupon.
Regression predicts the published index above from signal-derived inputs.
It does not predict an individual waveform amplitude or cycle count.
Raw signals are plotted without filtering, normalization, alignment or gain correction.
Time zero is the first stored sample; separate y-axis scales are used.
Sources: Layup1/README.pdf pp. 1-2; Documentation/Techical Report.pdf p. 8.
Source SHA-256: {before}
'''
print(summary)
fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
for ax, values, title in zip(axes, (act, received),
        ('Actuator 1 - stored excitation signal', 'Receiver 7 - stored received signal')):
    ax.plot(t_us, values, color='#24628a', linewidth=0.9)
    ax.set_title(title, loc='left', fontsize=11)
    ax.set_ylabel('Amplitude\n(units unknown)')
    ax.grid(True, color='#dddddd', linewidth=0.5)
    ax.spines[['top', 'right']].set_visible(False)
    ax.set_xlim(t_us[0], t_us[-1])
axes[-1].set_xlabel('Time from first sample (microseconds; metadata-based)')
fig.suptitle('L1S11 | 10,000 cycles | Loaded, 4.004 kips\n'
             'Actuator 1 to receiver 7 | nominal 150 kHz | target = 0.076005931', fontsize=13)
fig.text(0.10, 0.025, 'Stored sampling rate: 1.2 MHz; physical timing unverified (~15 kHz FFT peak).\n'
         'Raw exported amplitudes; separate y-axis scales; 2,000 samples per signal.', fontsize=9)
fig.tight_layout(rect=(0, 0.085, 1, 0.92))
fig.savefig(out / 'L1S11_10000_1_2_path_1_7.png', dpi=180)
plt.close(fig)
assert hashlib.sha256(source.read_bytes()).hexdigest() == before, 'Source changed'
(out / 'walkthrough.txt').write_text(summary + 'Source unchanged: SHA-256 verified.\n', encoding='utf-8')
