"""Bounded ordered MAT prefetch, targeting the measured parsing bottleneck."""

from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib

from scipy.io import loadmat


def load_one(path):
    # Preserve the original before/after source hash semantics.
    """Hash and load one PZT MAT file.

    Parameters
    ----------
    path : pathlib.Path
        MAT file.

    Returns
    -------
    tuple
        ``(path, sha256_hex, coupon_dict)``.
    """
    # Hash the exact bytes that are decoded, so the recorded hash proves which file
    # produced each feature.
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    coupon = loadmat(path, simplify_cells=True)['coupon']
    return path, sha256, coupon


def iter_coupons(paths, workers=1):
    """Yield MAT files in their original order, optionally prefetched by threads.

    At most ``workers`` large coupons are held in memory at once.

    Parameters
    ----------
    paths : iterable of pathlib.Path
        MAT files in the order to yield.
    workers : int, optional
        1 for serial loading (default); more for bounded ordered prefetch.

    Yields
    ------
    tuple
        ``(path, sha256_hex, coupon_dict)`` from :func:`load_one`.

    Raises
    ------
    ValueError
        If ``workers`` is less than 1.
    """
    if workers == 1:
        for path in paths:
            yield load_one(path)
        return
    if workers < 1:
        raise ValueError('workers must be positive')
    iterator = iter(paths)
    # Prefetch: keep `workers` reads in flight but yield results strictly in input
    # order, so downstream code (and every output) is identical to the serial loop.
    # The gain comes from overlapping file I/O and MAT decoding, not from reordering.
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = deque()
        for _ in range(workers):
            path = next(iterator, None)
            if path is not None:
                pending.append(executor.submit(load_one, path))
        while pending:
            # popleft() waits for the oldest request first: this is what preserves order.
            result = pending.popleft().result()
            yield result
            path = next(iterator, None)
            if path is not None:
                pending.append(executor.submit(load_one, path))
