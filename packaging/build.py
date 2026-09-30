"""Build DocBridge executables and a portable archive without optional engines."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from md2docx import __version__

DIST = ROOT / 'dist'
SPECS = ('md2docx-cli.spec', 'docx2md-cli.spec', 'md2docx-gui.spec')
EXES = ('md2docx.exe', 'docx2md.exe', 'docbridge.exe')
ZIP_NAME = f'docbridge-{__version__}-win64.zip'
DOC_IMAGES = ('workbench-markdown.png', 'workbench-word.png',
              'workbench-advanced.png', 'workbench-doc-support.png')


def run(command, **kwargs):
    try:
        return subprocess.run(command, check=True, cwd=ROOT, **kwargs)
    except subprocess.CalledProcessError as exc:
        for output in (exc.stdout, exc.stderr):
            if output:
                print(output.decode('utf-8', errors='replace') if isinstance(output, bytes) else output,
                      file=sys.stderr, flush=True)
        raise


def validate_artifacts():
    """Verify installed resources and both conversion directions in owned temp files."""
    flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
    with tempfile.TemporaryDirectory(prefix='docbridge-build-') as folder:
        folder = Path(folder)
        for name in EXES[:2]:
            run([str(DIST / name), '--help'], capture_output=True, timeout=45, creationflags=flags)
        markdown = folder / 'document.md'
        markdown.write_text('# DocBridge\n\n**bold** and *italic*\n', encoding='utf-8')
        word = folder / 'document.docx'
        run([str(DIST / 'md2docx.exe'), str(markdown), '-o', str(word)],
            capture_output=True, timeout=90, creationflags=flags)
        if not word.is_file():
            raise RuntimeError('Markdown to Word artifact check failed')
        exported = folder / 'exported'
        run([str(DIST / 'docx2md.exe'), str(word), '-o', str(exported)],
            capture_output=True, timeout=90, creationflags=flags)
        if 'DocBridge' not in (exported / 'document.md').read_text(encoding='utf-8'):
            raise RuntimeError('Word to Markdown artifact check failed')
        snapshot = folder / 'window.png'
        try:
            run([str(DIST / 'docbridge.exe'), '--selftest', str(snapshot)],
                capture_output=True, timeout=90, creationflags=flags)
        except subprocess.CalledProcessError:
            log = Path(str(snapshot) + '.log')
            if log.is_file():
                print(log.read_text(encoding='utf-8'), file=sys.stderr, flush=True)
            raise
        if not snapshot.is_file() or snapshot.stat().st_size < 5000:
            raise RuntimeError('GUI artifact check failed')


def make_release_zip():
    target = DIST / ZIP_NAME
    paths = [*(DIST / name for name in EXES), ROOT / 'README.md',
             ROOT / 'docs/architecture.md', ROOT / 'examples/quickstart.md',
             *sorted((ROOT / 'config').glob('*.yaml')),
             *(ROOT / 'docs' / name for name in DOC_IMAGES)]
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as package:
        for path in paths:
            if not path.is_file():
                raise FileNotFoundError(path)
            name = path.name if path.parent == DIST else path.relative_to(ROOT).as_posix()
            package.write(path, name)
        package.writestr('START.txt', 'Run docbridge.exe. Optional .doc support is downloaded only when requested in the GUI.\n')
    return target


def main():
    parser = argparse.ArgumentParser(description='Build DocBridge for Windows')
    parser.add_argument('--clean', action='store_true')
    parser.add_argument('--workpath', default=str(ROOT / 'build'))
    parser.add_argument('--skip-smoke', action='store_true', help='Skip executable verification')
    parser.add_argument('--skip-zip', action='store_true')
    args = parser.parse_args()
    run([sys.executable, str(ROOT / 'packaging/make_icon.py')])
    for name in SPECS:
        command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(DIST),
                   '--workpath', str(Path(args.workpath).resolve())]
        if args.clean:
            command.append('--clean')
        run([*command, str(ROOT / 'packaging' / name)])
    for name in EXES:
        if not (DIST / name).is_file():
            raise FileNotFoundError(DIST / name)
    if not args.skip_smoke:
        validate_artifacts()
    if not args.skip_zip:
        print(make_release_zip(), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
