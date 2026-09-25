"""Bounded ordered MAT prefetch, targeting the measured parsing bottleneck."""
from collections import deque
from concurrent.futures import ThreadPoolExecutor
import hashlib

from scipy.io import loadmat


def load_one(path):
    # Preserve the original before/after source hash semantics.
    sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    coupon = loadmat(path, simplify_cells=True)['coupon']
    return path, sha256, coupon


def iter_coupons(paths, workers=1):
    """Yield in original order; at most workers large coupons are prefetched."""
    if workers == 1:
        for path in paths:
            yield load_one(path)
        return
    if workers < 1:
        raise ValueError('workers must be positive')
    iterator = iter(paths)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = deque()
        for _ in range(workers):
            path = next(iterator, None)
            if path is not None:
                pending.append(executor.submit(load_one, path))
        while pending:
            result = pending.popleft().result()
            yield result
            path = next(iterator, None)
            if path is not None:
                pending.append(executor.submit(load_one, path))
