"""Include notices from the exact installed formula dependencies in binaries."""
from importlib.metadata import distribution
from pathlib import Path

PACKAGES = ('mdit-py-plugins', 'latex2mathml', 'mathml2omml', 'ziamath', 'ziafont', 'resvg-py')


def license_files():
    files = [(Path(__file__).resolve().parents[1] / 'docs/licenses/STIX-OFL.txt', 'licenses/STIX')]
    for package in PACKAGES:
        dist = distribution(package)
        for item in dist.files or []:
            if item.name.upper().startswith(('LICENSE', 'COPYING', 'OFL')):
                files.append((Path(dist.locate_file(item)),
                              'licenses/' + package + '/' + item.parent.as_posix()))
    return files
