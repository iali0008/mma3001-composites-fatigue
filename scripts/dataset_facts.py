"""Record dataset facts used in the documentation: label links, strain files, sampling rate.

Reads the three labelled specimens (L1S11, L1S12, L2S11) and writes
``results/dataset_facts/facts.json``. It fits no model and computes no score.

* **Label provenance.** For each labelled file, the strain files named in
  ``coupon.straingage_data.file_location``; and the variables stored in every
  converted strain file (to show whether load is available to recompute the
  stiffness index).
* **Sampling rate.** The stored ``sampling_rate`` values, and an FFT check of
  the actuator signal at every interrogation frequency: if the stored rate were
  right, the spectral peak would sit at the nominal frequency. The implied rate
  is ``nominal_frequency * n_samples / peak_bin``.

Example
-------
``python scripts/dataset_facts.py --data-root "data/2.+Composites/2. Composites"``
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.io import loadmat, whosmat

from common import ROOT, save_json, scalar

SPECIMENS = {'L1S11': 'Layup1/L1_S11_F', 'L1S12': 'Layup1/L1_S12_F', 'L2S11': 'Layup2/L2_S11_F'}
OUT = ROOT / 'results' / 'dataset_facts'


def peak_bin(x):
    """Return the index of the largest non-DC FFT magnitude of a real signal.

    Parameters
    ----------
    x : numpy.ndarray
        Real signal.

    Returns
    -------
    int
        FFT bin with the largest magnitude, excluding bin 0.

    Examples
    --------
    >>> n = 2000
    >>> peak_bin(np.sin(2 * np.pi * 25 * np.arange(n) / n))
    25
    """
    spectrum = np.abs(np.fft.rfft(np.asarray(x, float) - np.mean(x)))
    return int(np.argmax(spectrum[1:]) + 1)


def burst_span(x, fraction=0.05):
    """Return the number of samples between the first and last exceedance of a threshold.

    Parameters
    ----------
    x : numpy.ndarray
        Actuator signal.
    fraction : float, optional
        Threshold as a fraction of the peak absolute deviation from the median.

    Returns
    -------
    int
        Span in samples (0 if nothing exceeds the threshold).
    """
    d = np.abs(np.asarray(x, float) - np.median(x))
    idx = np.flatnonzero(d > fraction * d.max())
    return int(idx[-1] - idx[0] + 1) if len(idx) else 0


def main(argv=None):
    """Collect the facts and write ``facts.json``.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--data-root', required=True, type=Path)
    args = parser.parse_args(argv)
    root = args.data_root.resolve()
    facts = dict(specimens={}, sampling_rate={})
    spectra = defaultdict(list)
    stored_rates = Counter()
    for specimen, folder in SPECIMENS.items():
        links, n_labelled = [], 0
        for path in sorted((root / folder / 'PZT-data').glob(specimen + '_*.mat')):
            c = loadmat(path, simplify_cells=True)['coupon']
            label = scalar(c['straingage_data'].get('stiffness_degradation', []))
            if label is not None:
                n_labelled += 1
                loc = c['straingage_data'].get('file_location', [])
                names = [str(v) for v in np.atleast_1d(loc)] if len(np.atleast_1d(loc)) else []
                links.append(dict(file=path.name, cycles=scalar(c['cycles']), strain_files=names))
            for p in c['path_data']:
                stored_rates[scalar(p['sampling_rate'])] += 1
                if (p['actuator'], p['sensor']) == (1, 7):
                    x = np.asarray(p['signal_actuator'], float)
                    spectra[int(p['frequency'])].append((len(x), peak_bin(x), burst_span(x)))
        variables = Counter()
        strain_files = sorted((root / folder / 'StrainData').glob('*.mat'))
        for f in strain_files:
            variables[', '.join(sorted(v[0] for v in whosmat(f)))] += 1
        facts['specimens'][specimen] = dict(
            labelled_pzt_files=n_labelled, label_links_examples=links[:3] + links[-2:],
            files_with_linked_strain=sum(bool(l['strain_files']) for l in links),
            converted_strain_mat_files=len(strain_files),
            strain_file_variable_sets=dict(variables))
    facts['sampling_rate']['stored_values_all_paths'] = {str(k): v for k, v in stored_rates.items()}
    per_freq = {}
    for freq, rows in sorted(spectra.items()):
        n = Counter(r[0] for r in rows).most_common(1)[0][0]
        bins = Counter(r[1] for r in rows)
        k = bins.most_common(1)[0][0]
        per_freq[str(freq)] = dict(
            signals=len(rows), n_samples=n, peak_bin_counts=dict(bins), modal_peak_bin=k,
            samples_per_period=n / k,
            peak_frequency_if_stored_rate_hz=k * 1.2e6 / n,
            implied_sampling_rate_hz=freq * 1e3 * n / k,
            median_burst_span_samples=float(np.median([r[2] for r in rows])))
    facts['sampling_rate']['actuator_pair_1_7'] = per_freq
    facts['sampling_rate']['note'] = ('Stored rate written as a constant by NEWFILEDEF.m line 102 '
                                      '(Technical Report PDF p. 8); FFT bins have resolution '
                                      'fs/n, so implied rates are approximate.')
    OUT.mkdir(parents=True, exist_ok=True)
    save_json(OUT / 'facts.json', facts)
    print(per_freq)


if __name__ == '__main__':
    main()
