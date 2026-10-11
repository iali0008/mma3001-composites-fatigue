"""Shared helpers: integrity checks, hashing, CSV/JSON I/O and configuration.

Every workflow script imports these instead of redefining them, so integrity
checks behave identically everywhere and survive ``python -O`` (unlike
``assert`` statements, which the optimiser removes).
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
"""Repository root (the parent of ``scripts/``)."""

EXPERIMENT_V1_PATH = ROOT / 'config' / 'experiment_v1.json'
"""Frozen constants of the historical (protocol v1) experiments."""

RECORDED_RESULTS = (
    'baseline',
    'repeat_sensitivity',
    'model_comparison',
    'protocol_v2',
    'protocol_v2_audit',
    'reproduction_check',
    'dataset_facts',
    'test_report',
)
"""Recorded folders under ``results/``; workflows must never write into them.

``test_report`` is refreshed only by the documented pytest command."""


def require(condition, message):
    """Raise ``ValueError(message)`` unless ``condition`` is true.

    Parameters
    ----------
    condition : bool
        Integrity condition that must hold.
    message : str
        Explanation used for the exception.

    Raises
    ------
    ValueError
        If ``condition`` is false. Unlike ``assert``, this check is not removed
        when Python runs with ``-O``.

    Examples
    --------
    >>> require(1 + 1 == 2, 'arithmetic is broken')
    >>> require(False, 'stop here')
    Traceback (most recent call last):
    ...
    ValueError: stop here
    """
    if not condition:
        raise ValueError(message)


def require_not_recorded(path, root=ROOT):
    """Refuse an output path that is, contains or sits inside a recorded results folder.

    Parameters
    ----------
    path : pathlib.Path
        Output file or folder requested by the user.
    root : pathlib.Path, optional
        Repository root (a temporary tree in tests).

    Returns
    -------
    pathlib.Path
        The resolved path, when it is safe.

    Raises
    ------
    ValueError
        If writing there would overwrite recorded evidence.

    Examples
    --------
    >>> require_not_recorded(ROOT / 'results' / 'rebuilt' / 'x').name
    'x'
    """
    path = Path(path).resolve()
    root = Path(root).resolve()
    for name in RECORDED_RESULTS:
        folder = root / 'results' / name
        overlap = path == folder or folder in path.parents or path in folder.parents
        require(not overlap, f'Recorded results are immutable; refusing to write to {path}')
    return path


def digest(path):
    """Return the SHA-256 hex digest of a file's bytes.

    Parameters
    ----------
    path : pathlib.Path
        File to hash.

    Returns
    -------
    str
        64-character lowercase hexadecimal digest.
    """
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(paths, base):
    """Record size and modification time of files, keyed relative to ``base``.

    Parameters
    ----------
    paths : iterable of pathlib.Path
        Files to record.
    base : pathlib.Path
        Directory the keys are made relative to.

    Returns
    -------
    dict
        ``{relative_posix_path: {'bytes': int, 'mtime_ns': int}}``. Comparing two
        snapshots detects changed metadata; it is not a content hash.
    """
    return {
        p.relative_to(base).as_posix(): {
            'bytes': p.stat().st_size,
            'mtime_ns': p.stat().st_mtime_ns,
        }
        for p in paths
    }


def read_csv(path):
    """Read a CSV file into a list of string-valued dictionaries.

    Parameters
    ----------
    path : pathlib.Path
        CSV file with a header row. A UTF-8 byte-order mark is tolerated.

    Returns
    -------
    list of dict
        One dictionary per data row; all values are strings.
    """
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows, fields=None):
    """Write dictionaries to a UTF-8 CSV file.

    Parameters
    ----------
    path : pathlib.Path
        Destination file; overwritten if it exists.
    rows : list of dict
        Rows to write. Must be non-empty when ``fields`` is omitted.
    fields : list of str, optional
        Column order. Defaults to the keys of the first row.

    Raises
    ------
    ValueError
        If ``rows`` is empty and ``fields`` is not given.
    """
    require(bool(rows) or fields is not None, f'No rows or columns for {path}')
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def save_json(path, value):
    """Write ``value`` as indented JSON followed by a newline.

    Parameters
    ----------
    path : pathlib.Path
        Destination file.
    value : object
        JSON-serialisable value; other objects are converted with ``str``.
    """
    Path(path).write_text(json.dumps(value, indent=2, default=str) + '\n', encoding='utf-8')


def load_json(path):
    """Read a JSON file.

    Parameters
    ----------
    path : pathlib.Path
        JSON file.

    Returns
    -------
    object
        The decoded value.
    """
    return json.loads(Path(path).read_text(encoding='utf-8'))


def load_experiment_v1(path=EXPERIMENT_V1_PATH):
    """Load the frozen constants of the historical v1 experiments.

    Parameters
    ----------
    path : pathlib.Path, optional
        Configuration file; defaults to ``config/experiment_v1.json``.

    Returns
    -------
    dict
        Specimen settings, acquisition rules, expected counts and integrity
        values used by the baseline, repeat-sensitivity, model-comparison and
        coverage workflows.

    Raises
    ------
    ValueError
        If the file does not declare exactly the two development specimens.
    """
    config = load_json(path)
    require(
        set(config['specimens']) == {'L1S11', 'L1S12'},
        'experiment_v1 must declare exactly L1S11 and L1S12',
    )
    return config


def scalar(value):
    """Return a finite float from a one-element numeric value, else ``None``.

    Parameters
    ----------
    value : object
        Value read from a MATLAB structure (number, array or empty array).

    Returns
    -------
    float or None
        The value as a float, or ``None`` if it is empty, has more than one
        element, is not numeric, or is not finite. Missing labels therefore stay
        missing instead of becoming zero.

    Examples
    --------
    >>> scalar([4.0]), scalar([]), scalar('x'), scalar([1.0, 2.0]), scalar(float('nan'))
    (4.0, None, None, None, None)
    """
    a = np.asarray(value)
    if a.size != 1 or not np.issubdtype(a.dtype, np.number):
        return None
    v = float(a.ravel()[0])
    return v if np.isfinite(v) else None


def waveform_features(x):
    """Return mean-centred RMS and peak-to-peak amplitude of a waveform.

    Parameters
    ----------
    x : numpy.ndarray
        One-dimensional finite receiver signal in raw acquisition units.

    Returns
    -------
    rms : float
        ``sqrt(mean((x - mean(x))**2))``.
    ptp : float
        ``max(x) - min(x)``.

    Notes
    -----
    Both features are in the (unknown) raw acquisition units; only their ratios
    to a reference are used, and those are dimensionless. Neither depends on the
    sampling rate.

    Examples
    --------
    >>> t = np.arange(8000) / 8000
    >>> rms, ptp = waveform_features(3 * np.sin(2 * np.pi * 10 * t))
    >>> round(rms, 6), round(ptp, 6)
    (2.12132, 6.0)
    """
    x = np.asarray(x, dtype=float)
    return float(np.sqrt(np.mean((x - x.mean()) ** 2))), float(np.ptp(x))
