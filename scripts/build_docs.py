"""Build the HTML API documentation for every script into ``docs/html`` with pdoc.

pdoc renders default values such as the resolved repository root as absolute
local paths. After building, this script replaces the local repository path
with ``<repository>`` so the published pages do not depend on one machine.

Example
-------
``python scripts/build_docs.py``
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from common import ROOT, require

OUT = ROOT / 'docs' / 'html'
PLACEHOLDER = '&lt;repository&gt;'


def local_path_forms(root):
    """Return the spellings of a local path that may appear in generated HTML.

    Parameters
    ----------
    root : pathlib.Path
        Repository root.

    Returns
    -------
    list of str
        Forward-slash, backslash and escaped-backslash forms, longest first.

    Examples
    --------
    >>> 'C:/a/b' in local_path_forms(Path('C:/a/b'))
    True
    """
    posix = root.as_posix()
    windows = posix.replace('/', '\\')
    # pdoc embeds absolute source paths; scrub every spelling so the pages do not
    # reveal the local folder layout.
    forms = {posix, windows, windows.replace('\\', '\\\\')}
    return sorted(forms, key=len, reverse=True)


def main(argv=None):
    """Run pdoc on all modules in ``scripts/`` and scrub local paths.

    Parameters
    ----------
    argv : list of str, optional
        Command-line arguments; defaults to ``sys.argv[1:]``.

    Raises
    ------
    ValueError
        If a generated page still contains the local repository path.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--output', type=Path, default=OUT)
    args = parser.parse_args(argv)
    import pdoc
    import pdoc.render

    scripts = ROOT / 'scripts'
    sys.path.insert(0, str(scripts))
    modules = sorted(p.stem for p in scripts.glob('*.py'))
    pdoc.render.configure(docformat='numpy', footer_text='MMA3001 composites fatigue project')
    pdoc.pdoc(*modules, output_directory=args.output)
    forms = local_path_forms(ROOT)
    for page in args.output.rglob('*.html'):
        text = page.read_text(encoding='utf-8')
        for form in forms:
            text = text.replace(form, PLACEHOLDER)
        require(not any(form in text for form in forms), f'Local path left in {page.name}')
        page.write_text(text, encoding='utf-8', newline='\n')
    print(f'Built {len(modules)} module pages in {args.output}')


if __name__ == '__main__':
    main()
